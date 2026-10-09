# 1.2.8 本地实现和验收记录

开发分支为 `codex/new-theme-system`，版本号为 `1.2.8`。本地开发、自动回归、OSS 实网联调和用户补充中二素材接入已完成，新增 MATE 预设，等待本地人工验收。尚未推送或正式发布。最新状态以本文件末尾 2026-10-09 最终收尾记录为准，前面的阶段记录保留其当时范围。

## 实现范围

- Excel 支持 `.xlsx`、工作表选择、中英文表头别名与模糊候选、列映射确认、行级默认值和错误预览、曲绘路径、可选元数据补全、追加/替换草稿。两种游戏提供样本和教学；导入后进入手动编辑，明确点击“提交存档修改”后保存。
- 谱面、成绩和曲绘关联用单一 SQLite 事务提交，失败回滚并清理本批次新曲绘。保存的曲绘为程序独立文件；源图删除后仍可读取。自定义 ID 与官方、其他存档隔离。
- 舞萌按线上 `catalog_active_release` schema 1 发现入口读取同一 revision 的数据。配套文件通过结构、版本和关联检查后切换本地指针，操作期间固定快照，缓存按版本目录分开。中二保留原有搜索及歌曲元数据路径。
- 支持独立公开投影目录和本地公开投影导出脚本，保留私有源文件。当前版本无变化时只检查发现入口，不重复创建版本目录。
- 本地诊断记录完整 stderr、实际命令、各轮编码尝试、退出码、Python 异常链、媒体属性和可取得的硬件信息。CPU MoviePy 编码、GPU 管道和 concat 均记录；手动查看、下载和确认后直接匿名上传，未配置地址时只提供下载。
- 启动器清空影响导入的外部 Python 设置，使用包内解释器、`-I -X utf8`、受控 `_pth` 和依赖来源预检。启动失败保存诊断；整合包不再回退向系统 Python 安装 Taichi。
- 转场规范化分辨率、SAR、像素格式、帧率和时间基准，缺音轨时补静音。编码器能力类失败只影响当前任务，输入/滤镜失败不永久缓存成硬件不可用。成品通过临时输出发布，失败保留旧文件；片段复用比较配置及输出文件属性，不计算 hash。

## 已有本地证据

| 范围 | 结果和证据 |
| --- | --- |
| 新功能测试 | `tests/test_release128.py` 在目标 Python 3.12.10 runtime 下通过 16 项测试，包括完整日志、进程启动/超时、真实本地 HTTP PUT/GET、403、上传超时、重试冲突、百分比与源 ID、公式缺失、列歧义、曲绘源删除、事务回滚、release 快照及独立公开投影 |
| 原相关回归 | 新功能 13 项与原运行时/主题测试合计 41 项通过；后续新增的公开投影、无变化版本和 HTTP 失败测试也分别在目标 runtime 验证 |
| Excel 原生页面 | `scripts/verify_release128_ui.py` 在独立应用中通过舞萌、中二的预览、草稿不写 DB、手动编辑、保存及重载；日志桶未配置时确认按钮禁用。文件运输由 AppTest 注入，解析和页面逻辑均运行真实代码 |
| Excel 真实浏览器 | 独立无头 Edge 通过实际文件选择、上传、预览、确认、保存和重载；两条记录在重载选择项中可见，页面无 JS 错误。证据为 `test_output/release128-browser/verification.json` 和截图 |
| Windows 启动 | 中文空格路径、其他工作目录以及注入 `PYTHONHOME/PYTHONPATH/PYTHONUSERBASE` 后，包内解释器和 `_distutils_hack` 来源正确。缺少 `_distutils_hack` 与 `_pth` 的实际最小损坏包均失败并生成启动诊断。证据为独立应用的 `release128-startup-verification.json` |
| 转场 FFmpeg | 混合尺寸、15/30fps、缺音轨的三段素材，libx264 和真实 NVENC 都生成可完全解码的视频；故意给 NVENC 无效参数后真实回退 libx264；损坏输入不覆盖旧成品。证据为 `test_output/release128-media-01/verification.json` |
| 完整 CPU/CUDA | 两种游戏在 CPU 和实际 Taichi CUDA/NVENC 路径生成 640×360 短成片；片头/片尾不同测试音频路由、短 BGM 循环、中二三模式六张图及片段配置变更均通过。证据为 `test_output/release128-theme-cpu-01`、`release128-theme-cuda-01` |
| 本地打包 | 应用和 runtime 从显式范围打包并实际解压到中文路径，关键依赖、模板、内置快照存在；解压后的包内预检通过。包不包含用户 DB、日志、凭据和存档，采用仓库默认渲染配置 |

