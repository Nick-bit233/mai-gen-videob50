## 修复 mai-gen-videob50 的三个问题

### 1. NVENC 检测分辨率问题
**问题**：`detect_hw_encoder()` 使用 64×64 分辨率探测编码器，但 RTX 3060 的最低要求是 256×256，导致在部分驱动版本下误判为不可用。

**修复**：将探测分辨率从 `64x64` 改为 `256x256`，同时将时长从 0.04s 改为 0.1s、帧率从 25 改为 30，使其符合主流 GPU 的最低要求。

### 2. 中文路径支持
**问题**：Windows 路径中包含中文时，`cv2.imread()` 无法正确读取文件，导致背景图片加载失败。

**修复**：将 `_prepare_bg_frame()` 和 `_load_image_rgb()` 中的 `cv2.imread(path)` 替换为：
```python
with open(path, 'rb') as f:
    img_array = np.frombuffer(f.read(), dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
```
通过二进制读取 + `cv2.imdecode` 解决中文路径问题。

### 3. 60fps 输出选项
**问题**：输出帧率硬编码为 30fps，无法满足高帧率需求。

**修复**：
- `Composite_Videos.py` 添加帧率滑块（24-120，默认 60），配置持久化到 `VIDEO_FPS`
- `render_all_video_clips()` 和 `render_complete_full_video()` 新增 `video_fps` 参数
- `render_all_clips_accel()` 的 `fps` 参数默认值从 30 改为 60
- 所有 `write_videofile` 调用改为使用 `video_fps`

**影响范围**：
- `utils/AccelRenderer.py`：NVENC 检测分辨率 + 中文路径 2 处
- `st_pages/Composite_Videos.py`：UI 滑块 + 配置读写
- `utils/VideoUtils.py`：FPS 参数透传（`render_all_video_clips`、`render_complete_full_video`、CPU 渲染路径、`_combine_with_xfade` 滤镜链）

---

关联 Issue：无（自行发现并修复的问题，非 Issue 反馈）