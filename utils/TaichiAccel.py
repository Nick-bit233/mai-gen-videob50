"""
TaichiAccel.py - Taichi GPU 加速模块

使用 Taichi 实现 GPU 加速的图像合成操作，替代 MoviePy 逐帧 CPU 处理。
支持自动选择最佳 GPU 后端（CUDA > Vulkan > Metal > OpenGL > CPU）。
"""

import numpy as np
import traceback

try:
    import taichi as ti
    TAICHI_AVAILABLE = True
except ImportError:
    TAICHI_AVAILABLE = False

_ti_initialized = False


def init_taichi(arch=None):
    """
    初始化 Taichi 运行时，自动选择最佳 GPU 后端。
    如果 GPU 不可用则回退到 CPU。
    """
    global _ti_initialized
    if _ti_initialized:
        return True
    if not TAICHI_AVAILABLE:
        print("[TaichiAccel] Warning: taichi 未安装，GPU 加速不可用")
        return False

    if arch is not None:
        try:
            ti.init(arch=arch)
            _ti_initialized = True
            print(f"[TaichiAccel] 已使用指定后端初始化: {arch}")
            return True
        except Exception:
            pass

    # 按优先级尝试 GPU 后端 (macOS 上 Metal 优先于 Vulkan)
    import platform
    if platform.system() == "Darwin":
        backends = [
            (ti.metal, "Metal"),
            (ti.vulkan, "Vulkan"),
            (ti.cpu, "CPU"),
        ]
    else:
        backends = [
            (ti.cuda, "CUDA"),
            (ti.vulkan, "Vulkan"),
            (ti.opengl, "OpenGL"),
            (ti.cpu, "CPU"),
        ]
    for backend_arch, name in backends:
        try:
            ti.init(arch=backend_arch)
            # Taichi 可能静默回退到其他后端，检查实际使用的后端
            # 注意：current_cfg() 是 Taichi 内部 API，通过 try/except 保护兼容性
            try:
                actual_arch = ti.lang.impl.current_cfg().arch
            except AttributeError:
                actual_arch = backend_arch  # API 变更时假设未回退
            if actual_arch != backend_arch and backend_arch != ti.cpu:
                ti.reset()
                continue
            actual_name = str(actual_arch).replace("Arch.", "").upper()
            _ti_initialized = True
            print(f"[TaichiAccel] ✓ 使用 {actual_name} 后端初始化成功")
            return True
        except Exception:
            try:
                ti.reset()
            except Exception:
                pass
            continue

    print("[TaichiAccel] Warning: 所有后端均初始化失败")
    return False


def is_available():
    """检查 Taichi 加速是否可用"""
    return TAICHI_AVAILABLE and _ti_initialized


# ============================================================================
# Taichi Kernels
# ============================================================================

