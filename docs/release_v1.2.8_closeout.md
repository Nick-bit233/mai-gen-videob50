# 1.2.8 收尾操作

2026-10-20 更新：两家公开客户端已配置，舞萌真实授权、全部成绩读取、B50/AP B50 页面保存和新会话重载通过；用户撤销后再次授权与保存重载也通过。中二真实账号验收由用户明确允许跳过。ADVANCED 边框已补齐，本轮提交后重打验收包，保持不推送、不正式发布。

`codex/new-theme-system` 的 1.2.8 开发、自动测试、用户补充素材及 OSS 网络联调已完成。当前进入本地人工验收阶段，未推送远端或发布。日志使用独立桶匿名只写，舞萌直接读取现役 release，中二视频继续旧版搜索。以下网络写入命令仅在明确执行时上传合成测试报告。

## 正式中二素材

用户提供的正式透明 Logo 已接入 `static/assets/images/Chunithm/ConstantDisplay/`；内容底图及标题层保留已确认的 Verse 资源。后续替换应保持布局规格，或在 `utils/themes.py` 更新路径。

| 文件 | 现有尺寸 | 正式文件要求 |
| --- | --- | --- |
| `content_base.png` | 1920×1080 | 独立成绩底图，右下定数区域不带旧版本 Logo、数字或标题 |
| `header_compare.png` | 429×50 | “定数变动”标题层，与底图配套 |
| `header_single.png` | 429×50 | “谱面定数”标题层，与底图配套 |
| `logo_cn_2027.png` | 188×95 | 已接入的国服透明 RGBA PNG，等比缩放 |
| `logo_latest_mate.png` | 196×85 | 已接入的 MATE 透明 RGBA PNG，等比缩放 |

不要再次运行 `scripts/prepare_chunithm_placeholders.py`，它会覆盖正式 Logo。Verse/X-Verse/MATE × 国服、最新、对比九种布局已生成检查；人工验收仍应重生成自己的存档图片，确认标题、Logo、数字和等级标识。

Verse/X-Verse 使用 `opening_chunithm_verse.mp3` / `ending_chunithm_verse.mp3`；新增 MATE 预设使用 `opening_chunithm_mate.mp3` / `ending_chunithm_mate.mp3` 和 `opening_bg_chunithm_mate.mp4`。MATE 的片头/片尾与内容动态背景使用新视频，成绩底图与标题层共用 Verse。已保存的自定义音乐保留；缺失的旧内置 `intro_chunithm_verse.mp3` 引用自动迁移到新配对。

在开发仓库根目录，用包内 Python 运行现有主题验收：

```powershell
& '<本地验收应用>\runtime\python.exe' '.\scripts\verify_theme_system.py' --output '.\test_output\release128-repeat-cpu' --backend cpu --preset-assets
& '<本地验收应用>\runtime\python.exe' '.\scripts\verify_theme_system.py' --output '.\test_output\release128-repeat-cuda' --backend cuda --preset-assets
```

输出目录必须是新的目录。脚本使用可辨识的测试音频验证音频路由；正式 BGM 还需在样式页试听，并实际生成正式片头/片尾检查内容。正式素材变更后，只复验受影响画面、音乐及必要渲染回归，保留之前的本地测试证据。

## 创建日志桶和配置前缀权限

日志桶为 `nickbit-maigen-report-logs`（华东2上海），ACL 为 `private`、Object ACL 使用 `default/private`。Bucket Policy 仅对 `reports/*` 开放匿名 `oss:PutObject`，不开放匿名读取、列举、删除、修改 ACL、桶管理和前缀外读写权限；维护者登录控制台读取报告。核对 OSS 全局及该桶的“阻止公共访问”设置是否阻止这一授权，其他桶按各自保护范围保留配置。

在 `static/error_report_config.json` 填写公共 HTTPS 桶地址及前缀：

```json
{
  "endpoint": "https://nickbit-maigen-report-logs.oss-cn-shanghai.aliyuncs.com",
  "prefix": "reports"
}
```

该文件不填写任何身份、AccessKey 或签名参数。收尾时设置日志保留期及费用告警。客户端使用随机报告编号和禁止同名覆盖参数，上传失败仍保留本地诊断包。成功提交后当前会话禁用再次提交；网络超时后重试沿用固定对象名。如果返回 409，提示报告已存在但内容无法核对，不发出 GET、不覆盖文件，也不将冲突认定为提交成功。维护者用报告编号在控制台核对。

匿名授权语句如下，已有规则需合并并确认没有其他公共读取授权：

