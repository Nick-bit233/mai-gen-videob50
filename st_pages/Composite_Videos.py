from utils.theme_artifacts import validate_image_style
import streamlit as st
import traceback
import os
import platform
import io
import sys
import html
import contextlib
import threading
import time
import streamlit.components.v1 as components

from datetime import datetime
from utils.PageUtils import load_style_config, open_file_explorer, read_global_config, write_global_config, get_game_type_text
from utils.themes import THEME_COLORS
from utils.PathUtils import get_user_media_dir
from utils.VideoUtils import render_all_video_clips, combine_full_video_direct, combine_full_video_ffmpeg_concat_gl, render_complete_full_video
from db_utils.DatabaseDataHandler import get_database_handler
from utils.diagnostics import begin_report, capture_exception


def show_render_error(exc, message):
    report = capture_exception(exc, '视频生成')
    st.session_state['last_diagnostic_report'] = report.report_id
    st.error(f"{message}: {exc}")
    st.info(f"诊断编号：{report.report_id}。可在“错误报告与硬件检查”下载或手动提交完整日志。")


def _rgba_from_hex(hex_color, alpha=0.2):
    """把主题色转成 CSS rgba，用于描边等半透明效果。"""
    value = (hex_color or "#31333f").lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    try:
        red, green, blue = (int(value[index:index + 2], 16)
                            for index in (0, 2, 4))
    except ValueError:
        red, green, blue = 49, 51, 63
    alpha = max(0.0, min(1.0, float(alpha)))
    return f"rgba({red}, {green}, {blue}, {alpha})"


def _resolve_theme_colors(game_type):
    """优先取当前 session 主题，回退到实际生效的 .streamlit/config.toml。"""
    theme_name = st.session_state.get("theme")
    colors = THEME_COLORS.get(game_type, {}).get(theme_name)
    if colors:
        return dict(colors)
    try:
        import tomllib
        with open(".streamlit/config.toml", "rb") as stream:
            config = tomllib.load(stream)
        theme = config.get("theme")
        if isinstance(theme, dict) and theme:
            return theme
    except Exception:
        pass
    return {}


class _TeeLog(io.TextIOBase):
    """把渲染日志同时写入控制台和内存环形缓冲区。"""

    def __init__(self, original):
        self._original = original
        self._lines = []
        self._buffer = ""
        self._lock = threading.Lock()
        self.version = 0

    def write(self, text):
        if not text:
            return 0
        if self._original is not None:
            try:
                self._original.write(text)
            except Exception:
                pass
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        with self._lock:
            self._buffer += normalized
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                self._lines.append(line[:500])
                if len(self._lines) > 2000:
                    del self._lines[:-2000]
            self.version += 1
        return len(text)

    def flush(self):
        if self._original is not None:
            try:
                self._original.flush()
            except Exception:
                pass

    def tail(self, count=18):
        with self._lock:
            lines = list(self._lines)
            if self._buffer:
                lines.append(self._buffer[:500])
        return lines[-count:]


def _start_log_flusher(refresh_log):
    """每秒把新日志刷到页面，渲染进入拼接/音频阶段时也能看到进度。"""
    stop = threading.Event()

    def loop():
        while not stop.wait(1.0):
            try:
                refresh_log()
            except Exception:
                break

    thread = threading.Thread(target=loop, name="ui-log-flusher", daemon=True)
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx
        add_script_run_ctx(thread)
    except Exception:
        pass
    thread.start()
    return stop, thread

G_config = read_global_config()
G_type = st.session_state.get('game_type', 'maimai')
style_config = load_style_config(game_type=G_type)
db_handler = get_database_handler()

# =============================================================================
# Page layout starts here
# ==============================================================================
st.header("🎥 视频生成")

st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")

st.info("在执行视频生成前，请确保已经完成了4-1和4-2步骤，并且检查所有填写的配置无误。")

# 检查Taichi依赖是否安装
if 'taichi_accel_installed' not in st.session_state:
    st.session_state.taichi_accel_installed = False
    try:
        from utils.TaichiAccel import TAICHI_AVAILABLE
        st.session_state.taichi_accel_installed = TAICHI_AVAILABLE
    except ImportError:
        st.session_state.taichi_accel_installed = False

### Savefile Management - Start ###
username = st.session_state.get("username", None)
archive_name = st.session_state.get("archive_name", None)
archive_id = st.session_state.get("archive_id", None)

if not username:
    st.warning("请先在存档管理页面指定用户名。")
    st.stop()
st.write(f"当前用户名: **{username}**")
archives = db_handler.get_user_save_list(username, game_type=G_type)