if TAICHI_AVAILABLE:

    # ------------------------------------------------------------------
    # 核心原则：所有 kernel 的最外层 for 遍历每个像素 (i,j)，
    # Taichi 自动将其映射为 GPU thread，保证逐像素并行。
    # 蒙版(mask)作为独立 2D ndarray 传入，避免 kernel 内部动态
    # shape 分支，确保 warp 内所有线程走同一条指令路径。
    # ------------------------------------------------------------------

    @ti.kernel
    def _alpha_composite_kernel(
        base: ti.types.ndarray(dtype=ti.f32, ndim=3),
        overlay_rgb: ti.types.ndarray(dtype=ti.f32, ndim=3),
        mask: ti.types.ndarray(dtype=ti.f32, ndim=2),
        out: ti.types.ndarray(dtype=ti.f32, ndim=3),
        ox: ti.i32, oy: ti.i32,
        overlay_h: ti.i32, overlay_w: ti.i32,
        base_h: ti.i32, base_w: ti.i32
    ):
        """逐像素并行 alpha 混合：mask 为独立 2D 蒙版 [0,1]"""
        for i, j in ti.ndrange(base_h, base_w):
            si = i - oy
            sj = j - ox
            if 0 <= si < overlay_h and 0 <= sj < overlay_w:
                a = mask[si, sj]
                inv_a = 1.0 - a
                for c in ti.static(range(3)):
                    out[i, j, c] = base[i, j, c] * inv_a + overlay_rgb[si, sj, c] * a
            else:
                for c in ti.static(range(3)):
                    out[i, j, c] = base[i, j, c]

    @ti.kernel
    def _multiply_brightness_kernel(
        src: ti.types.ndarray(dtype=ti.f32, ndim=3),
        out: ti.types.ndarray(dtype=ti.f32, ndim=3),
        factor: ti.f32,
        h: ti.i32, w: ti.i32
    ):
        """逐像素并行亮度调整"""
        for i, j in ti.ndrange(h, w):
            for c in ti.static(range(3)):
                out[i, j, c] = ti.min(src[i, j, c] * factor, 255.0)

    @ti.kernel
    def _crossfade_kernel(
        frame_a: ti.types.ndarray(dtype=ti.f32, ndim=3),
        frame_b: ti.types.ndarray(dtype=ti.f32, ndim=3),
        out: ti.types.ndarray(dtype=ti.f32, ndim=3),
        alpha: ti.f32,
        h: ti.i32, w: ti.i32
    ):
        """逐像素并行交叉淡入淡出"""
        for i, j in ti.ndrange(h, w):
            inv_alpha = 1.0 - alpha
            for c in ti.static(range(3)):
                out[i, j, c] = frame_a[i, j, c] * inv_alpha + frame_b[i, j, c] * alpha

    @ti.kernel
    def _resize_bilinear_kernel(
        src: ti.types.ndarray(dtype=ti.f32, ndim=3),
        out: ti.types.ndarray(dtype=ti.f32, ndim=3),
        src_h: ti.i32, src_w: ti.i32,
        dst_h: ti.i32, dst_w: ti.i32
    ):
        """逐像素并行双线性插值缩放 (固定 3 通道)"""
        for i, j in ti.ndrange(dst_h, dst_w):
            src_y = ti.cast(i, ti.f32) * ti.cast(src_h, ti.f32) / ti.cast(dst_h, ti.f32)
            src_x = ti.cast(j, ti.f32) * ti.cast(src_w, ti.f32) / ti.cast(dst_w, ti.f32)

            y0 = ti.cast(ti.floor(src_y), ti.i32)
            x0 = ti.cast(ti.floor(src_x), ti.i32)
            y1 = ti.min(y0 + 1, src_h - 1)
            x1 = ti.min(x0 + 1, src_w - 1)

            fy = src_y - ti.cast(y0, ti.f32)
            fx = src_x - ti.cast(x0, ti.f32)

            w00 = (1.0 - fx) * (1.0 - fy)
            w01 = fx * (1.0 - fy)
            w10 = (1.0 - fx) * fy
            w11 = fx * fy

            for c in ti.static(range(3)):
                out[i, j, c] = (src[y0, x0, c] * w00 +
                                src[y0, x1, c] * w01 +
                                src[y1, x0, c] * w10 +
                                src[y1, x1, c] * w11)

    @ti.kernel
    def _resize_bilinear_4ch_kernel(
        src: ti.types.ndarray(dtype=ti.f32, ndim=3),
        out: ti.types.ndarray(dtype=ti.f32, ndim=3),
        src_h: ti.i32, src_w: ti.i32,
        dst_h: ti.i32, dst_w: ti.i32
    ):
        """逐像素并行双线性插值缩放 (固定 4 通道 RGBA)"""
        for i, j in ti.ndrange(dst_h, dst_w):
            src_y = ti.cast(i, ti.f32) * ti.cast(src_h, ti.f32) / ti.cast(dst_h, ti.f32)
            src_x = ti.cast(j, ti.f32) * ti.cast(src_w, ti.f32) / ti.cast(dst_w, ti.f32)

            y0 = ti.cast(ti.floor(src_y), ti.i32)
            x0 = ti.cast(ti.floor(src_x), ti.i32)
            y1 = ti.min(y0 + 1, src_h - 1)
            x1 = ti.min(x0 + 1, src_w - 1)

            fy = src_y - ti.cast(y0, ti.f32)
            fx = src_x - ti.cast(x0, ti.f32)

            w00 = (1.0 - fx) * (1.0 - fy)
            w01 = fx * (1.0 - fy)
            w10 = (1.0 - fx) * fy
            w11 = fx * fy

            for c in ti.static(range(4)):
                out[i, j, c] = (src[y0, x0, c] * w00 +
                                src[y0, x1, c] * w01 +
                                src[y1, x0, c] * w10 +
                                src[y1, x1, c] * w11)

    @ti.kernel
    def _five_layer_composite_kernel(
        bg: ti.types.ndarray(dtype=ti.f32, ndim=3),
        video: ti.types.ndarray(dtype=ti.f32, ndim=3),
        score_rgb: ti.types.ndarray(dtype=ti.f32, ndim=3),
        score_mask: ti.types.ndarray(dtype=ti.f32, ndim=2),
        text_rgb: ti.types.ndarray(dtype=ti.f32, ndim=3),
        text_mask: ti.types.ndarray(dtype=ti.f32, ndim=2),
        out: ti.types.ndarray(dtype=ti.f32, ndim=3),
        bg_brightness: ti.f32,
        vid_x: ti.i32, vid_y: ti.i32,
        vid_h: ti.i32, vid_w: ti.i32,
        score_h: ti.i32, score_w: ti.i32,
        text_x: ti.i32, text_y: ti.i32,
        text_h: ti.i32, text_w: ti.i32,
        out_h: ti.i32, out_w: ti.i32
    ):
        """
        逐像素并行 5 层合成内核。
        蒙版(score_mask, text_mask)为独立 2D 数组，无动态分支。
        层顺序: black → bg (dimmed) → video → score → text
        """
        for i, j in ti.ndrange(out_h, out_w):
            # Layer 1: 背景 (dimmed)
            r = bg[i, j, 0] * bg_brightness
            g = bg[i, j, 1] * bg_brightness
            b = bg[i, j, 2] * bg_brightness

            # Layer 2: 谱面视频 (直接覆盖，无 alpha)
            vi = i - vid_y
            vj = j - vid_x
            if 0 <= vi < vid_h and 0 <= vj < vid_w:
                r = video[vi, vj, 0]
                g = video[vi, vj, 1]
                b = video[vi, vj, 2]

            # Layer 3: 成绩图 (mask 混合)
            if i < score_h and j < score_w:
                sa = score_mask[i, j]
                inv_sa = 1.0 - sa
                r = r * inv_sa + score_rgb[i, j, 0] * sa
                g = g * inv_sa + score_rgb[i, j, 1] * sa
                b = b * inv_sa + score_rgb[i, j, 2] * sa

            # Layer 4: 文字 (mask 混合)
            ti_i = i - text_y
            tj_j = j - text_x
            if 0 <= ti_i < text_h and 0 <= tj_j < text_w:
                ta = text_mask[ti_i, tj_j]
                inv_ta = 1.0 - ta
                r = r * inv_ta + text_rgb[ti_i, tj_j, 0] * ta
                g = g * inv_ta + text_rgb[ti_i, tj_j, 1] * ta
                b = b * inv_ta + text_rgb[ti_i, tj_j, 2] * ta

            out[i, j, 0] = ti.min(r, 255.0)
            out[i, j, 1] = ti.min(g, 255.0)
            out[i, j, 2] = ti.min(b, 255.0)

    @ti.kernel
    def _five_layer_fast_kernel(
        bg: ti.types.ndarray(dtype=ti.f32, ndim=3),
        video_u8: ti.types.ndarray(dtype=ti.u8, ndim=3),
        score_rgb: ti.types.ndarray(dtype=ti.f32, ndim=3),
        score_mask: ti.types.ndarray(dtype=ti.f32, ndim=2),
        text_rgb: ti.types.ndarray(dtype=ti.f32, ndim=3),
        text_mask: ti.types.ndarray(dtype=ti.f32, ndim=2),
        out: ti.types.ndarray(dtype=ti.u8, ndim=3),
        bg_brightness: ti.f32,
        vid_x: ti.i32, vid_y: ti.i32,
        vid_h: ti.i32, vid_w: ti.i32,
        score_h: ti.i32, score_w: ti.i32,
        text_x: ti.i32, text_y: ti.i32,
        text_h: ti.i32, text_w: ti.i32,
        out_h: ti.i32, out_w: ti.i32
    ):
        """
        零拷贝快速路径：video 输入为 uint8，输出直接写 uint8，
        跳过 Python 端 float32 转换和 np.clip，减少内存带宽开销。
        """
        for i, j in ti.ndrange(out_h, out_w):
            r = bg[i, j, 0] * bg_brightness
            g = bg[i, j, 1] * bg_brightness
            b = bg[i, j, 2] * bg_brightness

            vi = i - vid_y
            vj = j - vid_x
            if 0 <= vi < vid_h and 0 <= vj < vid_w:
                r = ti.cast(video_u8[vi, vj, 0], ti.f32)
                g = ti.cast(video_u8[vi, vj, 1], ti.f32)
                b = ti.cast(video_u8[vi, vj, 2], ti.f32)

            if i < score_h and j < score_w:
                sa = score_mask[i, j]
                inv_sa = 1.0 - sa
                r = r * inv_sa + score_rgb[i, j, 0] * sa
                g = g * inv_sa + score_rgb[i, j, 1] * sa
                b = b * inv_sa + score_rgb[i, j, 2] * sa

            ti_i = i - text_y
            tj_j = j - text_x
            if 0 <= ti_i < text_h and 0 <= tj_j < text_w:
                ta = text_mask[ti_i, tj_j]
                inv_ta = 1.0 - ta
                r = r * inv_ta + text_rgb[ti_i, tj_j, 0] * ta
                g = g * inv_ta + text_rgb[ti_i, tj_j, 1] * ta
                b = b * inv_ta + text_rgb[ti_i, tj_j, 2] * ta

            out[i, j, 0] = ti.cast(ti.min(ti.max(r, 0.0), 255.0), ti.u8)
            out[i, j, 1] = ti.cast(ti.min(ti.max(g, 0.0), 255.0), ti.u8)
            out[i, j, 2] = ti.cast(ti.min(ti.max(b, 0.0), 255.0), ti.u8)


