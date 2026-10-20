# 新版主题系统：使用与验收

实现日期：2026-09-18。开发分支：`codex/new-theme-system`。尚未发布新版本或修改正式运行数据。

## 使用方法

1. 打开“自定义视频素材和样式”，选择预设并点击“应用预设”。舞萌可选 Buddies、Prism、Circle、MAGiCAL。
2. 在“自定义样式”分别设置“片头背景音乐”“片尾背景音乐”。支持 MP3/WAV、单独试听和恢复相应主题默认音乐；点击“保存自定义样式”后生效。
3. 页面配色在首页“外观设置”中单独选择 MAGiCAL，并应用主题。
4. 中二模式在“生成成绩背景图片”选择“国服 / 最新 / 定数对比”，然后重新生成图片；自定义样式的预览也使用该选项。
5. 完成视频编辑后照常生成视频。只修改 BGM 可选“跳过全部曲目片段”，单独更新片头片尾；不必重新下载谱面视频。

短 BGM 从头循环到片段结束，长 BGM 截断到片段长度。多页片头/片尾仍逐段从头播放。上传先验证时长与解码，新文件用独立名称保存，同名上传不会覆盖另一段的音频。

应用预设会覆盖自定义样式。仅切换中二 Verse / X-Verse 会保留定数展示选择；“恢复本游戏默认样式”会恢复默认对比模式，并保留已上传文件及另一游戏的设置。

## 默认音乐

| 主题 | 片头 | 片尾 |
| --- | --- | --- |
| Buddies | BUDDiES opening | BUDDiES ending |
| Prism | PRiSM opening | PRiSM ending |
| Circle | CiRCLE opening | CiRCLE ending |
| MAGiCAL | 正式 magical opening | 正式 magical ending |
| Verse / X-Verse | 现有 Verse 音频 | 暂沿用现有 Verse 音频 |

舞萌采用 SaaS 正式配对，Magical 采用 2026-09-17 正式素材。中二独立配置与上传功能已可用，新的默认配对等待用户提供。

## 中二定数规则

| 选择 | 右下定数区 | 左侧等级 |
| --- | --- | --- |
| 国服 | 国服 Logo + `level_value_cn`，无比较箭头 | 根据国服定数显示 |
| 最新 | 最新 Logo + `level_value_latest`，无比较箭头 | 根据最新定数显示 |
| 定数对比 | 双 Logo、双列定数及原有升降/相等箭头 | 延续原有优先国服、缺失回退逻辑 |

国服、最新均严格使用对应字段，缺失显示 `--`，不会借用另一版本。未标明版本来源的存档自定义定数也不自动填入单版本展示。单曲 Rating、成绩和分表排序不重算。

“最新”指本机已加载元数据中的最新字段，不会因为选择该选项自动联网更新。版本 Logo 与元数据需配套维护。

## 旧配置与产物

- 老自定义配置缺少 `ending_bgm` 时，片尾继续使用其原有的 `intro_bgm`。已移除的旧内置 Verse 音频引用迁移到新配对；其他仍存在的旧音频和用户上传音频保留。
- 缺少定数展示选项时，默认为“定数对比”。按游戏补全配置，不覆盖另一游戏保存值。
- 新图片旁记录 `.theme.json`，片段也保存直接可比较的配置记录；不计算文件或状态 hash。
- 旧成绩图缺少记录时需重新生成一次。之后，仅 BGM 变化不会要求重做成绩图；定数模式、成绩底图或相应字体变化会在视频生成前提示重做图片。
- 图片先生成到新的批次目录，再通过一次数据库事务发布全部图片引用；中途失败保留原引用和视频编辑字段。
- 未变化的片段仍可跳过。新片段成功后替换旧文件；拼接只使用本次完成的片段列表，避免混入其他存档或旧编号片段。
- 旧图片批次和上传文件不自动删除。本版本不做存档数据迁移。

## 1.2.8 正式素材和 MATE

中二内容底图及标题层沿用用户已确认的 Verse 资源，正式透明版本 Logo 已补齐。素材位于 `static/assets/images/Chunithm/ConstantDisplay/`，具体规格见该目录的 `README.md`：

- `content_base.png`：1920×1080 中性底图。
- `header_compare.png` / `header_single.png`：两种标题。
- `logo_cn_2027.png` / `logo_latest_mate.png`：两个独立版本 Logo。

新增 MATE 预设使用 `opening_bg_chunithm_mate.mp4` 作为片头/片尾与内容动态背景，使用 `opening_chunithm_mate.mp3` / `ending_chunithm_mate.mp3`。Verse/X-Verse 使用 `opening_chunithm_verse.mp3` / `ending_chunithm_verse.mp3`，共用 Verse 成绩底图。缺失的旧内置 `intro_chunithm_verse.mp3` 引用在读取时迁移；其他用户自定义音乐不被替换。不要再次运行占位制作脚本覆盖正式 Logo。