with st.expander(f"更换分表存档"):
    if not archives:
        st.warning("未找到任何存档。请先新建或加载存档。")
        st.stop()
    else:
        archive_names = [a['archive_name'] for a in archives]
        try:
            current_archive_index = archive_names.index(st.session_state.get('archive_name'))
        except (ValueError, TypeError):
            current_archive_index = 0
        
        st.markdown("##### 加载本地存档")
        selected_archive_name = st.selectbox(
            "选择存档进行加载",
            archive_names,
            index=current_archive_index
        )
        if st.button("加载此存档（只需要点击一次！）"):

            archive_id = db_handler.load_save_archive(username, selected_archive_name)
            st.session_state.archive_id = archive_id
        
            archive_data = db_handler.load_archive_metadata(username, selected_archive_name)
            if archive_data:
                st.session_state.archive_name = selected_archive_name
                st.success(f"已加载存档 **{selected_archive_name}**")
                st.rerun()
            else:
                st.error("加载存档数据失败。")
if not archive_id:
    st.warning("未找到有效的存档！")
    st.stop()
### Savefile Management - End ###

st.markdown("#### 视频生成设置")

_mode_index = 0 if G_config['ONLY_GENERATE_CLIPS'] else 1
_video_res = G_config['VIDEO_RES']
_video_bitrate = G_config.get('VIDEO_BITRATE', 5000)
_video_fps = G_config.get('VIDEO_FPS', 60)
_trans_enable = G_config['VIDEO_TRANS_ENABLE']
_trans_time = G_config['VIDEO_TRANS_TIME']

options = ["仅生成每个视频片段", "生成完整视频"]
with st.container(border=True):
    mode_str = st.radio("选择视频生成模式", 
            horizontal=True,
            options=options, 
            index=_mode_index)
    
    no_main_clip = st.checkbox("生成视频片段时，跳过全部曲目片段（仅生成开场、结尾）", value=False)
    force_render_clip = st.checkbox("生成视频片段时，强制重新生成全部片段（默认自动更新设置已变化的片段）", value=False)

trans_config_placeholder = st.empty()
with trans_config_placeholder.container(border=True):
    st.write("片段过渡设置（仅对生成完整视频模式有效）")
    trans_enable = st.checkbox("启用片段过渡", value=_trans_enable)
    trans_time = st.number_input("过渡时间", min_value=0.5, max_value=10.0, value=_trans_time, step=0.5,
                                 disabled=not trans_enable)
vcof_col1, vcof_col2 = st.columns(2)
with vcof_col1:
    with st.container(border=True):
        st.write("视频分辨率")
        col1, col2 = st.columns(2)
        v_res_width = col1.number_input("视频宽度", min_value=360, max_value=4096, value=_video_res[0])
        v_res_height = col2.number_input("视频高度", min_value=360, max_value=4096, value=_video_res[1])
with vcof_col2:
    with st.container(border=True):
        st.write("视频比特率(kbps)")  
        v_bitrate = st.number_input("视频比特率", min_value=1000, max_value=10000, value=_video_bitrate)

with st.container(border=True):
    st.write("视频帧率")
    _fps_options = [30, 60]
    _fps_index = _fps_options.index(_video_fps) if _video_fps in _fps_options else 1
    v_fps = st.radio(
        "输出帧率 (fps)",
        _fps_options,
        index=_fps_index,
        horizontal=True,
        format_func=lambda value: f"{value} fps" + ("（更快，推荐）" if value == 30 else "（更流畅）"),
        help="30fps 的合成帧数约为 60fps 的一半，生成速度约快一倍；60fps 画面更流畅。",
    )

_gpu_accel = G_config.get('USE_GPU_ACCEL', False)
with st.container(border=True):
    st.markdown("##### 🚀 GPU 加速渲染（实验性）")
    gpu_accel = st.checkbox(
        "启用 Taichi GPU 加速",
        value=_gpu_accel and st.session_state.taichi_accel_installed,
        disabled=not st.session_state.taichi_accel_installed,
        help="使用 Taichi GPU 合成 + FFmpeg 硬件编码加速视频渲染。如果无法勾选，请在主页检查是否安装Taichi加速组件。"
             "启用后将自动选择可用 GPU 后端（CUDA/Vulkan/Metal）和硬件编码器（NVENC/VideoToolbox 等）。"
    )
    gpu_accel = gpu_accel and st.session_state.taichi_accel_installed
    backend_options = ['auto', 'metal', 'vulkan'] if platform.system() == 'Darwin' else ['auto', 'cuda', 'vulkan']
    saved_backend = G_config.get('TAICHI_BACKEND', 'auto')
    taichi_backend = st.selectbox(
        'GPU 后端', backend_options,
        index=backend_options.index(saved_backend) if saved_backend in backend_options else 0,
        format_func=lambda name: '自动选择（推荐）' if name == 'auto' else name.upper(),
        disabled=not gpu_accel,
        help='Linux 会先测试实际合成能力。CUDA 不稳定时可以选择 Vulkan；切换已启用的后端需要重新启动应用。',
    )
    if gpu_accel:
        from utils.TaichiAccel import get_backend_name
        active_backend = get_backend_name()
        if active_backend:
            st.caption(f'当前已启用：{active_backend.upper()}')
            if taichi_backend not in ('auto', active_backend):
                st.warning('更换 GPU 后端后，请重新启动应用再生成视频。')

