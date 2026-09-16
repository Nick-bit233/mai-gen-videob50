# v1.2.6 修复与 runtime 验收

## 改动

- #123：固定 OpenCV 4.14.0.94、NumPy 2.2.6、MoviePy 2.2.1；GPU 可选依赖固定 Taichi 1.7.4。
- 保留 Taichi GPU 片段合成，增加自动/CUDA/Vulkan 选择。Linux 在独立子进程运行真实 uint8 合成内核，单次探测最多 45 秒，失败时继续尝试其他 GPU 后端。Windows 默认后端顺序不变。
- 已初始化的后端拒绝热切换，并串行化并发初始化请求；CUDA 的初始化、合成与退出清理在同一个持久线程完成。
- 首帧实际解码检查、重复帧缓存、顺序读取和 seek 状态一致性；正常 EOF 与解码失败分别处理。
- 按源时间读取片头/片尾背景，避免不同帧率下播放速度错误。
- 片段在临时文件中编码，成功后替换成品；失败清理进程和临时文件，保留旧成品；页面不再将 error 结果显示为成功。
- #124：舞萌和中二成绩图的 `Playcount` 两处引用均修正为 `PlayCount`。
- 拼接和音频均衡化函数保持原实现，硬件编码失败继续回退 libx264。

## 测试方法

```text
python -m unittest discover -s tests -p test_runtime_regressions.py -v
python scripts/verify_runtime.py --output <独立输出目录> --backend auto --ffmpeg <ffmpeg完整路径>
python scripts/verify_runtime.py --output <另一个输出目录> --backend vulkan --ffmpeg <ffmpeg完整路径>
```

GPU 后端测试需分别在新进程中运行。验收脚本使用合成 H.264/AV1 素材、真实图片资源、动态背景、片头、片尾和交叉转场，并故障注入验证旧成品保护。输出包含 verification.json 和预览图，不接触真实用户存档。

页面测试使用 `scripts/verify_runtime_ui.py`，只允许在带 `.runtime-acceptance-workspace` 标记的临时应用副本中运行。它建立合成存档，验证首页版本和依赖、后端配置保存，以及错误结果不会被显示为成功。页面测试中的渲染失败由 mock 注入，真实 GPU 渲染由前述独立验收覆盖。

## 已完成的代码验收

- Windows 11 / RTX 4070 Laptop：14 项单元测试、CUDA 完整 1080p60 视频、CPU 完整视频通过。
- DSW Ubuntu 24.04 / RTX 4090：14 项单元测试、自动选择 CUDA 和显式 Vulkan 完整 1080p60 视频通过。
- 两端舞萌和中二的游玩次数图片均实际生成并与无游玩次数图片比较。
- DSW NVENC 实测不可用，按原流程实际尝试后成功回退软件编码。
- 测试成片含 315 帧、5.25 秒视频；可完整解码。GPU 路线原有 AAC 音轨尾部为 5.482 秒、视频起始时间约 0.021 秒。使用 main 原版拼接和 loudnorm 对相同片段重做后得到完全相同的时长和时间戳。本版本保留此既有行为，不将短样本尾部差异伪称为新增修复或主观音画同步验收。

## Windows runtime 构建

使用完整 Python 3.12 构建，最终包内为独立 Python 3.12.10 embedded（python.org 3.12 最后一个 Windows 嵌入式发行版），用户无需安装系统 Python。Windows wheel 约束位于 `scripts/runtime-constraints-win-py312.txt`，包含已验证环境的版本组合；全部实际安装版本写入包内 `runtime-installed.txt`。

```text
python scripts/build_runtime.py --stage-only --ffmpeg-dir <FFmpeg-7.1-bin目录> --ffmpeg-license <对应LICENSE文件>
```

构建器只写入独立 staging，拒绝覆盖任意已有目录。已标记的本版本 staging 可用 `--resume` 继续；可用 `--index-url` 指定包镜像。先用完整 Python 生成 wheel，再离线安装到 embedded Python，避免其隔离路径破坏源包构建。

完成 staging 的实际验收后，使用 `--archive-only` 生成 ZIP。ZIP 根目录直接包含 `runtime/`、`ffmpeg.exe`、`ffprobe.exe`、`start.bat`、依赖清单和许可信息。升级时先改名留存旧 runtime 文件夹，再把 ZIP 全部内容解压到 v1.2.6 应用目录，避免混用旧 DLL。

## ZIP 解压验收结果

交付文件：`dist/runtime_v1.2.6_windows_x64.zip`，402,772,314 字节（约 403 MB）。

ZIP 已实际解压到带空格的独立路径；测试进程清空 PYTHONPATH、禁用用户 site-packages，并从 PATH 中移除系统 Python/FFmpeg，只保留包内程序和 Windows 系统目录。

- 包内 Python 3.12.10 的 `pip check`、全部关键依赖导入通过。
- 包内解释器执行 14 项回归测试通过，包括并发初始化不会重置已启用后端。
- 首页显示 v1.2.6、识别包内 Taichi；后端选择/保存、错误结果不显示成功等页面检查通过。
- CUDA 和 Vulkan 完整 1080p60 合成均通过；CPU 完整 640×360/60fps 合成通过。每次包含 AV1/H.264 主视频、AV1 动态背景、片头片尾、两种成绩图与失败保护。
- 包内 `start.bat` 在带空格路径启动 Streamlit 成功，回环地址健康检查通过，随后关闭测试进程。
- 关键组合为 Taichi 1.7.4、OpenCV 4.14.0.94、NumPy 2.2.6、MoviePy 2.2.1、Streamlit 1.55.0、FFmpeg/FFprobe 7.1。完整依赖版本在 ZIP 内 `runtime-installed.txt`。

本机详细证据位于 `test_output/issue123/runtime126-bundled-*.log`、`test_output/release126-bundled-*/verification.json`；Linux 证据取回至 `test_output/release126-evidence/`。

## 验收边界

- RTX 5060 / Blackwell 的原报告 CUDA 卡死未获同型号实机验证；新增探测和手动 Vulkan 选择提供了受控替代路径。
- 没有替代 Debian 12 Docker、AMD/Intel GPU 或 macOS 的实机验收。
- 未执行完整真实 B50 长视频、实际 Bilibili/YouTube 登录下载或全部页面功能；高级 ffmpeg-concat Node 插件仍单独安装。