```json
{
  "Version": "1",
  "Statement": [{
    "Effect": "Allow",
    "Principal": ["*"],
    "Action": ["oss:PutObject"],
    "Resource": ["acs:oss:*:*:nickbit-maigen-report-logs/reports/*"],
    "Condition": {"Bool": {"acs:SecureTransport": "true"}}
  }]
}
```

服务器端禁止覆盖写规则使用前缀 `reports/`、后缀留空、所有账号 `*`；保持版本控制未开启。此项限制既有对象后续覆盖，不限制新文件上传总量。生命周期清理和费用告警不能充当实时上传限额，客户端 10 MiB 限制也不能防止其他程序直接滥用匿名上传。

## 舞萌公开元数据：直接读取现有 release

发现入口仍为 `https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com/metadata_json/active-release.json`。它的 schema 1 结构来自线上发布端，包含 `kind=catalog_active_release`、`game_type=maimai`、`release_revision`、`metadata_store_version`、`state_row_version` 和 release ID。

如果发现索引及同版本 JSON 已准备公开且格式兼容，可以直接匿名读取现有 release，不必另行生成、上传桌面投影。客户端仍只保存已审核、可解析的公开 Bilibili 视频来源字段。当前配置保持 `files_root` 为空，使用以下标准布局：

```text
metadata_json/active-release.json
metadata_json/releases/<release_revision>/release.json
metadata_json/releases/<release_revision>/mai_fusion_data.json
metadata_json/releases/<release_revision>/asset-manifest.json
```

Bucket ACL 可以设为私有，并通过 Object ACL 或只读 Bucket Policy 公开选定 JSON。Object ACL 选择“公共读”可以独立于桶权限公开该文件；选择“继承 Bucket”在私有桶中不会公开。网页入口为 Bucket 列表 → 目标桶 → 文件列表 → 目标文件操作列“详情” → 设置读写权限 → 公共读 → 确定。改桶权限前，先保留仍需公开的图片及旧版 JSON 的访问规则；本项目的中二旧路径为 `metadata_json/chuni_fusion_data.json`。

对持续新增的 release，优先使用只读 Bucket Policy。网页入口为 权限控制 → Bucket 授权策略 → 按语法策略添加 → 编辑。将以下授权语句合并到原策略；不覆盖仍需保留的其他公开资源规则：

```json
{
  "Version": "1",
  "Statement": [{
    "Effect": "Allow",
    "Principal": ["*"],
    "Action": ["oss:GetObject"],
    "Resource": [
      "acs:oss:*:*:nickbit-maigen-images/metadata_json/active-release.json",
      "acs:oss:*:*:nickbit-maigen-images/metadata_json/mai_fusion_data.json",
      "acs:oss:*:*:nickbit-maigen-images/metadata_json/chuni_fusion_data.json",
      "acs:oss:*:*:nickbit-maigen-images/metadata_json/asset-manifest.json",
      "acs:oss:*:*:nickbit-maigen-images/metadata_json/releases/*/release.json",
      "acs:oss:*:*:nickbit-maigen-images/metadata_json/releases/*/mai_fusion_data.json",
      "acs:oss:*:*:nickbit-maigen-images/metadata_json/releases/*/asset-manifest.json"
    ],
    "Condition": {"Bool": {"acs:SecureTransport": "true"}}
  }]
}
```

该授权仅允许读取所列 JSON，不授予匿名上传、删除、列举或管理权限。匿名公开授权要求 OSS 全局及该桶“阻止公共访问”关闭，显式 Deny 或其他访问限制仍需单独检查。给目录占位对象设置 ACL 不会自动修改目录下文件或未来新文件的 ACL；Bucket Policy 的通配符资源规则可覆盖后续同布局 release。

目前 `static/metadata_release_config.json` 使用：

```json
{
  "index_url": "https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com/metadata_json/active-release.json",
  "files_root": ""
}
```

2026-10-09 权限修正后，索引和现役 `video-timeline-repair-20261008` 的三份 JSON 均匿名返回 200，成套更新已通过：1607 首曲目、2840 条可用视频来源。同版本只检查一次索引，断网保持旧完整版本；中二及旧版舞萌 JSON 路径也返回 200。合法的全角空格标题 `「　」` 被保留，未知作者 `null` 规范为空字符串，不做模糊视频身份猜测。

