# Issue #123 Linux Taichi 实验评估

本文记录正式修复前的实验。1.2.6 的实现、打包与最终验收见 [发布验收记录](release_v1.2.6.md)。

日期：2026-09-16。实验分支：`codex/linux-taichi-issue123`。

本轮是修复方案的实机评估。应用源码、默认配置、原 requirements.txt 和拼接实现均未改动；候选依赖只安装在隔离目录。没有操作 DSW 上已有 Worker 的代码、虚拟环境、配置或服务。

## 结论与推荐方案

保留 Linux 上的 Taichi 片段合成。当前已经复现的 AV1 黑屏问题可通过 OpenCV 4.14.0.94 修复，完全不需要改成 CPU 合成片段。不要仅设置 `opencv-python<5`，旧的 4.x wheel 同样可能缺少 Linux AV1 解码能力。

推荐将正式改动分成以下几项：

1. 发布时固定经过验证的 OpenCV 4.14.0.94；Taichi GPU 可选组件使用已验证的 1.7.4。OpenCV 4.14 要求 Python 3.9+ 环境的 NumPy >= 2，需在安装说明和运行包构建中明确。Windows 候选组合已通过本报告所列验收，暂不需要两套分叉依赖包。现有 Windows 用户无需为本次实验升级，正式发布前仍需重建运行包验收。
2. 在视频读取边界实际检查首帧和所需时间点。不能只检查 `VideoCapture.isOpened()`；正常时间范围内解码失败应报错并释放读取器/编码进程，不能填黑帧后返回成功。区分正常 EOF、超出素材时长与损坏/不支持的素材。独立验证主视频、动态背景和片头背景。
3. 给读帧器增加最后一帧缓存，重复请求同一源帧时复用已解码数组，避免 30fps 素材输出 60fps 时每两帧就向后 seek。正式实现需覆盖 `get_frame`、`read_next`、`seek_to` 的位置及缓存失效语义，禁止缓存失败结果。两端真实片段的缓存实验已验证输出像素一致，并明显减少耗时。
4. Taichi 增加可选的自动/CUDA/Vulkan 后端选择，Windows 的默认选择及线程亲和性处理保持原状。Linux 自动选择时用独立且有超时的子进程执行真实合成内核，验证实际后端和像素结果，不能把 `ti.init()` 成功等同于完整可用。CUDA 不可用时尝试 Vulkan，仍保留 GPU 片段合成；已初始化的运行时不热切后端。OpenGL 不纳入 Linux 默认候选。
5. 拼接保持现状：优先硬件编码，失败回退 libx264；符合条件的最终拼接继续流拷贝。此次实验没有改这些函数。

第 4 项用于提高选择可靠性并提供可操作的替代后端，不能据此宣称 RTX 5060 的 CUDA 卡死已被修复。DSW RTX 4090 和 Windows RTX 4070 Laptop 均不是 Blackwell。若后续实机出现中途 GPU 卡死，应单独评估渲染进程隔离，不能仅给 Python 等待线程加一个超时后继续使用已卡死的 GPU 上下文。

## 实验环境与隔离

| 项目 | Linux DSW | Windows 原环境 / 候选环境 |
| --- | --- | --- |
| 系统 | Ubuntu 24.04，容器内 glibc 2.39 | Windows 11 |
| GPU | NVIDIA RTX 4090，驱动 570.153.02 | RTX 4070 Laptop，驱动 555.97 |
| Python | 3.12.3，临时 venv | 3.12.11，现有 conda 环境只读使用 |
| Taichi | 1.7.4 | 1.7.4 |
| OpenCV | 基线 5.0.0.93 / 候选 4.14.0.94 | 基线 4.12.0.88 / 候选 4.14.0.94 |
| NumPy | 2.5.3 | 2.2.6 |
| MoviePy | 2.2.1 | 2.2.1 |
| FFmpeg | 7.1.5 | 7.1 |

