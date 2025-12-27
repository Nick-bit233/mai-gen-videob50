<img src="md_res/icon.png" width="256" alt="Icon">

# mai-gen-videob50(+chu) 分表视频生成器

自动从流媒体上搜索并构建你的舞萌DX / 中二节奏 Best分表视频

Auto search and generate your best videos of MaimaiDX / Chunithm

## 更新速览

`v1.0 (beta test)` 版本现已更新：
- ✨ **重大更新**：现已支持中二节奏（CHUNITHM）B30视频生成！您可以从落雪查分器获取中二节奏数据
    - 中二节奏B30功能已完善，支持完整的视频生成流程
    - 支持从落雪查分器CSV备份文件导入游玩次数数据
- 🛠️ 数据库重构：使用本地Sqlite3数据库替换原基于文件的数据存储系统，在调取资源时更加灵活，并兼容分表数据的未来更新
    - 支持数据库版本管理和自动迁移
    - 提供完整的数据管理功能，包括数据清空和存档管理
- 🎮 界面更新：统一的视频生成流程，根据游戏类型自动切换显示 B30（中二侧）或 B50（maimai侧）
    - 支持在首页一键切换游戏类型
    - 根据游戏类型自动切换主题配色
- 🔍 搜索优化：支持 YouTube Data API v3，并优化更加快捷的手动搜索流程
- 📥 **新增下载器**：引入 yt-dlp 作为 YouTube 视频下载的另一种选择，提供更稳定的下载体验，减少风控问题
- ⚡ **GPU硬件加速**：支持 NVIDIA (CUDA + NVENC)、AMD (AMF)、Intel (Quick Sync Video) 三种硬件加速方案
    - 可显著提升视频渲染速度，分担 CPU 负载
    - 在合成视频页面可选择启用硬件加速
- 🚀 **快速生成模式**：新增分批处理和快速拼接模式
    - 分批处理模式可降低内存占用，适合处理大量视频片段
    - 快速拼接模式可大幅减少生成时间，适合快速预览
- 📝 自定义存档：新增"编辑数据/创建自定义数据"功能，支持手动创建和编辑分表数据
    - 支持拖拽排序、搜索添加歌曲、批量编辑等功能
- 🎨 **画面生成完善**：优化视频合成和画面渲染逻辑
    - 改进视频片段合成算法，提升画面质量
    - 优化内存管理，支持大批量视频生成
    - 改进过渡效果处理，提供更流畅的视频衔接
- 🐛 界面优化：优化前端界面，改进分表填写和媒体处理逻辑，提升用户体验

我们经过短暂测试后将提供release包，目前请使用源代码安装。无需更新runtime，可以直接替换v0.6.5版本的所有源代码