# ============================================================================
# Python API Wrappers
# ============================================================================

# ============================================================================
# 辅助函数：从 RGBA 图像拆分 RGB + mask
# ============================================================================

def _split_rgba(image: np.ndarray):
    """
    将 RGBA 图像拆分为 RGB (H,W,3) float32 和 mask (H,W) float32 [0,1]。
    如果输入是 RGB (无 alpha)，返回 RGB + 全 1 mask（完全不透明）。
    """
    if image.ndim == 3 and image.shape[2] == 4:
        rgb = image[:, :, :3].astype(np.float32)
        mask = image[:, :, 3].astype(np.float32) / 255.0
    elif image.ndim == 3 and image.shape[2] == 3:
        rgb = image.astype(np.float32)
        mask = np.ones((image.shape[0], image.shape[1]), dtype=np.float32)
    else:
        raise ValueError(f"Unsupported image shape: {image.shape}")
    return rgb, mask


def alpha_composite(base: np.ndarray, overlay: np.ndarray,
                    position: tuple = (0, 0)) -> np.ndarray:
    """
    GPU 加速的 alpha 混合。蒙版自动从 RGBA 第4通道拆分。
    
    Args:
        base: 底图 (H, W, 3|4) uint8
        overlay: 叠加图 (H, W, 3|4) uint8, 支持 RGBA alpha 通道
        position: (x, y) 叠加位置
    Returns:
        合成结果 (H, W, 3) uint8
    """
    if not is_available():
        raise RuntimeError("Taichi 未初始化")

    h, w = base.shape[:2]
    oh, ow = overlay.shape[:2]
    ox, oy = int(position[0]), int(position[1])

    base_f = base[:, :, :3].astype(np.float32)
    overlay_rgb, mask = _split_rgba(overlay)
    out = np.zeros((h, w, 3), dtype=np.float32)

    _alpha_composite_kernel(base_f, overlay_rgb, mask, out, ox, oy, oh, ow, h, w)
    return np.clip(out, 0, 255).astype(np.uint8)