`test_output/release128 中文 runtime` 是独立验收应用，使用合成用户和自己的数据库；`test_output/release128 解压验收` 用于真实解包预检。测试没有改动运行中的真实用户数据或线上 OSS 权限。

样本工作簿的两张表均使用 Artifact Tool 生成和渲染，导出的真实单元格通过 openpyxl 独立读取；源 ID `00001` 保留为字符串，舞萌 Excel 百分比 `1.005` 精确转换为 `100.5`。渲染器对文本数字的显示不作为单元格类型判断依据。

## 验证边界

本机真实硬件验证覆盖 NVIDIA NVENC 和 Taichi CUDA。其他厂商、其他驱动版本及 Linux/macOS 实机未在本轮覆盖；已有自动化后端回归继续通过。反馈用户的特定 Transition island/NVENC 根因仍需其完整报告，不能由本机成功推断全部设备已修复。

短成片的完整解码和音频频率检查是功能证据，不是长 B50 性能或真人主观音画同步验收。现有完整 GPU 音频均衡化结果仍可能有 AAC 尾部时长差，验收记录保留实际流时长。

舞萌采用现有 release 直接匿名读取，发现入口及配套 JSON 尚待权限修正和真实更新验收，不要求先上传公开投影。用户确认中二正式素材稍后补，当前底图、Logo 和默认 BGM 保留经授权的占位/兼容素材。素材补齐和实际网络操作见 [收尾操作](release_v1.2.8_closeout.md)。此前生成的本地 ZIP 为当时的验收快照，新的代码和配置需使用后续重打包的本地应用包。

以上为较早阶段状态；权限和资源已在下方最终收尾阶段完成验收。

## 2026-10-09 日志桶匿名只写联调

- 公共配置已填写 `https://nickbit-maigen-report-logs.oss-cn-shanghai.aliyuncs.com`，前缀 `reports`；不使用身份、密钥或签名参数。
- 客户端仅 PUT，同名 409 返回明确的冲突提示，不 GET、不覆盖，也不声称冲突对象内容已核对。当前会话成功提交后禁用重复提交；本地诊断包仍可下载。
- 当前代码的 47 项回归测试全部通过，覆盖只写 HTTP 服务、相同/不同内容冲突、上传被拒、服务器已接收但响应超时后的重试、页面确认/失败/成功/新会话冲突以及误配公共读取时拒绝验收并保存证据。输出为 `test_output/release128-write-only-regressions.txt`。独立应用的舞萌/中二保存重载和未配置桶时禁用提交也再次通过，记录为 `test_output/release128 中文 runtime/release128-ui-verification.json`。
- 真实 OSS 验收记录位于 `test_output/release128-network-405be7da38e84236b8782144ccd978f9/verification.json`：合成报告 PUT 成功；GET、HEAD、列举、删除本轮报告及前缀外 PUT 均为 403；同名重提为 409。
- 合成报告编号为 `20261009T034944-d6c8d9505f8e439f9cce25ab9e0f3773`，对象为 `reports/2026/10/09/20261009T034944-d6c8d9505f8e439f9cce25ab9e0f3773.zip`，首次请求编号为 `6AC8644FAB5F263233F402A6`。匿名删除被拒绝，该合成报告保留在桶内供维护者查看。
- PUT 回执证明服务器接受上传；本轮未使用维护者身份下载远端 ZIP 检查内容，也未验证生命周期、费用告警或不带禁止覆盖请求头时的服务器端覆盖限制。没有修改线上桶策略或其他用户报告。

## 2026-10-09 舞萌现有 JSON 匿名读取检查

`test_output/release128-metadata-access-f76d82eb0f2e431cbd313426c9e5910a/verification.json` 记录了实际请求：`metadata_json/mai_fusion_data.json` 返回 200；`metadata_json/active-release.json` 和旧路径 `metadata_json/asset-manifest.json` 返回 403，错误为 `AccessDenied`、`You do not have read permission on this object.`、`0003-00000005`。请求无签名、身份或密钥，不列举桶、不计算 hash。

当前不能确认发现索引里的 revision 及该版本三份文件的可读性和兼容性。权限修正后运行 `scripts/verify_release128_network.py --metadata` 继续验收。收尾说明已补充私有 Bucket + 指定 Object 公共读以及只读 Bucket Policy 两种设置方式，保留中二旧 JSON 路径。没有修改线上 ACL 或 Bucket Policy。

