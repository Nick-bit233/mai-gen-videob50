# 中二定数展示素材（当前为占位拆分）

用户已授权先从现有底图简单拆分，后续提供独立正式素材。本目录不代表最终美术。

| 文件 | 规格 / 用途 |
| --- | --- |
| content_base.png | 1920×1080，无定数区标题和版本 Logo 的成绩底图 |
| header_compare.png | 429×50，“定数变动”标题 |
| header_single.png | 429×50，“谱面定数”占位标题 |
| logo_cn_2027.png | 国服 Logo，目前 190×106，仍包含原底色 |
| logo_latest_mate.png | 最新版 Logo，目前 202×106，仍包含原底色 |

正式 Logo 使用透明 RGBA PNG；合成器等比容纳于 202×106 区域，单版本居中，双版本分列。
可以直接替换同名文件，或修改 `utils/themes.py` 中 `constant_*` 路径；替换后重新生成成绩图片。
当前中性底图使用同区域的空白行延伸制作，标题、Logo 和底图均可独立替换。
生成脚本为 `scripts/prepare_chunithm_placeholders.py`，不修改原始 Verse 底图；正式素材到位后不要再次运行该脚本覆盖它们。

原仓库 `Frames/1.png`（ADVANCED）缺失，本目录未补造该难度框。