def multiply_brightness(image: np.ndarray, factor: float) -> np.ndarray:
    """GPU 加速的亮度调整"""
    if not is_available():
        raise RuntimeError("Taichi 未初始化")

    h, w = image.shape[:2]
    src = image.astype(np.float32)
    out = np.zeros_like(src)
    _multiply_brightness_kernel(src, out, factor, h, w)
    return np.clip(out, 0, 255).astype(np.uint8)


def resize_bilinear(image: np.ndarray, target_size: tuple) -> np.ndarray:
    """
    GPU 加速的双线性插值缩放。

    Args:
        image: 输入图像 (H, W, 3|4) uint8
        target_size: (target_width, target_height)
    Returns:
        缩放后图像 uint8，通道数与输入一致
    """
    if not is_available():
        raise RuntimeError("Taichi 未初始化")

    dst_w, dst_h = target_size
    src_h, src_w = image.shape[:2]
    channels = image.shape[2] if image.ndim == 3 else 3

    src = image.astype(np.float32)
    if src.ndim == 2:
        src = np.stack([src, src, src], axis=-1)
        channels = 3

    if channels == 4:
        out = np.zeros((dst_h, dst_w, 4), dtype=np.float32)
        _resize_bilinear_4ch_kernel(src, out, src_h, src_w, dst_h, dst_w)
    else:
        src = src[:, :, :3]
        out = np.zeros((dst_h, dst_w, 3), dtype=np.float32)
        _resize_bilinear_kernel(src, out, src_h, src_w, dst_h, dst_w)
    return np.clip(out, 0, 255).astype(np.uint8)