## 2026-10-09 更新本地应用包

当前应用 ZIP 为 `dist/release128-local-04/maigen_release_v1.2.8_local.zip`，包含 293 个分发文件、匿名只写日志代码/配置和现有 release 直接读取说明。runtime 未变，配套复用 `dist/release128-local-02/runtime_v1.2.8_windows_x64_local.zip`；本轮构建报告的 runtime 为 null，未声称创建新的 runtime ZIP。

新应用包已实际解压到独立验收应用。8 份关键源码、配置及说明与打包时源码直接比较字节一致，不计算 hash；包内启动预检通过，冲突处理类可导入，日志桶配置正确，`files_root` 为空，内置舞萌视频清单含 2613 条可用素材。包不包含用户数据库、日志、test_output 或 runtime。证据为 `dist/release128-local-04/package-verification.json`。这是本地代码收尾包，舞萌实网更新和正式中二素材验收未完成，不代表正式发布。

## 2026-10-09 最终收尾：等待人工验收

- 舞萌现役 release 为 `video-timeline-repair-20261008`：发现索引和三份配套 JSON 均为匿名 200；1607 首曲目、2840 条可用已审核视频来源。实网同版本只请求索引一次；模拟断网不改变完整指针；三条真实视频身份（含正式全角空格标题）精确匹配。证据：`test_output/release128-final-metadata-5e67a692b3b34c66a5a442a579bfee91/verification.json`。中二及旧版舞萌 JSON 路径也为 200。离线曲库和视频清单同步为该版本，并纳入分发。
- 日志桶本轮再次验证匿名 PUT 成功、GET/HEAD/列举/删除/前缀外写入为 403、同名重提为 409。证据：`test_output/release128-network-7fcbd87004d946deba1d54def742abee/verification.json`。本轮报告编号 `20261009T063853-44a25235d97b4e49a5aca60fcebc9ccc`，该合成报告留在桶内；远端 ZIP 内容仍需维护者登录下载核对。
- 新增 MATE 视频预设及暖黄配色：新 MATE 背景用于信息片段和内容动态背景，片头/片尾分别使用用户提供的 MATE MP3；成绩底图和标题层共用 Verse。Verse/X-Verse 使用用户补齐的独立 Verse 音乐配对。正式国服/MATE Logo 均为透明 RGBA；三预设 × 三模式共九张图已检查。
- 当前 51 项 unittest、19 项视频匹配 pytest 全部通过。覆盖真实 Windows 无共享删除句柄占用时的诊断文件发布重试；旧视频更新接口尊重显式目标/请求函数，默认调用仍使用成套 release；合法 `null` 作者规范为空字符串，正式 `「　」` 标题保留，普通空标题仍拒绝。测试依赖仅在 `test_output/release128-test-deps`，不进入 runtime。输出为 `test_output/release128-final-regressions.txt`、`release128-final-video-metadata-tests.txt`。
- 页面预设、MATE 音乐保存、三模式切换、实际生成图片和失败提示通过：`test_output/release128-final-theme-ui/verification.json`。
- CPU 和实际 Taichi CUDA/NVENC 均完成 Magical、Verse、X-Verse、MATE 四种完整短片；全部完整解码，440/880Hz 区分音频和循环路由验证通过；六个正式音乐片段与源音频相似度 CPU 最低 0.9753、CUDA 最低 0.9791。CUDA 有 42 次成功 NVENC 尝试、零失败尝试。证据：`test_output/release128-final-theme-cpu/verification.json`、`release128-final-theme-cuda-02/verification.json`。
- 自动视频样本为 640×360/30fps，不代表长 B50、1080p60、所有用户设备或全部 Bilibili 视频下载验收。原 ADVANCED `Frames/1.png` 缺口保留；既有难度框通过。人工检查列表见 `release_v1.2.8_closeout.md`。
- 本轮应用与 runtime 生成到 `dist/release128-manual-acceptance/`，文件名带 `manual`，构建状态为 `manual_acceptance_pending`。不推送远端、不部署；人工验收通过后再由用户决定发布。
- 最终包含 298 个应用文件及 10258 个 runtime 文件，已实际解压到 `test_output/release128 人工验收`；18 份关键源码、配置、正式素材和离线 JSON 直接比较字节一致。包内启动隔离及两种最小损坏 runtime 的失败诊断、实际页面 Excel 保存重载、日志配置恢复均通过。证据：`dist/release128-manual-acceptance/package-verification.json`。包不包含用户数据库、日志、上传资源或 pytest 测试依赖。