相关控制台和鉴权说明见 [Object ACL](https://help.aliyun.com/zh/oss/user-guide/object-acl)、[Bucket Policy](https://help.aliyun.com/zh/oss/user-guide/use-bucket-policy-to-grant-permission-to-access-oss/) 和 [OSS 0003-00000005](https://www.alibabacloud.com/help/zh/oss/user-guide/0003-00000005)。

如果以后需要保留原始清单私有，再选用服务端公开投影：

```powershell
python '.\scripts\export_public_metadata_release.py' --source '<私有release本地目录>' --output '<新的公开投影目录>'
```

该命令只读取源文件并生成 `mai_fusion_data.json`、`asset-manifest.json`、`release.json`，不上传、不读取 OSS 凭据，也不修改私有原文件。维护者可将结果上传到 `metadata_json/desktop-public/releases/<revision>/`，并将 `files_root` 改为 `https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com/metadata_json/desktop-public/releases/{revision}/`。文件根目录必须与发现入口同源，客户端不会接受签名地址、跨域重定向或混合版本。以后每次发布先备齐该版本文件，再切换发现入口；视频对象的权限单独管理。

## 真实网络联调

在开发仓库根目录进行验收，先检查舞萌元数据：

```powershell
& '<本地验收应用>\runtime\python.exe' '.\scripts\verify_release128_network.py' --metadata
```

脚本匿名读取实际配置的发现入口和配套文件，在 `test_output/release128-network-*` 独立目录落地结果，不修改现有存档。必须成功读取同一版本，公开来源能对应谱面，并生成 `verification.json`。当前 403 或文件缺失均作为失败处理。

日志桶就绪后，显式提交一份无玩家数据的合成诊断包并校验权限：

```powershell
& '<本地验收应用>\runtime\python.exe' '.\scripts\verify_release128_network.py' --submit-test-report --check-negative-policy
```

该命令会上传一份合成报告，检查匿名 GET/HEAD、列举、删除该合成报告和随机 `outside-verification/*` 键的写入全部被拒绝，并验证同名提交返回 409。不会通过匿名下载比较内容。即使失败，`verification.json` 仍保存已完成的检查结果；若策略错误导致操作被允许，维护者在控制台清理仅由该轮产生的测试对象并修正策略，不能删除其他用户报告。成功的 PUT 是服务器接收证据；实际 ZIP 内容由维护者登录下载检查。

最后在页面实际上传一次诊断包：查看预览、确认提交、记录报告编号，在控制台确认文件存在。重启后检查首页舞萌版本和默认视频匹配，中二继续走旧版搜索，并测试断网/403 时保留旧数据和本地日志下载。元数据模拟测试和本地 HTTP 上传测试不代替这一步。

## 本地人工验收

1. 将本轮 `manual` 应用包和配套 runtime 包解压到同一个新目录，运行 `start.bat`。确认版本 1.2.8，首次无网络也能读取内置曲库；不要混装旧 runtime。
2. 首页手动检查舞萌元数据，确认显示现役 release；确认中二仍使用旧版歌曲 JSON 和视频搜索流程。
3. 在“自定义视频样式”选择 MATE 并点击“应用预设”。分别试听片头、片尾音乐并生成预览；再切换 Verse/X-Verse，确认保存的自定义音乐和另一游戏设置保留。
4. 用自己的中二存档依次生成国服、最新、定数对比图片。确认单版本 Logo 居中、对比双列、缺失定数为 `--`，Rating、成绩和记录排序不变。旧图片需重生成一次。
5. 用样本 Excel 和自有曲绘路径验证两种游戏的列映射、预览、草稿、提交及重载；确认失败不会留下半个存档。
6. 先生成短片，再用常用分辨率/帧率生成自己的完整分表，检查背景、音乐、转场及主观音画同步。分别试 CPU 与可用的 GPU 后端；自动证据覆盖 640×360/30fps，不能代替长 B50 和其他用户硬件验收。
7. 错误报告页查看预览、下载本地包、手动确认提交，记录报告编号；维护者在日志桶控制台检查报告。匿名只写不提供报告下载；重复编号 409 不覆盖也不直接认定成功。

原先缺少的中二 `Frames/1.png`（ADVANCED）已在 2026-10-20 补齐。按官方难度选择画面的橙色制作，保持 1311×780 与原边框透明通道逐字节一致；三预设 × 三种定数模式生成通过。打包缺少任一难度边框会立即报错。

## 人工通过后再发布

确认正式素材、日志/元数据/OAuth 三个公共配置文件、样本 Excel、新增依赖和 `runtime_bootstrap.py` 都进入最终包。完整替换旧 runtime，避免混装旧 Python 包；保留用户数据库、存档、曲绘和自定义音乐。重新解压到中文及空格目录启动，至少验证 OAuth 授权与导入保存、日志提交、舞萌匹配和一条真实成片。

本轮打包文件标注为 `manual`，状态为 `manual_acceptance_pending`。开发和自动验收已完成，人工验收及远端推送/正式发布仍由用户后续确认。