with st.expander("⚙️ 高级渲染设置"):
    st.caption("CPU 路线（未启用 GPU 加速时生效）")
    col_cpu1, col_cpu2 = st.columns(2)
    cpu_bands = col_cpu1.number_input(
        "CPU 合成分带线程", min_value=1, max_value=16,
        value=int(G_config.get('CPU_BANDS', 8)), disabled=gpu_accel,
        help="CPU 合成器把每帧按水平带并行处理；默认 8，通常 8 已接近内存带宽上限。",
    )
    cpu_encoder_threads = col_cpu2.number_input(
        "libx264 编码线程", min_value=1, max_value=16,
        value=int(G_config.get('CPU_ENCODER_THREADS', 8)), disabled=gpu_accel,
        help="每个片段交给 libx264 的线程数；与合成分带线程共享 CPU。",
    )
    col_cpu3, col_cpu4 = st.columns(2)
    cpu_clip_workers = col_cpu3.number_input(
        "同时渲染片段数", min_value=1, max_value=8,
        value=int(G_config.get('CPU_CLIP_WORKERS', 1)), disabled=gpu_accel,
        help="CPU 合成为内存带宽瓶颈，通常 1 最快；可尝试 3，4 及以上往往更慢。",
    )
    preset_options = ["ultrafast", "superfast", "veryfast", "faster", "fast"]
    saved_preset = G_config.get('CPU_PRESET', 'veryfast')
    cpu_preset = col_cpu4.selectbox(
        "x264 preset", preset_options,
        index=preset_options.index(saved_preset) if saved_preset in preset_options else 2,
        disabled=gpu_accel,
        help="veryfast 是速度/体积的折中；superfast/ultrafast 更快但文件更大。",
    )
    # 兼容性开关不再显示在页面上，但仍从 global_config.yaml 读取，
    # 便于需要时手动回退，且不会在保存时被覆盖成默认值。
    legacy_cpu = bool(G_config.get('LEGACY_CPU', False))
    sync_writer = bool(G_config.get('SYNC_WRITER', False))
    gpu_legacy_layers = bool(G_config.get('GPU_LEGACY_LAYERS', False))
    gpu_legacy_info = bool(G_config.get('GPU_LEGACY_INFO', False))

    st.divider()
    st.caption("渲染流水线")
    col_pipe1, col_pipe2 = st.columns(2)
    source_fps_composite = col_pipe1.checkbox(
        "按源视频帧率合成",
        value=bool(G_config.get('SOURCE_FPS_COMPOSITE', True)),
        help="60fps 输出且素材是 30fps 时，按 30fps 合成再由 FFmpeg 补帧到 60fps，减少一半合成量；最终输出仍是 60fps。",
    )
    decode_prefetch = col_pipe2.checkbox(
        "解码预取线程",
        value=bool(G_config.get('DECODE_PREFETCH', True)),
        help="后台线程提前解码下一帧，与 GPU/CPU 合成重叠，减少解码等待。",
    )

    st.divider()
    st.caption("转场拼接")
    _stage_workers = int(G_config.get('STEP2_WORKERS', 2))
    col_step2a, col_step2b, col_step2c = st.columns(3)
    step2_body_workers = col_step2a.number_input(
        "主体并行数", min_value=1, max_value=8,
        value=int(G_config.get('STEP2_BODY_WORKERS', _stage_workers)),
        help="关键帧流拷贝/主体重编码的并行数；默认 2。",
    )
    step2_transition_workers = col_step2b.number_input(
        "转场并行数", min_value=1, max_value=8,
        value=int(G_config.get('STEP2_TRANSITION_WORKERS', 4)),
        help="同时运行的转场批次数量；默认 4。与“每次转场批量”相乘不要超过 GPU 的 NVENC 并发上限。",
    )
    transition_batch = col_step2c.number_input(
        "每次转场批量", min_value=1, max_value=8,
        value=int(G_config.get('TRANSITION_BATCH', 1)),
        help="一个 FFmpeg 进程同时渲染几个转场。批量>1 可减少进程启动次数，但在消费级 GPU 上可能降低并行吞吐；默认 1。",
    )