DSW 临时根目录为 `/tmp/mai-gen-issue123-20260916`。`venv` 从仓库现有 requirements.txt 加 Taichi 安装，实际解析到了 OpenCV 5.0.0.93；`opencv414` 是通过 PYTHONPATH 在子进程中启用的独立 wheel 目录。候选环境 `pip check` 通过。Windows 以相同方式在 `test_output/issue123/windows-opencv414` 隔离候选 OpenCV，没有修改现有 conda 包。

DSW Vulkan 测试指定 NVIDIA ICD，避免将 Mesa 软件 Vulkan 误认为 NVIDIA GPU。每个后端在独立进程运行，每项测试最多 150 秒；Linux 超时会终止本项测试的整个进程组。

## Linux 实测

素材为同一套程序生成的 8 秒 640×360/30fps H.264 和 AV1 彩条动画，包含 48 kHz 正弦音轨。片段渲染使用仓库真实 `render_segment_accel`、Taichi `FrameCompositor`、Prism 背景、文字渲染和编码实现，成绩层使用透明测试图。没有模拟 Taichi、解码器或编码器。

| 检查 | OpenCV 5.0.0.93 | OpenCV 4.14.0.94 |
| --- | --- | --- |
| H.264：首帧、向前取帧、向后 seek | 通过 | 通过 |
| AV1：相同五个时间点 | 全部读帧失败，但打开状态和 240 帧元信息正常 | 全部通过 |
| CUDA 600 帧 1080p 实际合成 | 像素检查通过 | 像素检查通过 |
| NVIDIA Vulkan 600 帧 1080p 实际合成 | 像素检查通过 | 像素检查通过 |
| CUDA AV1 短片段 | 应用返回成功，但视频区域均值为 0，验收失败 | 正常画面，帧数正确 |
| CUDA H.264 / AV1，1080p60，各 6 秒 | 未作为该组合的正式验收 | 均输出 360 帧，非黑屏检查通过 |
| Vulkan AV1，1080p60，6 秒 | 未作为该组合的正式验收 | 输出 360 帧，非黑屏检查通过 |

基线 AV1 的 OpenCV 日志包含 `Failed to get pixel format` / `Get current frame error`。更换候选 wheel 后，不修改应用代码即可恢复视频解码和 Taichi 合成，因果对照成立。

DSW 的 NVENC 实际探测报 `OpenEncodeSessionEx failed: unsupported device (2)`。因此片段使用 Taichi GPU 合成、libx264 软件编码；这两者是不同阶段。

拼接两段 6 秒片段，设置 0.5 秒交叉转场，正常自动选编码器以及显式传入 h264_nvenc 两条测试都通过。后一条在主体段、转场段实际尝试 NVENC 后失败，再由原实现回退 libx264。输出为 H.264 1920×1080/60fps，690 帧，视频时长 11.500 秒，AAC 音频 11.521333 秒；整段 FFmpeg 解码无错误。约 21 ms 的封装时长差接近一个 AAC 帧，不代表已完成真人主观音画同步验收。

已抽取并查看 AV1 + CUDA 输出帧，彩条视频、背景与文字均可见。测试结束 DSW GPU 回到 705 MiB、0% 利用率，未留下本轮渲染子进程。

## Windows 实测

原 OpenCV 4.12 环境的 H.264/AV1 取帧、600 帧 CUDA/Vulkan 内核检查、CUDA+NVENC 短片段全部通过。

候选 4.14 环境的相同基线检查全部通过。1080p60、6 秒的 CUDA H.264、CUDA AV1、Vulkan AV1 片段均输出 360 帧，非黑屏检查通过，实际使用 h264_nvenc。原拼接实现的自动编码器和显式 NVENC 测试均通过，最终视频 690 帧、11.500 秒，AAC 音频 11.521333 秒；完整解码无错误。

## 重复 seek 的性能问题

额外发现一个与操作系统无关的既有问题：`get_frame()` 总是在读取后把当前位置推进一帧。当输出帧率是源帧率的两倍时，下次请求常常还是上一源帧，现实现会向后 seek，再次从关键帧解码。