def crossfade(frame_a: np.ndarray, frame_b: np.ndarray, alpha: float) -> np.ndarray:
    """GPU 加速的交叉淡入淡出混合"""
    if not is_available():
        raise RuntimeError("Taichi 未初始化")

    h, w = frame_a.shape[:2]
    a_f = frame_a.astype(np.float32)
    b_f = frame_b.astype(np.float32)
    out = np.zeros_like(a_f)
    _crossfade_kernel(a_f, b_f, out, alpha, h, w)
    return np.clip(out, 0, 255).astype(np.uint8)


def composite_five_layers(
    bg: np.ndarray,
    video_frame: np.ndarray,
    score_image: np.ndarray,
    text_image: np.ndarray,
    video_pos: tuple,
    text_pos: tuple,
    bg_brightness: float = 0.8,
    output_size: tuple = (1920, 1080)
) -> np.ndarray:
    """
    GPU 加速的 5 层合成 —— 单次 kernel 调用替代 MoviePy CompositeVideoClip。
    
    蒙版处理策略：RGBA 图像的第4通道在 Python 端拆分为独立 2D mask 数组，
    kernel 内部不做任何 shape 动态分支，确保所有像素走完全相同的指令路径，
    最大化 GPU warp/SIMD 利用率。

    层顺序: black → bg (dimmed) → video → score_image (mask) → text (mask)
    
    Args:
        bg: 背景图/帧 (H, W, 3) uint8
        video_frame: 谱面视频帧 (H, W, 3) uint8
        score_image: 成绩图 (H, W, 4) uint8 RGBA
        text_image: 文字图 (H, W, 4) uint8 RGBA
        video_pos: (x, y) 视频位置
        text_pos: (x, y) 文字位置
        bg_brightness: 背景亮度系数
        output_size: (width, height) 输出尺寸
    Returns:
        合成帧 (H, W, 3) uint8 RGB
    """
    if not is_available():
        raise RuntimeError("Taichi 未初始化")

    out_w, out_h = output_size
    vid_x, vid_y = int(video_pos[0]), int(video_pos[1])
    text_x, text_y = int(text_pos[0]), int(text_pos[1])
    vid_h, vid_w = video_frame.shape[:2]

    bg_f = bg[:, :, :3].astype(np.float32)
    video_f = video_frame[:, :, :3].astype(np.float32)

    # 拆分蒙版：RGB + mask 分离传入 kernel
    score_rgb, score_mask = _split_rgba(score_image)
    text_rgb, text_mask = _split_rgba(text_image)
    score_h, score_w = score_rgb.shape[:2]
    text_h, text_w = text_rgb.shape[:2]

    out = np.zeros((out_h, out_w, 3), dtype=np.float32)

    _five_layer_composite_kernel(
        bg_f, video_f, score_rgb, score_mask, text_rgb, text_mask, out,
        bg_brightness,
        vid_x, vid_y, vid_h, vid_w,
        score_h, score_w,
        text_x, text_y, text_h, text_w,
        out_h, out_w
    )
    return np.clip(out, 0, 255).astype(np.uint8)