v_mode_index = options.index(mode_str)
v_bitrate_kbps = f"{v_bitrate}k"

user_media_paths = get_user_media_dir(username, game_type=G_type)
video_output_path = user_media_paths['output_video_dir']
if not os.path.exists(video_output_path):
    os.makedirs(video_output_path)

# 读取存档的 video_config，只读，用于生成视频
try:
    main_configs, intro_configs, ending_configs = db_handler.load_full_config_for_composite_video(
                                                                username=username,
                                                                archive_name=archive_name
                                                            )
except Exception as e:
    st.error(f"读取存档配置失败: {e}")
    with st.expander("错误详情"):
        st.error(traceback.format_exc())
    st.stop()

if not main_configs:
    st.error("❌ 未找到主视频配置，请检查4-1步骤是否正常保存！")

if not intro_configs or not ending_configs:
    st.error("❌ 未找到片头或片尾配置，请检查4-2步骤是否正常保存！")

def save_video_render_config(include_main=True):
    if include_main:
        try:
            for config in main_configs:
                validate_image_style(config.get('main_image'), G_type, style_config, require_snapshot=True)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
    # 保存配置
    G_config['ONLY_GENERATE_CLIPS'] = v_mode_index == 0
    G_config['VIDEO_RES'] = (v_res_width, v_res_height)
    G_config['VIDEO_BITRATE'] = v_bitrate
    G_config['VIDEO_FPS'] = v_fps
    G_config['VIDEO_TRANS_ENABLE'] = trans_enable
    G_config['VIDEO_TRANS_TIME'] = trans_time
    G_config['USE_GPU_ACCEL'] = gpu_accel
    G_config['TAICHI_BACKEND'] = taichi_backend
    G_config['CPU_BANDS'] = int(cpu_bands)
    G_config['CPU_ENCODER_THREADS'] = int(cpu_encoder_threads)
    G_config['CPU_CLIP_WORKERS'] = int(cpu_clip_workers)
    G_config['CPU_PRESET'] = cpu_preset
    G_config['LEGACY_CPU'] = bool(legacy_cpu)
    G_config['STEP2_WORKERS'] = int(step2_body_workers)
    G_config['STEP2_BODY_WORKERS'] = int(step2_body_workers)
    G_config['STEP2_TRANSITION_WORKERS'] = int(step2_transition_workers)
    G_config['TRANSITION_BATCH'] = int(transition_batch)
    G_config['SOURCE_FPS_COMPOSITE'] = bool(source_fps_composite)
    G_config['DECODE_PREFETCH'] = bool(decode_prefetch)
    G_config['SYNC_WRITER'] = bool(sync_writer)
    G_config['GPU_LEGACY_LAYERS'] = bool(gpu_legacy_layers)
    G_config['GPU_LEGACY_INFO'] = bool(gpu_legacy_info)
    G_config['SHOW_RENDER_LOG'] = bool(show_render_log)
    write_global_config(G_config)

    # 渲染函数通过环境变量读取这些高级开关；在点击生成时同步到当前进程。
    os.environ['MAIGEN_CPU_BANDS'] = str(int(cpu_bands))
    os.environ['MAIGEN_CPU_ENCODER_THREADS'] = str(int(cpu_encoder_threads))
    os.environ['MAIGEN_CPU_CLIP_WORKERS'] = str(int(cpu_clip_workers))
    os.environ['MAIGEN_CPU_PRESET'] = str(cpu_preset)
    os.environ['MAIGEN_STEP2_WORKERS'] = str(int(step2_body_workers))
    os.environ['MAIGEN_STEP2_BODY_WORKERS'] = str(int(step2_body_workers))
    os.environ['MAIGEN_STEP2_TRANSITION_WORKERS'] = str(int(step2_transition_workers))
    os.environ['MAIGEN_TRANSITION_BATCH'] = str(int(transition_batch))
    os.environ['MAIGEN_SOURCE_FPS_COMPOSITE'] = (
        '1' if source_fps_composite else '0')
    os.environ['MAIGEN_DECODE_PREFETCH'] = '1' if decode_prefetch else '0'
    for key, enabled in (
        ('MAIGEN_LEGACY_CPU', legacy_cpu),
        ('MAIGEN_SYNC_WRITER', sync_writer),
        ('MAIGEN_LEGACY_LAYERS', gpu_legacy_layers),
        ('MAIGEN_LEGACY_INFO', gpu_legacy_info),
    ):
        if enabled:
            os.environ[key] = '1'
        else:
            os.environ.pop(key, None)
    st.toast("配置已保存！")