在相同 30fps AV1 素材上，以 60fps 请求连续 2 秒、共 120 帧，原实现发生 61 次 seek；最后一帧缓存原型只需 1 次 seek、60 次读取：

| 环境 | 原读帧耗时 | 缓存重复帧后 |
| --- | --- | --- |
| Linux / OpenCV 4.14 | 0.971 秒 | 0.029 秒 |
| Windows / OpenCV 4.12 | 12.149 秒 | 0.371 秒 |
| Windows / OpenCV 4.14 | 11.736 秒 | 0.361 秒 |

因此观察到的 Windows AV1 慢主要是既有重复 seek 问题，该对照未显示 OpenCV 4.14 带来退化。

将缓存原型接入真实 Taichi CUDA 片段生成，6 秒、1080p60 AV1 样本结果如下：

| 环境 | 原管线耗时 | 缓存原型耗时 | 输出检查 |
| --- | --- | --- | --- |
| Linux / 4.14 / libx264 | 13.377 秒 | 7.175 秒 | 360 帧；缓存前后逐帧像素差为 0 |
| Windows / 4.14 / NVENC | 101.592 秒 | 17.104 秒 | 360 帧；缓存前后逐帧像素差为 0 |

以上是该合成样本的单次对照，不是通用性能保证，也不是完整 B50 耗时估计。缓存只在实验脚本中注入，正式应用读帧器尚未修改。

## 证据与复现材料

本机实验材料位于 `test_output/issue123/`，不作为用户运行数据或发布包内容：

- `probe_runtime.py`：解码、实际 GPU 内核、真实片段渲染及输出验证。
- `run_probes.py`：进程隔离、超时、日志和结构化结果。
- `decode_benchmark.py`、`compare_outputs.py`：重复 seek 对照和缓存前后输出逐帧像素比较。
- `dsw-evidence/logs-baseline-opencv500-final/summary.json`：修正测试脚本退出清理后的 5.0 失败基线。
- `dsw-evidence/logs-baseline-opencv414/summary.json`：4.14 基线。
- `dsw-evidence/logs-acceptance-opencv414/summary.json`：Linux 1080p60 与拼接验收。
- `logs-baseline-windows-original/summary.json`：Windows 原依赖回归。
- `logs-baseline-windows414/summary.json`、`logs-acceptance-windows414/summary.json`：Windows 候选依赖验证。
- `decode-windows-original.log`、`decode-windows414.log`、`render-windows414-cached.log`、`compare-windows414.log`：Windows 性能及输出一致性证据。
- `dsw-evidence/decode-linux414.log`、`dsw-evidence/render-linux414-cached.log`、`dsw-evidence/compare-linux414.log`：Linux 性能及输出一致性证据。

最初测试脚本在结束 GPU 工作线程后才由主线程销毁 Taichi，触发 CUDA 上下文退出错误。测试脚本改为在原 GPU 工作线程上 `ti.reset()` 后再退出，随后重跑了基线。该脚本清理问题与视频 AV1 解码失败分开记录，不将它认定为 issue 中的运行时 CUDA 卡死。

## 尚未覆盖

- RTX 5060 / Blackwell 实机和原报告的长时间 CUDA 卡死。
- Debian 12 Docker、AMD/Intel GPU、macOS，以及旧 Windows 运行包的完整重建。
- 真实完整 B50 长视频、损坏素材、可变帧率、10-bit AV1、动态背景和全部 UI 操作。
- 后端选择、超时探测和读帧失败防护仍是待实现的正式修复，不在此次依赖对照中假装已完成。

Issue #124 的两处 `Playcount` 路径修正方案仍然成立，本轮没有将其混入 #123 实验。

## 上游依据

- [项目 issue #123](https://github.com/Nick-bit233/mai-gen-videob50/issues/123)
- [OpenCV Linux AV1 修复 PR #1209](https://github.com/opencv/opencv-python/pull/1209)
- [OpenCV Python 发布记录](https://pypi.org/project/opencv-python/#history)
- [Taichi 初始化 API（包含 enable_fallback）](https://docs.taichi-lang.org/api/taichi/)