> 本预览版本的中二落雪查分器支持，以及YouTube Data API v3和yt-dlp下载器，部分界面重构支持，画面优化由[caiccu](https://github.com/CAICCU)提供，GPU硬件加速及快速生成由 [〖天蓝〗](https://github.com/MetallicAllex)提供

目前预览版的中二生成支持可能存在问题，如果您需要制作中二分表，请移步由 [〖天蓝〗](https://github.com/MetallicAllex) 修改的 [chu-gen-videob30](https://github.com/MetallicAllex/chu-gen-videob30/tree/get_userdata_FC)

---

`v1.0 (alpha test)` 预览版本现已更新：
- ✨ **重大更新**：现已支持中二节奏（CHUNITHM）B30视频生成！您可以从水鱼查分器和落雪查分器获取中二节奏数据
    - 中二节奏的自定义分表和国际服数据查询还在施工中，目前可能无法正常工作
- 🛠️ 数据库重构：使用本地Sqlite3数据库替换原基于文件的数据存储系统，在调取资源时更加灵活，并兼容分表数据的未来更新
- 🎮 界面更新：统一的视频生成流程，根据游戏类型自动切换显示 B30（中二侧）或 B50（maimai侧）
- 🔍 搜索优化：支持 YouTube Data API v3，并优化更加快捷的手动搜索流程
- 🐛 界面优化：优化前端界面，改进分表填写和媒体处理逻辑，提升用户体验

`v0.6.5`版本更新：
- 修复：从舞萌2025版本，成绩图片中的等级+号显示，由每个等级的定数.7及以上调整为.6及以上
- 修复：自动识别下载的视频源以对齐模板的位置，以避免视频没有嵌入到正确位置的问题。


## 快速开始

- 对于大多数无编程基础的用户，请**从右侧Release页面下载最新的**打包版本。
- 注意！从`v0.5-beta`版本开始，运行环境包已经和本体分离，要启动应用，请进行以下操作：
    - 下载本体Release包和运行环境包（`runtime_v<版本号>.zip`），并解压
    - 将运行环境包中的**全部文件**，复制到本体Release包解压后的目录
    - 双击`start.bat`文件启动应用。
    - 请不要使用旧版本的runtime运行环境，其缺少新版本的依赖
- 请注意：**打包版本仅支持Windows10及以上操作系统**
- 首次启动时，如果没有立刻弹出浏览器窗口，请检查控制台，如果要求输入Email，请直接回车跳过即可。
- 遇到问题请参考[常见问题](#常见问题)一节。

> 如果你具有基本的计算机和python知识，可以独立（或者GPT辅助）完成环境配置和脚本操作，可以直接clone仓库代码，参考[使用说明](#使用说明（从源代码启动）)部分开始使用。

## 效果预览

- 用户界面（支持主题换色）

| ![alt text](md_res/page_fes.png) | ![alt text](md_res/page_bud.png) | ![alt text](md_res/page_pri.png) |
|:---:|:---:|:---:|
| FES | BUD | PRI |

生成视频效果展示：[【舞萌2024/工具发布】还在手搓b50视频？我写了一个自动生成器！](https://www.bilibili.com/video/BV1bJi2YVEiE)


中二节奏生成效果：[【中二节奏2026】小伙入坑四个月在12月25日b30成功抵达16.25，特此纪念](https://www.bilibili.com/video/BV1vBB6BAE3z)

使用教程视频：[【舞萌2024】新版B50视频生成器来啦！支持一键启动/站内下载/全面升级用户界面~](https://www.bilibili.com/video/BV1G2kBY5Edq)



- 生成视频帧效果

<img src="md_res/image.png" width="600" alt="preview">


## 特性

本工具的原理是：

- 从查分器获取你的B50/B30数据，并保存在本地。

- 从流媒体上搜索并下载谱面确认视频，并保存在本地。

- 用户（你）编辑视频里要展示的内容，包括片段长度、评论等。

- 自动根据已缓存的素材合成视频。

### 支持的游戏类型

- **B50（maimai侧）**：舞萌DX Best 50 视频生成
- **B30（中二侧）**：中二节奏 Best 30 视频生成

### 查分器源支持情况

#### maimai（B50）数据源：
- [x] [水鱼查分器](https://www.diving-fish.com/maimaidx/prober/)：请注意在个人选项中关闭掩码，并允许公开获取你的B50数据。

- [x] [国际服Maimai DX NET](https://maimaidx-eng.com/maimai-mobile/home/ratingTargetMusic/)

- [x] [日服Maimai DX NET](https://maimaidx.jp/maimai-mobile/home/ratingTargetMusic/) (缺乏测试样本)

- [x] [DXrating](https://dxrating.net/rating)：支持国服/国际服/日服

    （国际服/日服官网以及DXrating网站导入数据需要通过下载网页或导出源码，点此查看[国际服/日服数据获取插件使用教程](docs/DX_NET_Guide.md)）

#### chunithm（B30）数据源：
- [x] [落雪查分器](https://maimai.lxns.net/)：支持中二节奏B30数据获取

### 流媒体源支持情况：

- [x] [youtube](https://www.youtube.com/)：支持 YouTube Data API v3 和 pytubefix 两种搜索方式

- [x] [bilibili](https://www.bilibili.com/)

### 已实现特性：

- [x] 可交互的全流程界面（streamlit）

- [x] 支持一键更换页面主题配色

- [x] 更好的B50/B30数据存档系统，可以保存多个历史副本

- [x] 支持自行筛选的B50/B30数据、自定义视频生成的列表（支持从水鱼自动获取AP B50）

- [x] 支持自定义视频背景图片、字体和字号等个性化功能

- [x] 支持中二节奏B30视频生成

- [x] 多策略视频搜索系统，智能匹配最相关的谱面视频

- [x] 自动处理歌曲名称中的特殊字符，提高搜索准确率

- [x] 改进视频预览错误处理，自动处理媒体文件存储错误

### 计划特性：

- [ ] 支持音击B45视频生成

---

## 使用说明（从源代码启动）

1. 安装python环境和依赖，推荐使用 `conda`。注意，python版本需要3.10以上。

    ```bash
    conda create -n mai-chu-gen-video python=3.10
    conda activate mai-chu-gen-video
    ```

2. 从 requirements.txt 安装依赖

    ```bash
    pip install -r requirements.txt
    ```
    > 注意，如果你使用linux系统，在登陆b站过程中需要弹出tkinter窗口。而在linux的python没有预装`tk`库，请自行使用`sudo apt-get install python3-tk`安装。

3. 安装ffmpeg（如果从Release包中下载，则无需此步骤）：

    - Windows:

        从 [CODEX FFMPEG](https://www.gyan.dev/ffmpeg/builds/) 下载 `ffmpeg-release-essentials.zip` 文件，解压文件到你的电脑上的任意目录后，将 `bin` 目录所在路径添加到系统环境变量中。

    - Linux:

        使用`sudo apt-get install ffmpeg`安装ffmpeg。

4. 使用下面的命令启动streamlit网页应用

    ```bash
    streamlit run st_app.py
    ```
    在网页运行程序时，请保持终端窗口打开，其中可能会输出有用的调试信息。

5. 在浏览器中打开应用后，你可以看到左侧导航栏分为：
   - **首页**：应用主页，包含系统状态和主题设置，可在首页切换游戏类型（B30/B50）
   - **视频生成**：统一的视频生成流程，根据当前选择的游戏类型自动显示 B30（中二节奏）或 B50（舞萌DX）相关功能（获取/管理数据、生成图片、搜索视频、编辑视频、合成视频等）

#### 其他注意事项

- **YouTube搜索配置**：
  - 推荐使用 YouTube Data API v3 进行搜索（更稳定可靠）
  - 在"搜索谱面确认视频信息"页面，勾选"使用 YouTube Data API v3 搜索"并填入你的 API Key
  - 如果没有 API Key，也可以使用传统的 pytubefix 方式，但可能遇到风控问题
  - 如果使用 pytubefix 且遇到风控，请参考：[使用自定义OAuth或PO Token](docs/UseTokenGuide.md)

- **数据源配置**：
  - 如果你使用国际服/日服，或使用DXrating网站作为B50数据源，在使用前请参考：[导入国际服/日服B50数据](docs/DX_NET_Guide.md)完成前置数据获取步骤。
  - 对于中二节奏B30，推荐使用落雪查分器获取数据。

---

## 常见问题

### 安装环境相关

- 出现`ModuleNotFoundError: No module named 'moviepy'`等报错

    请检查你是否已经配置好3.10版本以上的python环境，并安装了`requirements.txt`中的所有依赖。

- 出现类似如下的报错：

    ```
    OSError: [WinError 2] The system cannot find the file specified

    MoviePy error: the file 'ffmpeg.exe' was not found! Please install ffmpeg on your system, and make sure to set the path to the binary in the PATH environment variable
    ```

    请检查你的python环境和`ffmpeg`是否安装正确，确保其路径已添加到系统环境变量或项目根目录中。

### 视频抓取相关

- 搜索视频步骤中，扫码登录后出现如下报错：

    <img src="md_res/qa_6.jpg" width="400" alt="qa6">

    请检查任务栏是否有未关闭的二维码扫描窗口，如果有，关闭该窗口后尝试重新开始搜索。如果弹出了新的二维码窗口请重新扫描登陆。如果没有，请尝试重新整个程序重试。

- 搜索和下载视频时出现大量失败信息：

    <img src="md_res/qa_5.jpg" width="400" alt="qa5">

    这通常意味着您的网络环境在调用api时遇到风控问题。请查看控制台是否有有如下输出。

    - 使用youtube下载器时，被风控将输出如下错误：

    ```
    This request was detected as a bot. Use use_po_token=True to view. 
    ```
    说明你使用的ip地址可能被youtube识别为机器人导致封禁，最简单的办法是尝试更换代理ip后重试。

    如果更改代理仍然无法解决问题，请尝试配置`PO_TOKEN`或`OAUTH_TOKEN`后抓取视频，这部分需要额外的环境配置和手动操作，请参考[使用自定义OAuth或PO Token](UseTokenGuide.md)。

    - 使用bilibili下载器时，被风控将输出如下错误：

    ```
    搜索结果异常，请检查如下输出：'v_voucher': 'voucher_xxxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx'
    ```
    说明你未使用bilibili账号登录，或登录后遭到风控。

    请尝试登陆账号、更换网络运营商（ISP）后重试。若仍出现此问题，目前没有较好的解决办法，请考虑等待24h后再试。

- 网络链接问题

    下载视频过程中出现RemoteProtocolError或SSLEOFError异常，或http超时报错：

   - RemoteProtocolError
    ```
    httpx.RemoteProtocolError: peer closed connection without sending complete message body
    ```
    - SSLEOFError / urlopen error

    ```
    <urlopen error [Errno 2] No such file or directory>
    ```

    ```
    ssl.SSLEOFError: EOF occurred in violation of protocol (_ssl.c:2423)
    ```

    通常只是网络波动，重新尝试搜索/下载即可。

- 下载视频期间未报错，但是没有视频文件：
  
    - 请检查ffmpeg环境是否正确配置。

- 手动输入视频BV号或ID进行搜索时出现红色报错：

    - 从v0.5.1版本开始，请使用完整的bv号获取视频，如果视频号无效请按照报错说明调整输入。

### 配置填写相关

- Q：加载页面4-1时，已经生成和图片和下载的视频没有正常显示

    请检查是否完成了第1-3步中的图片生成以及视频下载等全步骤。
    
    如果确认已经完成并可以在本地文件夹中找到图片和视频，则按照以下步骤操作：

    - 进入页面下方`额外设置和配置文件管理` 中的 `危险区域`一栏
    - 点击`强制刷新视频配置文件`按钮

    （注意：此操作将会重置你已经填写的所有评论，如果你在还未填写任何评论的时候遇到该问题，可以进行该操作。否则，请参考下一问）

    <img src="md_res/qa_2.png" width="500" alt="qa2">

- Q：视频预览时出现 "MediaFileStorageError" 或 "No media file with id" 错误

    这通常是由于 Streamlit 的媒体文件引用失效导致的，可能的原因包括：
    - 文件路径在会话之间发生变化
    - 文件被移动或删除后，旧的引用仍然存在
    - Streamlit 的媒体文件缓存过期

    解决方法：
    - **刷新页面**：最简单的方法是刷新当前页面，让 Streamlit 重新加载媒体文件
    - **重新加载存档**：如果刷新无效，请返回首页重新加载存档
    - **检查文件路径**：确认视频文件确实存在于本地，且路径正确
    - **重新下载视频**：如果文件确实丢失，请返回第3步重新下载视频

    从 `v0.8` 版本开始，系统已自动处理此类错误，并会显示友好的提示信息。


- Q：我先填写了部分评论，但是后来B50/B30数据更新了，怎么更新评论？

    视频配置信息不会随B50/B30数据的更新而自动更新，建议推分后建立一个新的存档。如果确实需要复制部分旧存档的评论，请参考如下步骤：

    - 首先新建存档更新数据，在第1-3步将你的B50/B30数据和视频搜索数据都更新到最新。

    - 保持当前编辑的页面不动，复制浏览器中的地址，打开一个新的页面，以加载历史存档。
    
    - 进入页面4-1并对比两个页面的信息以复制粘贴评论内容，手动还原评论和时长配置

- Q：我不小心更新了B50/B30数据，但是我还想要使用旧的数据生成视频

    - 如果您使用的是`v0.4.0`以上的版本，每次更新数据（强制覆盖除外）将会自动新建存档，只需在首页加载历史存档继续编辑即可。
    

### 视频生成相关

- Q：视频生成过程中中断，并提示无法读取某视频文件

    ```
    ffmpeg_read: ...\videos\downloads\xxx-x-xx.mp4, 3 bytes wanted but 6 bytes read at frame index 0 (ouf of a total of xx frames) 0.00 sec, Using the last valid frame instead.
    ```

    请检查错误信息中输出的视频名称（如`xxxx-x-xx.mp4`），在`./videos/downloads`文件夹下检查是否存在该文件，且该视频是否可以正常播放。

    如果该视频无法播放，可能意味着下载过程中视频损坏。请删除该视频文件，重新进入第3步下载。
    
    如果重新下载后依然得到损坏的视频，那么该视频的在线媒体流可能存在问题，请考虑回到第2步，更换其他链接源。
    
    > 亦可手动获取对应的正确视频，替换到`./videos/downloads`文件夹下，请注意保持文件名一致。

- Q：**视频生成过程中中断，报错中出现如下内存错误**

    <img src="md_res/qa_4.jpg" width="500" alt="qa4">

    ```
    _ArrayMemoryError: Unable to allocate xxx MiB for an array with shape (xxx, xxx, 3) and data type float64
    ```

    这通常是由于ffmpeg没有被分配足够的内存导致的，由于完整生成模式需要一次缓存约50段视频的图像张量，且默认分辨率为高清，部分设备可能会出现内存瓶颈。

    请考虑：
    
    - 清理系统运行内存，关闭暂时不使用的后台程序后重试。
    - 缩减片段的预览时长，或降低视频分辨率（不推荐，可能导致文字错位）。
    - 增加系统的虚拟内存（请参考：[如何设置虚拟内存](https://www.bilibili.com/video/BV1a142197a9)），建议可以调整至32GB以上。

- Q：视频生成速度缓慢

    合并完整视频的时间取决于你设置的预览时长和设备的性能，在每个片段10s的情况下，生成完整视频大概需要60-100分钟。
    
    从 `v1.0 (beta test)` 版本开始，已支持 GPU 硬件加速渲染，可显著提升生成速度：
    - 在"合成视频"页面勾选"使用 GPU 硬件加速"
    - 根据您的显卡选择对应的加速方案（NVIDIA/AMD/Intel）
    - 如果 GPU 加速失败或效果不明显，可回退到 CPU 软件编码
    
    如果设备性能不佳，请考虑：
    - 启用 GPU 硬件加速（如果支持）
    - 使用快速生成模式（分批处理）
    - 缩减视频时长，或降低视频分辨率（不推荐，可能需要手动调整字号以防止文字错位）


- Q：生成视频最后出现如下控制台错误

    ```
    if _WaitForSingleObject(self._handle, 0) == _WAIT_OBJECT_0:
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    OSError: [WinError 6] 句柄无效。
    ```

    这是因为ffmpeg没有正常关闭视频文件导致的，但该问题不影响最终视频生成，可以忽略。

---

## 参数与配置文件结构

如果你有兴趣贡献本仓库，或是希望了解本工具的详细结构，请参考以下内容。

### 全局应用参数的解释

在 `global_congfig.yaml` 文件可更改本应用的所有外部配置：

- `DOWNLOAD_HIGH_RES` ：设置为是否下载高分辨率视频（开启后尽可能下载1080p的视频，否则最高下载480p的视频），默认为`true`。

- `NO_BILIBILI_CREDENTIAL` ：使用bilibili下载器时，是否禁用bilibili账号登录，默认为`false`。

    > 注意：使用bilibili下载器默认需要账号登录。不使用账号登录可能导致无法下载高分辨率视频，或受到风控

- `USE_CUSTOM_PO_TOKEN, USE_AUTO_PO_TOKEN, USE_OAUTH, CUSTOMER_PO_TOKEN` ：设置使用youtube下载器抓取视频时的额外验证Token。

    > 请参考文档[使用自定义OAuth或PO Token](UseTokenGuide.md)。

- `USE_YOUTUBE_API` ：是否使用 YouTube Data API v3 进行搜索，默认为`false`。推荐设置为`true`以获得更稳定的搜索体验。

- `YOUTUBE_API_KEY` ：YouTube Data API v3 的 API Key。如果`USE_YOUTUBE_API`为`true`，需要填写此字段。

- `SEARCH_MAX_RESULTS` ：设置搜索视频时，最多搜索到的视频数量。

- `SEARCH_WAIT_TIME` ：设置搜索和下载视频时，每次调用API后等待的时间，格式为`[min, max]`，单位为秒。

- `VIDEO_RES` ：设置输出视频的分辨率，格式为`(width, height)`。

- `VIDEO_TRANS_ENABLE` ：设置生成完整视频时，是否启用视频片段之间的过渡效果，默认为`true`，会在每个视频片段之间添加过渡效果。

- `VIDEO_TRANS_TIME` ：设置生成完整视频时，两个视频片段之间的过渡时间，单位为秒。

- `USE_ALL_CACHE` ：生成图片和视频需要一定时间。如果设置为`true`，则使用本地已经生成的缓存，从而跳过重新生成的步骤，推荐在已经获取过数据但是合成视频失败或中断后使用。如果你需要从水鱼更新新的b50数据，请设置为`false`。

- `ONLY_GENERATE_CLIPS` ：设置为是否只生成视频片段，如果设置为`true`，则只会在`./videos/{USER_ID}`文件夹下生成每个b的视频片段，而不会生成完整的视频。

- `CLIP_PLAY_TIME` ：设置生成完整视频时，每段谱面确认默认播放的时长，单位为秒。

- `CLIP_START_INTERVAL` ：设置生成完整视频时，每段谱面确认默认开始播放的时间随机范围，格式为`[min, max]`，单位为秒。


## 鸣谢

- [舞萌 DX 查分器](https://github.com/Diving-Fish/maimaidx-prober) 提供数据库及查询接口

- [落雪查分器](https://maimai.lxns.net/) 提供中二节奏数据接口

- [Tomsens Nanser](https://space.bilibili.com/255845314) 提供图片生成素材模板以及代码实现

- [bilibili-api](https://github.com/Nemo2011/bilibili-api)

---

