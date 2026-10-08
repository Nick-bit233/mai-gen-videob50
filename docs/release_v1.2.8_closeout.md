# 1.2.8 收尾操作

本地开发在 `codex/new-theme-system` 完成后，按以下顺序补齐正式素材和线上配置，再完成真实网络及正式发布包验收。当前日志直传使用独立桶的匿名前缀授权，舞萌使用 release 视频匹配，中二继续旧版搜索。以下网络写入命令仅在明确执行时上传合成测试报告。

## 正式中二素材

当前占位资源位于 `static/assets/images/Chunithm/ConstantDisplay/`。正式图可以替换同名文件，保持布局规格；若采用其他文件名，在 `utils/themes.py` 的对应 `asset_paths` 中更新引用。

| 文件 | 现有尺寸 | 正式文件要求 |
| --- | --- | --- |
| `content_base.png` | 1920×1080 | 独立成绩底图，右下定数区域不带旧版本 Logo、数字或标题 |
| `header_compare.png` | 429×50 | “定数变动”标题层，与底图配套 |
| `header_single.png` | 429×50 | “谱面定数”标题层，与底图配套 |
| `logo_cn_2027.png` | 190×106 | 国服版本透明 PNG，保持比例，允许容纳框内等比缩放 |
| `logo_latest_mate.png` | 202×106 | 最新版本透明 PNG，保持比例，允许容纳框内等比缩放 |

替换后不要再次运行 `scripts/prepare_chunithm_placeholders.py`，它会写入占位图。重生成中二成绩图片，并检查 Verse/X-Verse 的国服、最新、对比三种布局；确认标题、Logo、数字和等级标识没有遮挡或残留。

还需确定 Verse、X-Verse 各自的片头和片尾 BGM。将正式 MP3/WAV 放进 `static/assets/audios/`，在 `utils/themes.py` 对这两个预设分别设置 `intro_bgm` 和 `ending_bgm`。当前两者仍兼容复用原片头音乐。保存过的自定义音频保留；在样式页主动应用预设才使用新的默认配对。

在开发仓库根目录，用包内 Python 运行现有主题验收：

```powershell
& '<本地验收应用>\runtime\python.exe' '.\scripts\verify_theme_system.py' --output '.\test_output\release128-final-cpu' --backend cpu
& '<本地验收应用>\runtime\python.exe' '.\scripts\verify_theme_system.py' --output '.\test_output\release128-final-cuda' --backend cuda
```

输出目录必须是新的目录。脚本使用可辨识的测试音频验证音频路由；正式 BGM 还需在样式页试听，并实际生成正式片头/片尾检查内容。正式素材变更后，只复验受影响画面、音乐及必要渲染回归，保留之前的本地测试证据。

## 创建日志桶和配置前缀权限

新建独立标准存储桶，ACL 为 `private`、Object ACL 使用 `default/private`。Bucket Policy 仅对 `reports/*` 开放匿名 `oss:PutObject`、`oss:GetObject`。不授予匿名列举、删除、修改 ACL、桶管理和前缀外读写权限。核对 OSS 全局及该桶的“阻止公共访问”设置是否阻止这一授权，其他桶按各自保护范围保留配置。

在 `static/error_report_config.json` 填写公共 HTTPS 桶地址及前缀：

```json
{
  "endpoint": "https://<日志桶公共域名>",
  "prefix": "reports"
}
```

该文件不填写任何身份、AccessKey 或签名参数。收尾时设置日志保留期及费用告警。客户端使用随机报告编号和禁止同名覆盖参数，上传失败仍保留本地诊断包。

## 发布舞萌公开元数据投影

发现入口仍为 `https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com/metadata_json/active-release.json`。它的 schema 1 结构来自线上发布端，包含 `kind=catalog_active_release`、`game_type=maimai`、`release_revision`、`metadata_store_version`、`state_row_version` 和 release ID。

为避免公开 SaaS 私有完整版，可以将桌面白名单投影发布到独立公共目录。先在拥有该 release 文件的维护环境中运行：

```powershell
python '.\scripts\export_public_metadata_release.py' --source '<私有release本地目录>' --output '<新的公开投影目录>'
```

这一步只读取源文件并产生三份公开 JSON，不上传、不读取 OSS 凭据，也不修改私有原文件。输出包含 `mai_fusion_data.json`、`asset-manifest.json` 和 `release.json`；视频清单仅保留已审核、可解析的公开 Bilibili 来源和桌面字段。

将这三份文件通过维护者的 OSS 控制台或现有发布流程上传，例如：

```text
metadata_json/desktop-public/releases/<release_revision>/mai_fusion_data.json
metadata_json/desktop-public/releases/<release_revision>/asset-manifest.json
metadata_json/desktop-public/releases/<release_revision>/release.json
```

对发现入口和上述公开前缀授予匿名 `GetObject`。在 `static/metadata_release_config.json` 配置：

```json
{
  "index_url": "https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com/metadata_json/active-release.json",
  "files_root": "https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com/metadata_json/desktop-public/releases/{revision}/"
}
```

`files_root` 留空时客户端读取标准 `metadata_json/releases/<revision>/` 布局；采用独立公共投影时填写上述路径。两个地址必须同源，客户端通过已验证的 revision 替换 `{revision}`，不会接受签名地址、跨域重定向或混合版本。

以后线上 release 更新时，公开投影也要纳入发布收尾：先准备并验证该 revision 的三份文件可匿名读取，再使发现入口对桌面消费者生效。原始私有清单与公开视频对象权限分别管理；不公开私有视频文件来代替视频来源匹配。

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

该命令会上传一份合成报告并匿名下载比较内容，同时尝试列举、删除该合成报告、在随机 `outside-verification/*` 键写入小测试文件。后三项必须返回拒绝。若策略错误导致操作被允许，脚本报失败；维护者在控制台清理仅由该轮产生的测试对象并修正策略，不能删除其他用户报告。

最后在页面实际上传一次诊断包：查看预览、确认提交、记录报告编号，在控制台确认文件存在。重启后检查首页舞萌版本和默认视频匹配，中二继续走旧版搜索，并测试断网/403 时保留旧数据和本地日志下载。元数据模拟测试和本地 HTTP 上传测试不代替这一步。

## 正式发布检查

确认正式素材、两个公共配置文件、样本 Excel、新增依赖和 `runtime_bootstrap.py` 都进入最终包。完整替换旧 runtime，避免混装旧 Python 包；保留用户数据库、存档、曲绘和自定义音乐。重新解压到中文及空格目录启动，至少验证导入保存、日志提交、舞萌匹配和一条真实成片。

本地打包文件标注为 `local`，用于验收，不作为正式发布完成声明。正式素材与网络验收完成后更新版本说明和验收记录，再生成正式发布包。