class FrameCompositor:
    """
    高性能帧合成器：预计算静态层，复用缓冲区。

    一个视频片段内 score_image / text_image / bg(静态背景) 不会逐帧变化，
    因此在构造时一次性完成 RGBA 拆分和 float32 转换，帧循环里只传入
    变化的 video_frame (uint8)，由 _five_layer_fast_kernel 在 GPU 内部
    做 u8→f32 转换，避免 Python 端每帧 ~20MB 的内存拷贝。
    """

    def __init__(
        self,
        bg: np.ndarray,
        score_image: np.ndarray,
        text_image: np.ndarray,
        video_pos: tuple,
        text_pos: tuple,
        bg_brightness: float = 0.8,
        output_size: tuple = (1920, 1080),
    ):
        if not is_available():
            raise RuntimeError("Taichi 未初始化")

        self.out_w, self.out_h = output_size
        self.vid_x, self.vid_y = int(video_pos[0]), int(video_pos[1])
        self.text_x, self.text_y = int(text_pos[0]), int(text_pos[1])
        self.bg_brightness = float(bg_brightness)

        # 静态层预计算（一次性）
        self.bg_f = bg[:, :, :3].astype(np.float32)
        self.score_rgb, self.score_mask = _split_rgba(score_image)
        self.text_rgb, self.text_mask = _split_rgba(text_image)
        self.score_h, self.score_w = self.score_rgb.shape[:2]
        self.text_h, self.text_w = self.text_rgb.shape[:2]

        # 输出缓冲区复用
        self._out_buf = np.zeros((self.out_h, self.out_w, 3), dtype=np.uint8)

    def update_bg(self, bg: np.ndarray):
        """动态背景（视频背景）时更新 bg，复用缓冲区避免每帧分配"""
        src = bg[:, :, :3]
        if self.bg_f.shape[:2] == src.shape[:2]:
            np.copyto(self.bg_f, src, casting='unsafe')
        else:
            self.bg_f = src.astype(np.float32)

    def composite(self, video_frame: np.ndarray) -> np.ndarray:
        """
        合成一帧。video_frame 为 uint8 RGB，直接传入 GPU kernel。
        返回的 ndarray 是内部缓冲区的引用，下次调用会被覆盖。
        如果需要保留，请调用方自行 .copy()。
        """
        vid_h, vid_w = video_frame.shape[:2]
        video_u8 = np.ascontiguousarray(video_frame[:, :, :3])

        _five_layer_fast_kernel(
            self.bg_f, video_u8,
            self.score_rgb, self.score_mask,
            self.text_rgb, self.text_mask,
            self._out_buf,
            self.bg_brightness,
            self.vid_x, self.vid_y, vid_h, vid_w,
            self.score_h, self.score_w,
            self.text_x, self.text_y, self.text_h, self.text_w,
            self.out_h, self.out_w,
        )
        return self._out_buf