当前 1.2.8 的 51 项 unittest、19 项视频匹配 pytest、三预设页面流程，以及 CPU/CUDA 的 9 张中二图、4 种完整短片及 6 个正式音乐片段均通过。最新证据见 `docs/release_v1.2.8_local_acceptance.md`；下方记录保留先前主题开发阶段的证据。

## 已完成验证

使用现有 Windows v1.2.6 解压 runtime（Python 3.12.10 / MoviePy 2.2.1 / OpenCV 4.14.0.94 / Taichi 1.7.4）和 FFmpeg 7.1，测试均写入独立的 `test_output` 目录。

- **28 项针对性回归测试通过**：旧配置兼容、分别选择音频、上传失败保护、版本严格取值、比较箭头、缺失等级、画面非定数区域不变、图片配置变化检测、数据库整批回滚、CPU 片段失败保留旧文件、排除旧编号片段。
- **Streamlit 页面流程通过**：应用预设、保存自定义值、预设切换刷新控件、切换游戏、三种模式往返切换、图片实际生成、预览、旧图片拦截、错误不误报成功和配色保存。额外验证“仅片头片尾”可正常执行，其他完整生成入口不能借该开关绕过图片检查。
- **CPU 真实渲染通过**：片头/片尾分别使用 440Hz / 880Hz 的 0.2 秒音频，均循环生成 1.2 秒片段；尾段频率约 438.89Hz / 877.78Hz，音频/视频时长均为 1.200 秒。再次运行不重做未变片段，仅改变片尾音乐时片头文件保持不变。
- **CUDA 真实渲染通过**：同样的音频选择、循环与更新行为通过；实际后端为 CUDA，编码使用 NVIDIA NVENC。舞萌和中二完整短片均完成 0.5 秒转场拼接，并可完整解码。
- **图片检查通过**：Verse / X-Verse × 三种模式；缺失定数；现有 BASIC、EXPERT、MASTER、ULTIMA 边框。单版本居中、对比双列，等级随版本切换而变化，Rating 及其他区域保持不变。

本机证据：

| 文件 | 内容 |
| --- | --- |
| `test_output/theme-unit-final.log` | 28 项回归结果 |
| `test_output/theme-cpu-02/verification.json` | CPU 分段/完整舞萌和中二短片、音频频率与时长 |
| `test_output/theme-cuda-02/verification.json` | CUDA + NVENC 分段/完整短片 |
| `test_output/theme-ui-01/verification.json` | 页面流程结果 |
| `test_output/theme-preflight.log` | 不同视频按钮的图片前置检查 |
| `test_output/theme-contact-sheet.png` | 三种中二模式对照图 |

## 验证边界与已知限制

- 完整成片验收是 640×360 / 30fps 的合成短样本；未做真实长 B50、1080p60、Linux、Vulkan、macOS 或浏览器原生文件上传操作验收。上传写盘/实际解码由真实音频测试覆盖，页面交互由 Streamlit AppTest 覆盖。
- 2026-10-20 已补齐中二 `Frames/1.png`（ADVANCED）：橙色边框保持原尺寸和透明通道，九种预设/定数组合与五难度图像验证通过。原先的 ADVANCED 素材缺口已关闭。
- 测试额外试用了 UI 不提供的 0.1 秒转场，GPU 既有 acrossfade 拼接失败；页面支持的 0.5 秒转场通过。未更改转场算法去扩展极短转场能力。
- GPU 0.5 秒转场样本视频流长 2.600 秒、AAC 流长 2.752 秒；本次未修改原拼接/音频均衡算法，也不宣称解决该音轨尾长差异或完成主观音画同步验收。CPU 对应测试使用 0.1 秒转场，详细流时长保存在证据中。
- CUDA 进程打印过现有全局 Taichi 缓存目录锁警告，但后端断言、实际渲染与输出检查均通过；未清理用户的全局缓存。
- 当前仍未正式发布。中二正式 Logo、Verse/MATE 音乐已在 10 月 9 日接入；本轮补齐 ADVANCED 后重打验收版。

## 重跑验证

在已安装项目依赖的 Python 环境下：

```text
python -m unittest discover -s tests -p test_theme_system.py -v
python -m unittest discover -s tests -p test_runtime_regressions.py -v
python scripts/verify_theme_system.py --output test_output/theme-cpu-new --backend cpu
python scripts/verify_theme_system.py --output test_output/theme-cuda-new --backend cuda
python scripts/verify_theme_ui.py --output test_output/theme-ui-new
```

验收脚本要求新输出目录，防止覆盖已有证据；UI 验收复制应用并创建合成数据库，不使用真实用户存档。