if "show_render_log" not in st.session_state:
    st.session_state.show_render_log = bool(
        G_config.get('SHOW_RENDER_LOG', True))
show_render_log = st.checkbox(
    "显示运行日志",
    key="show_render_log",
    help="在生成框内显示实时运行日志；关闭后只保留进度条和预计时间。",
)

if st.button("开始生成视频", use_container_width=True, type="primary"):
    report = begin_report('视频生成', settings={'game_type': G_type, 'resolution': [v_res_width, v_res_height],
                          'fps': v_fps, 'gpu': gpu_accel, 'taichi_backend': taichi_backend})
    st.session_state['last_diagnostic_report'] = report.report_id
    save_video_render_config(include_main=not (v_mode_index == 0 and no_main_clip))
    video_res = (v_res_width, v_res_height)

    # 前置检查 FFmpeg 版本
    try:
        from utils.AccelRenderer import check_ffmpeg_version
        check_ffmpeg_version()
    except RuntimeError as e:
        st.error(f"❌ FFmpeg 版本检查失败: {e}")
        st.stop()

    placeholder = st.empty()

    # 进度条 + 实时日志。进度按片段合成/转场/音频三阶段加权。
    def _make_st_progress(container, log_stream, stage_weights, show_log=True):
        progress_bar = container.progress(0, text="准备渲染...")
        status_text = container.empty()
        theme_colors = _resolve_theme_colors(G_type)
        # 复刻 st.container(border=True) 的外观：
        # 页面整体背景 + 主题文本色 + 文本色半透明描边 + 圆角 + 内边距。
        page_bg = theme_colors.get("backgroundColor") or "#ffffff"
        log_bg = page_bg
        text_color = theme_colors.get("textColor") or "#31333f"
        log_border = _rgba_from_hex(text_color, 0.2)
        if show_log:
            st.caption("运行日志（可上下滚动查看）")
            log_slot = container.empty()
        else:
            log_slot = None
        log_lock = threading.Lock()
        update_lock = threading.Lock()
        started_at = time.monotonic()
        # 每次生成使用独立的滚动状态，避免上一次运行的历史滚动位置影响新任务。
        log_scroll_key = f"maigen-log-scroll-{time.time_ns()}"

        stage_order = ("render", "transition", "audio")
        weights = {name: max(0, int(stage_weights.get(name, 0)))
                   for name in stage_order}
        total_weight = sum(weights.values()) or 1

        state = {
            "stage": "render",
            "fraction": 0.0,
            "text": "准备渲染...",
            "overall": 0.0,
            "skipped": 0.0,
            "done": None,
            "total": None,
            "substage": None,
        }
        last_log_version = [-1]

        def fmt_time(seconds):
            seconds = int(max(0, seconds))
            hours, remainder = divmod(seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            if hours:
                return f"{hours}:{minutes:02d}:{secs:02d}"
            return f"{minutes:02d}:{secs:02d}"

        def refresh_log(force=False):
            if log_slot is None:
                return
            version = log_stream.version
            if not force and version == last_log_version[0]:
                return
            last_log_version[0] = version
            with log_lock:
                lines = log_stream.tail(2000)
                log_text = html.escape(
                    "\n".join(lines) if lines else "等待日志...")
                log_html = f"""
<!doctype html>
<html><head><meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; background: {page_bg}; }}
  #log {{
    height: 260px; overflow-y: auto; white-space: pre-wrap;
    font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
    font-size: 14px; line-height: 1.5;
    color: {text_color}; background: {log_bg};
    border: 1px solid {log_border};
    border-radius: 0.5rem;
    padding: 1rem; box-sizing: border-box;
  }}
  #log::-webkit-scrollbar {{ width: 10px; }}
  #log::-webkit-scrollbar-thumb {{
    background: rgba(0, 0, 0, 0.25); border-radius: 5px;
  }}
</style></head>
<body>
<div id="log">{log_text}</div>
<script>
(function() {{
  const el = document.getElementById('log');
  const key = '{log_scroll_key}';
  let state = {{atBottom: true, scrollTop: 0}};
  try {{
    const raw = localStorage.getItem(key);
    if (raw) state = JSON.parse(raw);
  }} catch (e) {{}}
  el.scrollTop = state.atBottom ? el.scrollHeight : state.scrollTop;
  let initialized = false;
  el.addEventListener('scroll', function() {{
    if (!initialized) return;
    const atBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 24;
    try {{
      localStorage.setItem(key, JSON.stringify({{
        atBottom: atBottom, scrollTop: el.scrollTop
      }}));
    }} catch (e) {{}}
  }});
  initialized = true;
}})();
</script>
</body></html>
"""
                with log_slot:
                    components.html(log_html, height=260, scrolling=False)

        def stage_offset(stage_name):
            offset = 0
            for name in stage_order:
                if name == stage_name:
                    break
                offset += weights[name]
            return offset

        def refresh_ui():
            overall = state["overall"]
            elapsed = time.monotonic() - started_at
            if overall >= 0.999:
                eta_text = "00:00"
            elif overall > 0.02:
                # 剩余时间 = 剩余进度 × 已用时间 / 实际已推进进度。
                # 跳过/复用片段会瞬间推进进度但不消耗时间，需要从分母扣除，
                # 否则会严重低估剩余时间（甚至一直显示 00:00）。
                effective = max(
                    overall - state["skipped"],
                    overall * 0.01,
                    1e-3,
                )
                remaining = max(0.0, (1.0 - overall) * elapsed / effective)
                eta_text = fmt_time(remaining)
            else:
                eta_text = "--:--"
            stage_label = {
                "render": "片段合成",
                "transition": "转场拼接",
                "audio": "音频均衡",
            }.get(state["stage"], state["stage"])
            if state["stage"] == "transition" and state["substage"]:
                stage_label = f"转场拼接·{state['substage']}"
            count_text = ""
            if state["done"] is not None and state["total"] is not None:
                count_text = f" ({int(state['done'])}/{int(state['total'])})"
            progress_bar.progress(
                overall,
                text=f"{int(round(overall * 100))}% | 已用 {fmt_time(elapsed)} | "
                     f"预计剩余 {eta_text} | {stage_label}{count_text}")
            if state["text"]:
                status_text.caption(state["text"])

        def update(stage, fraction, text=None, skipped=False,
                   done=None, total=None, substage=None):
            fraction = max(0.0, min(1.0, float(fraction)))
            weight = weights.get(stage, 0)
            overall = (stage_offset(stage) + weight * fraction) / total_weight
            overall = max(0.0, min(1.0, overall))
            with update_lock:
                delta = max(0.0, overall - state["overall"])
                if skipped and delta > 0:
                    state["skipped"] += delta
                if stage != state["stage"]:
                    state["done"] = None
                    state["total"] = None
                    state["substage"] = None
                state["stage"] = stage
                state["fraction"] = fraction
                state["overall"] = overall
                if done is not None:
                    state["done"] = int(done)
                if total is not None:
                    state["total"] = int(total)
                if substage is not None:
                    state["substage"] = substage
                if text:
                    state["text"] = text
                refresh_ui()
            refresh_log()

        def stage_update(stage, fraction, text=None, done=None, total=None,
                         substage=None):
            update(stage, fraction, text, skipped=False, done=done,
                   total=total, substage=substage)

        def tick(force_log=False):
            with update_lock:
                refresh_ui()
            refresh_log(force=force_log)

        def clip_callback(clip_idx, total_clips, frame, total_frames, clip_name):
            total = max(1, int(total_clips or 1))
            index = max(0, min(total - 1, int(clip_idx or 0)))
            frame_fraction = (float(frame) / float(total_frames)
                              if total_frames else 1.0)
            frame_fraction = max(0.0, min(1.0, frame_fraction))
            fraction = (index + frame_fraction) / total
            # 复用片段时 render 代码用 frame=1/total_frames=1 上报完成，
            # 这部分进度不计入实际耗时。
            is_skipped = bool(total_frames) and int(total_frames) == 1
            completed = index + (1 if frame_fraction >= 1.0 else 0)
            update("render", fraction, f"正在渲染: {clip_name}",
                   skipped=is_skipped, done=completed, total=total)

        refresh_log()
        return clip_callback, stage_update, tick

    if v_mode_index == 0:
        stage_weights = {"render": 100}
    elif not trans_enable:
        stage_weights = {"render": 95, "transition": 2, "audio": 3}
    elif gpu_accel:
        stage_weights = ({"render": 78, "transition": 19, "audio": 3}
                         if v_fps >= 60 else
                         {"render": 69, "transition": 26, "audio": 5})
    else:
        stage_weights = ({"render": 89, "transition": 9, "audio": 2}
                         if v_fps >= 60 else
                         {"render": 83, "transition": 15, "audio": 2})

    if v_mode_index == 0:
        try:
            with placeholder.container(
                    border=True,
                    height=(560 if show_render_log else "content")):
                st.warning("生成过程中请不要手动跳转到其他页面，或刷新本页面，否则可能导致生成失败！")
                with st.spinner("正在生成所有视频片段……"):
                    log_stream = _TeeLog(sys.stdout)
                    progress_cb, stage_cb, tick = _make_st_progress(
                        st.container(), log_stream, stage_weights,
                        show_log=show_render_log)
                    stop_flusher, flusher = _start_log_flusher(tick)
                    try:
                        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
                            render_all_video_clips(
                                game_type=G_type,
                                style_config=style_config,
                                main_configs=main_configs if not no_main_clip else [],
                                video_output_path=video_output_path,
                                video_res=video_res,
                                video_bitrate=v_bitrate_kbps,
                                video_fps=v_fps,
                                intro_configs=intro_configs,
                                ending_configs=ending_configs,
                                trans_time=trans_time,
                                force_render=force_render_clip,
                                use_gpu_accel=gpu_accel,
                                taichi_backend=taichi_backend,
                                progress_callback=progress_cb
                            )
                        tick(force_log=True)
                    finally:
                        stop_flusher.set()
                        flusher.join(timeout=2)
            st.success("视频片段生成结束！点击下方按钮打开视频所在文件夹")
        except Exception as e:
            show_render_error(e, '视频片段生成失败')

    else:
        try:
            with placeholder.container(
                    border=True,
                    height=(560 if show_render_log else "content")):
                st.warning("生成过程中请不要手动跳转到其他页面，或刷新本页面，否则可能导致生成失败！")
                with st.spinner("正在生成完整视频……"):
                    log_stream = _TeeLog(sys.stdout)
                    progress_cb, stage_cb, tick = _make_st_progress(
                        st.container(), log_stream, stage_weights,
                        show_log=show_render_log)
                    stop_flusher, flusher = _start_log_flusher(tick)
                    try:
                        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
                            output_info = render_complete_full_video(
                                username=username,
                                game_type=G_type,
                                main_configs=main_configs,
                                intro_configs=intro_configs,
                                ending_configs=ending_configs,
                                style_config=style_config,
                                video_output_path=video_output_path,
                                video_res=video_res,
                                video_bitrate=v_bitrate_kbps,
                                video_fps=v_fps,
                                video_trans_enable=trans_enable,
                                video_trans_time=trans_time,
                                full_last_clip=False,
                                use_gpu_accel=gpu_accel,
                                taichi_backend=taichi_backend,
                                progress_callback=progress_cb,
                                force_render=force_render_clip,
                                stage_callback=stage_cb,
                            )
                        if output_info['status'] != 'success':
                            raise RuntimeError(output_info['info'])
                        tick(force_log=True)
                        st.write(output_info['info'])
                    finally:
                        stop_flusher.set()
                        flusher.join(timeout=2)
            st.success("完整视频生成结束！点击下方按钮打开视频所在文件夹")
        except Exception as e:
            show_render_error(e, '完整视频生成失败')

abs_path = os.path.abspath(video_output_path)
if st.button("打开视频输出文件夹"):
    open_file_explorer(abs_path)
st.markdown(f">💡 如果打开文件夹失败，请在此路径中寻找生成的视频：{abs_path}")

# 添加分割线
st.divider()

with st.expander("展开其他视频生成方案"):
    st.warning("⚠️ 请注意，此区域的功能未经充分测试，不保证生成视频的效果或稳定性，请谨慎使用。")
    with st.container(border=True):
        st.write("【低内存模式】生成完整视频")
        st.info("GPU 加速时将使用低内存 xfade 转场拼接；CPU 路线仍使用直接拼接视频片段的简单模式。")
        if st.button("直接拼接方式生成完整视频"):
            report = begin_report('低内存视频生成')
            st.session_state['last_diagnostic_report'] = report.report_id
            save_video_render_config()
            video_res = (v_res_width, v_res_height)
            try:
                from utils.AccelRenderer import check_ffmpeg_version
                check_ffmpeg_version()
            except RuntimeError as e:
                st.error(f"❌ FFmpeg 版本检查失败: {e}")
                st.stop()
            if gpu_accel:
                # GPU 低内存模式：未烘焙片段 + transition island xfade/concat
                try:
                    with st.spinner("正在使用GPU低内存模式生成完整视频……"):
                        log_stream = _TeeLog(sys.stdout)
                        lowmem_weights = (
                            {"render": 78, "transition": 19, "audio": 3}
                            if v_fps >= 60 else
                            {"render": 69, "transition": 26, "audio": 5})
                        progress_cb, stage_cb, tick = _make_st_progress(
                            st.container(), log_stream, lowmem_weights,
                            show_log=show_render_log)
                        stop_flusher, flusher = _start_log_flusher(tick)
                        try:
                            with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
                                output_info = render_complete_full_video(
                                    username=username,
                                    game_type=G_type,
                                    main_configs=main_configs,
                                    intro_configs=intro_configs,
                                    ending_configs=ending_configs,
                                    style_config=style_config,
                                    video_output_path=video_output_path,
                                    video_res=video_res,
                                    video_bitrate=v_bitrate_kbps,
                                    video_fps=v_fps,
                                    video_trans_enable=trans_enable,
                                    video_trans_time=trans_time,
                                    full_last_clip=False,
                                    use_gpu_accel=True,
                                    taichi_backend=taichi_backend,
                                    progress_callback=progress_cb,
                                    stage_callback=stage_cb,
                                    force_render=force_render_clip
                                )
                            if output_info['status'] != 'success':
                                raise RuntimeError(output_info['info'])
                            tick(force_log=True)
                            st.write(output_info['info'])
                        finally:
                            stop_flusher.set()
                            flusher.join(timeout=2)
                    st.success("GPU低内存模式生成完成！点击上方按钮打开文件夹查看视频")
                except Exception as e:
                    show_render_error(e, 'GPU低内存模式生成失败')
            else:
                # CPU快速模式：原有逻辑
                with st.spinner("正在生成所有视频片段……"):
                    render_all_video_clips(
                        game_type=G_type,
                        style_config=style_config,
                        main_configs=main_configs,
                        video_output_path=video_output_path, 
                        video_res=video_res, 
                        video_bitrate=v_bitrate_kbps,
                        video_fps=v_fps,
                        intro_configs=intro_configs,
                        ending_configs=ending_configs,
                        auto_add_transition=trans_enable, 
                        trans_time=trans_time,
                        force_render=force_render_clip
                    )
                    st.info("已启动批量视频片段生成，请在控制台窗口查看进度……")
                with st.spinner("正在拼接视频……"):
                    combine_full_video_direct(video_output_path, video_fps=v_fps)
                st.success("所有任务已退出，请从上方按钮打开文件夹查看视频生成结果")

    with st.container(border=True):
        st.write("【更多过渡效果】使用ffmpeg concat生成视频，允许自定义片段过渡效果")
        st.warning("此模式要求先在本地环境中安装ffmpeg concat插件，请务必查看使用说明后进行！此模式不支持GPU加速！")
        @st.dialog("ffmpeg-concat使用说明")
        def delete_video_config_dialog(file):
            ### 展示markdown文本
            # read markdown file
            with open(file, "r", encoding="utf-8") as f:
                doc = f.read()
            st.markdown(doc)

        if st.button("查看ffmpeg concat使用说明", key=f"open_ffmpeg_concat_doc"):
            delete_video_config_dialog("./docs/ffmpeg_concat_Guide.md")

        with st.container(border=True):
            st.write("片段过渡效果")
            trans_name = st.selectbox("选择过渡效果", options=["fade", "circleOpen", "crossWarp", "directionalWarp", "directionalWipe", "crossZoom", "dreamy", "squaresWire"], index=0)
            if st.button("使用ffmpeg concat生成视频"):
                save_video_render_config()
                video_res = (v_res_width, v_res_height)
                with st.spinner("正在生成所有视频片段……"):
                    render_all_video_clips(
                        game_type=G_type,
                        style_config=style_config,
                        main_configs=main_configs,
                        video_output_path=video_output_path, 
                        video_res=video_res, 
                        video_bitrate=v_bitrate_kbps,
                        video_fps=v_fps,
                        intro_configs=intro_configs,
                        ending_configs=ending_configs,
                        auto_add_transition=trans_enable,
                        trans_time=trans_time,
                        force_render=force_render_clip
                    )
                    st.info("已启动批量视频片段生成，请在控制台窗口查看进度……")
                with st.spinner("正在拼接视频……"):
                    combine_full_video_ffmpeg_concat_gl(video_output_path, trans_name, trans_time)
                    st.info("已启动视频拼接任务，请在控制台窗口查看进度……")
                st.success("所有任务已退出，请从上方按钮打开文件夹查看视频生成结果")
