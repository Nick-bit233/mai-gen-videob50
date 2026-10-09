# 中二定数展示素材

内容底图与标题层沿用用户确认的 Verse 资源；2026-10-09 已接入用户提供的正式透明国服及 MATE Logo。Verse、X-Verse、MATE 共用这些成绩图片资源，动态背景和音乐由各自的视频预设选择。

| 文件 | 规格 / 用途 |
| --- | --- |
| content_base.png | 1920×1080，无定数区标题和版本 Logo 的成绩底图 |
| header_compare.png | 429×50，“定数变动”标题 |
| header_single.png | 429×50，“谱面定数”标题 |
| logo_cn_2027.png | 国服透明 RGBA Logo，188×95 |
| logo_latest_mate.png | MATE 透明 RGBA Logo，196×85 |

正式 Logo 使用透明 RGBA PNG；合成器等比容纳于 202×106 区域，单版本居中，双版本分列。
可以直接替换同名文件，或修改 `utils/themes.py` 中 `constant_*` 路径；替换后重新生成成绩图片。
当前中性底图由原 Verse 底图拆分而来，标题、Logo 和底图均可独立替换。
生成脚本为 `scripts/prepare_chunithm_placeholders.py`，不修改原始 Verse 底图；正式素材到位后不要再次运行该脚本覆盖它们。

原仓库 `Frames/1.png`（ADVANCED）缺失，本目录未补造该难度框。
