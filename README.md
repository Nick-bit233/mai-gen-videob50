# mai-gen-videob50 DX.NET Extension

为[Nick-bit233/mai-gen-videob50](https://github.com/Nick-bit233/mai-gen-videob50)项目开发的DX NET国际服（理论上支持日服）兼容拓展插件。原README从[此处](#mai-gen-videob50)开始。

Extension for supporting DX NET International Ver. of repository 'Nick-bit233/mai-gen-videob50'. Original README starts from [here](#mai-gen-videob50).

## 简易使用说明

1. 打开maimai DX NET并进入B50查看页面（[国际服链接](https://maimaidx-eng.com/maimai-mobile/home/ratingTargetMusic/)）。等待歌曲信息加载完毕后，右键浏览器保存当前网页，将其中`.html`后缀文件移动至软件根目录下（于本文件相同文件夹内）。

- HTML文件的文件名大概率为`maimai DX NET－Music for DX RATING－.html`。如果保证同一路径下仅有一个HTML文件，则文件名不会影响程序的运行。

- 浏览器可能保存了一些其他文件（如图片等），您可以放心的删除这些文件。

1. 根据[原使用说明](#使用说明)的步骤继续使用。不同的是，在获取B50成绩时，请选择`从本地HTML读取B50`而非`从水鱼获取B50数据`。

## 插件特性

- 尽可能保留原仓库的.py文件，避免分支更新产生冲突

- （目前）使用保存的Rating对象乐曲网页作为B50信息的读取源，替代国服使用的水鱼查分器获取B50.

- 支持DX.NET国际服的网页信息解析。理论上支持日服，但是开发者没有日服账号无法测试。

## 开发状态与计划

- [x] 支持获取更多非国服乐曲的ID和定数；

- [ ] 为本插件录制一个简单的介绍视频。

- [ ] 改变成绩的获取来源，以获取DX score、FC等级、FS等级。

- [ ] 歌曲列表文件的自动更新同步；

- [ ] 优化B50的获取方式，避免保存网页的复杂操作；

## 引用

[maimaiDX-songs](https://github.com/Becods/maimaiDX-songs) 更新更热的歌曲数据库

本文件以下内容为 CST 2024 Dec 22 11:00 AM 时原仓库内README.md内容。

# mai-gen-videob50

自动从流媒体上搜索并构建你的舞萌DX B50视频

Auto search and generate your best 50 videoes of MaimaiDX

## 特性

本工具的原理是：

- 从查分器获取你的B50数据，并保存在本地。

- 从流媒体上搜索并下载谱面确认视频，并保存在本地。

- 用户（你）编辑视频里要展示的内容，包括片段长度、评论等。

- 自动根据已缓存的素材合成视频。

查分器源支持情况：

- [x] [水鱼查分器](https://www.diving-fish.com/maimaidx/prober/)：请注意在个人选项中允许公开获取你的B50数据。

- [ ] [落雪查分器](https://maimai.lxns.net/)（暂未支持）

流媒体源支持情况：

- [x] [youtube](https://www.youtube.com/)

- [x] [bilibili](https://www.bilibili.com/)

计划特性开发情况：

- [x] 可交互的全流程界面（streamlit）

- [ ] 更好的B50数据存档和更新覆盖确认

- [ ] 可自行筛选的特殊B50数据（如AP B50）

- [ ] （远期）支持中二B30视频生成

效果展示和教程请参考视频：

[【舞萌2024/工具发布】还在手搓b50视频？我写了一个自动生成器！](https://www.bilibili.com/video/BV1bJi2YVEiE)

## 当前生成效果预览

![alt text](md_res/image.png)

## 快速开始

- 如果你具有基本的计算机和python知识，可以独立（或者GPT辅助）完成环境配置和脚本操作，请直接clone仓库代码，参考[使用说明](#使用说明)开始使用!

- 如果你没有上述经验，请**从右侧Release页面下载最新的**打包版本，双击包内的`start.bat`文件启动应用使用。


## 使用说明

1. 安装python环境和依赖，推荐使用 `conda`。注意，python版本需要3.10以上。

    ```bash
    conda create -n mai-gen-videob50 python=3.10
    conda activate mai-gen-videob50
    ```

2. 从 requirements.txt 安装依赖

    ```bash
    pip install -r requirements.txt
    ```
    > 注意，如果你使用linux系统，在登陆b站过程中需要弹出tkinter窗口。而在linux的python没有预装`tk`库，请自行使用`sudo apt-get install python3-tk`安装。

3. 使用下面的命令启动streamlit网页应用

    ```
    streamlit run st_app.py
    ```
    在网页运行程序时，请保持终端窗口打开，其中可能会输出有用的调试信息。
    
注意，如果你使用youtube源且使用代理下载，你可能会遇到风控情况，此时请额外按照youtube的 po token生成相关依赖，具体请参考：[使用自定义OAuth或PO Token](UseTokenGuide.md)

---

### 如果你使用V3.0.0之前的老版本，请参考下面的旧版使用说明：

### 环境安装和准备工作

1. 推荐使用 `conda` 安装python环境和依赖

    ```bash
    conda create -n mai-gen-videob50 python=3.10
    conda activate mai-gen-videob50
    ```

2. 从 requirements.txt 安装依赖

    ```bash
    pip install -r requirements.txt
    ```
    > 注意，如果你使用linux系统，在登陆b站过程中需要弹出tkinter窗口。而在linux的python没有预装`tk`库，请自行使用`sudo apt-get install python3-tk`安装。

3. 安装必要的工具软件：

    请确保`ffmpeg`（用于视频的编码和解码）可以在你的系统命令行或终端中正常使用：

    - Windows:

        从 [CODEX FFMPEG](https://www.gyan.dev/ffmpeg/builds/) 下载 `ffmpeg-release-essentials.zip` 文件，解压文件到你的电脑上的任意目录后，将 `bin` 目录所在路径添加到系统环境变量中。

        > 如果你不了解如何配置系统环境变量，请自行搜索相关教程。配置完环境变量后需要重启终端方可生效
    
    - Linux:

        使用以下命令安装ffmpeg：

        ```bash
        sudo apt-get install -y ffmpeg
        ```
### 配置核心选项

找到 `global_congfig.yaml` 文件，修改：

-  `USER_ID` ：设置为你的查分器用户名

> 为了能抓取到精确的成绩信息，请在[舞萌 DX | 中二节奏查分器](https://www.diving-fish.com/maimaidx/prober/)中点击“编辑个人资料”，并取消勾选“对非网页查询的成绩使用掩码”。


-  `DOWNLOADER` ：设置下载器

    - `"bilibili"` ：使用bilibili下载器

    - `"youtube"` ：使用youtube下载器

-  `USE_PROXY` ：设置为是否启用网络代理，默认为`false`。

> 如果你位于中国大陆，并选择Youtube下载器，则你可能需要开启网络代理才可以正常使用，而bilibili下载器无需开启。如果你位于海外，则可能两级反转。

-  `HTTP_PROXY` 如果开启网络代理，将其设置为你的代理地址（如果你使用clash等代理工具，请设置为`"127.0.0.1:7890"`）。


### 测试系统的功能是否正常

运行 `test.py` ：

```bash
python test.py
```

下面是一个程序输出内容的参考。如果可以在`./videos/test`文件夹下获得一个`test_video.mp4`的17秒钟视频文件，则说明系统功能正常。

```
##### 开始系统功能测试...

## [1/4]测试网络代理配置...
当前代理设置: 127.0.0.1:7890
## [1/4]网络测试成功

## [2/4]测试图片生成功能...
## [2/4]图片生成测试成功

## [3/4]测试视频搜索和下载功能...
测试搜索结果: {'id': 'q26OmWO8ccg' ... 'duration': 174}
正在下载: 【maimai外部出力(60fps)】系ぎて Re:MAS AP
下载完成，存储为: 11663-4-DX.mp4
## [3/4]测试完毕

## [3/4]测试视频生成功能...
正在合成视频片段: intro_1
正在合成视频片段: NewBest_1
正在合成视频片段: ending_1
MoviePy - Building video videos/test/test_video.mp4 
...
MoviePy - Done !
MoviePy - video ready videos/test/test_video.mp4
## [4/4]视频生成测试成功
##### 全部系统功能测试完成！
```

如果未能正常执行测试，请对照[常见问题](#常见问题)一节检查。

如无法自行确认问题，可在[issue](https://github.com/teleaki/mai-gen-videob50/issues)中反馈，将错误输出粘贴帖子中（在发issue前请先搜索是否已有相同问题）。

### 其他参数配置

在 `global_congfig.yaml` 文件中，还可以修改以下配置：

- `DOWNLOAD_HIGH_RES` ：设置为是否下载高分辨率视频（开启后尽可能下载1080p的视频，否则最高下载480p的视频），默认为`true`。

> 注意：高分辨率视频有更高的下载失败率与合并失败率，如果网络状态不佳请修改为`false`。  

- `NO_BILIBILI_CREDENTIAL` ：使用bilibili下载器时，是否禁用bilibili账号登录，默认为`false`。

> 注意：使用bilibili下载器默认需要账号登录。不使用账号登录可能导致无法下载高分辨率视频，或受到风控

- `USE_CUSTOM_PO_TOKEN, USE_AUTO_PO_TOKEN, USE_OAUTH, CUSTOMER_PO_TOKEN` ：设置使用youtube下载器抓取视频时的额外验证Token。

>一般情况下无需修改，仅当需要绕过youtube风控时使用，请参考文档[使用自定义OAuth或PO Token](UseTokenGuide.md)。

- `SEARCH_MAX_RESULTS` ：设置搜索视频时，最多搜索到的视频数量。

- `SEARCH_WAIT_TIME` ：设置搜索视频时，每次搜索后等待的时间，格式为`[min, max]`，单位为秒。

- `VIDEO_RES` ：设置输出视频的分辨率，格式为`(width, height)`。

- `VIDEO_TRANS_ENABLE` ：设置生成完整视频时，是否启用视频片段之间的过渡效果，默认为`true`，会在每个视频片段之间添加过渡效果。

- `VIDEO_TRANS_TIME` ：设置生成完整视频时，两个视频片段之间的过渡时间，单位为秒。

- `USE_ALL_CACHE` ：生成图片和视频需要一定时间。如果设置为`true`，则使用本地已经生成的缓存，从而跳过重新生成的步骤，推荐在已经获取过数据但是合成视频失败或中断后使用。如果你需要从水鱼更新新的b50数据，请设置为`false`。

- `ONLY_GENERATE_CLIPS` ：设置为是否只生成视频片段，如果设置为`true`，则只会在`./videos/{USER_ID}`文件夹下生成每个b的视频片段，而不会生成完整的视频。

- `CLIP_PLAY_TIME` ：设置生成完整视频时，每段谱面确认默认播放的时长，单位为秒。

- `CLIP_START_INTERVAL` ：设置生成完整视频时，每段谱面确认默认开始播放的时间随机范围，格式为`[min, max]`，单位为秒。

### 完整B50视频生成操作流程

0. 配置好`global_congfig.yaml`文件，主要是配置下载器以及填写`USER_ID`为你的水鱼用户名。

    按照下面的步骤开始生成你的b50视频：

1. 运行`pre_gen.py`文件，程序将会自动查询您的最新b50数据，并抓取相关谱面确认视频。

    > 如果你使用的是bilibili下载器，并且没有禁用账号登录。首次运行将会弹出bilibili的登录二维码，请扫描二维码登录后继续。

    ```bash
    python pre_gen.py
    ```

    > 如果网络连接异常，请检查是否开启了使用代理，以及`HTTP_PROXY`是否配置正确。持续出现异常请参考[常见问题](#视频抓取相关)一节。

    > 视网络情况，通常抓取完整的一份b50视频素材的时间不定。如果在这一步骤期间遇到网络异常等问题导致程序中断，可以重新运行`pre_gen.py`文件，程序将会从上一次中断处继续执行。

2. 执行完毕后，将会弹出类似下图的浏览器页面：

    ![alt text](md_res/web_config.png)

    其中你可以预览已经生成的图片和抓取到的谱面预览视频。

    你需要填写：
    
    - 所有的评论文本框（请注意评论的长度，可换行，总长度在200字以内，过长可能导致超出屏幕）

    - 每条视频的开始时间和持续时间（在生成时已为你随机一个片段，你可以手动调整）

    **填写完毕后请务必点击页面底部的保存按钮！**

    > 你还可以手动请检查如下文件是否生成：

    > - 在`./b50_datas`文件夹下可以找到一个`video_config_{USER_ID}.json`文件

    > - 在`./b50_images/{USER_ID}`文件夹下可以找到所有生成的成绩图片，以`{PastBest/NewBest}_{id}.png`的格式命名。

    > - 在`./videos/downloads`文件夹下可以找到所有已下载的谱面确认视频，命名格式为`{song_id}-{level_index}-{type}.mp4`。其中，`song_id`为曲目的ID，`level_index`为难度，`type`为谱面类型，例如`834-4-SD.mp4`。

    如果你好奇的话，下面是配置文件的详细格式解释：

    > - "intro"和"ending"部分你填写的text会作为开头和结尾的文字展示。"main"部分填写的text为每条b50下的文字展示。

    > - 你输入的文字会根据模板长度自动换行，如果想要手动换行换行请使用`\n`，例如`aaa\nbbb`。

    > - 如果在一页的"intro"和"ending"部分想要展示的文字太多写不下，可以复制配置文件内容，修改为不同的id，以生成多页的intro和ending，例如：

    ```json
    "intro": [
        {
            "id": "intro_1",
            "duration": 10,
            "text": "【前言部分第一页】"
        },
        {
            "id": "intro_2",
            "duration": 10,
            "text": "【前言部分第二页】"
        }
    ],
    "ending": [
        {
            "id": "ending_1",
            "duration": 10,
            "text": "【后记部分第一页】"
        },
        {
            "id": "ending_2",
            "duration": 10,
            "text": "【后记部分第二页】"
        }
    ],
    ```
    - "main"的部分暂不支持多页文字。"main"部分的示例如下：

    ```json
    "main": [
        {
            "id": "NewBest_1",
            "achievement_title": "系ぎて-re:Master-DX",
            "song_id": 11663,
            "level_index": 4,
            "type": "DX",
            "main_image": "b50_images\\test\\PastBest_1.png",
            "video": "videos\\test\\11663-4-DX.mp4",
            "duration": 9,
            "start": 49,
            "end": 58,
            "text": "【请填写b50评价】\n【你只需要填写这条字符串】"
        },
    ]
    ```
    
    如果你在配置编辑页面浏览谱面预览视频的时候发现如下问题：

    - 视频对应的谱面确认和实际不符

    - 视频中谱面确认的画面没有位于视频的正中央（部分早期谱面可能出现此问题，因为往往只能抓取到到带有手元的视频）
    
    请考虑进行替换视频，你可以找到视频源文件，手动剪辑将外录的谱面确认部分移动至视频中央。请**保持视频的分辨率和比例均不变**（可以两边用黑色填充）。也可以直接去寻找其他谱面确认视频替换。

    - 如何找到下载视频的源文件位置：

        - 在`./videos/downloads/{USER_ID}`文件夹下缓存了所有下载的视频，每个视频会按照`曲目id-难度阶级-类型（SD或DX）.mp4`的格式命名，可以对照`video_config_{USER_ID}.json`文件里的`video`字段检查。
    
        - 替换视频时，请保证视频的文件名不变。

3. 检查完毕无误后，你可以关闭浏览器和之前运行程序的终端窗口。然后重新启动一个终端窗口运行`main_gen.py`文件，程序将会依照已编辑的配置生成完整的视频（或每组视频片段）。

    ```bash
    python main_gen.py
    ```

    > 合并完整视频的时间取决于你设置的预览时长和设备的性能，在每个片段15s的情况下，生成完整视频大概需要30-40分钟。

## 常见问题

### 安装环境相关

- 出现`ModuleNotFoundError: No module named 'moviepy'`等报错

    请检查你是否已经配置好3.8版本以上的python环境，并安装了`requirements.txt`中的所有依赖。

- 出现类似如下的报错：

    ```
    OSError: [WinError 2] The system cannot find the file specified

    MoviePy error: the file 'ffmpeg.exe' was not found! Please install ffmpeg on your system, and make sure to set the path to the binary in the PATH environment variable
    ```

    请检查你的python环境和`ffmpeg`是否安装正确，确保其路径已添加到系统环境变量中。

### 视频抓取相关

- 网络链接问题，例如：

    ```
    [WinError 10060] 由于连接方在一段时间后没有正确答复或连接的主机没有反应，连接尝试失败。
    ```

    请检查网络连接。如果你使用代理，请检查是否在启用了`USE_PROXY`的情况下没有打开代理，或代理服务是否正常。

- 下载视频过程中出现RemoteProtocolError或SSLEOFError异常：

    ```
    httpx.RemoteProtocolError: peer closed connection without sending complete message body
    ```

    ```
    <urlopen error [Errno 2] No such file or directory>
    ```

    ```
    ssl.SSLEOFError: EOF occurred in violation of protocol (_ssl.c:2423)
    ```

    请重启脚本，从断点处重新执行。

- 使用youtube下载器，搜索和下载视频期间出现如下错误：

    ```
    This request was detected as a bot. Use use_po_token=True to view. 
    ```
    说明你使用的ip地址可能被youtube识别为机器人导致封禁，最简单的办法是尝试更换代理ip后重试。

    如果更改代理仍然无法解决问题，请尝试配置`PO_TOKEN`或`OAUTH_TOKEN`后抓取视频，这部分需要额外的环境配置和手动操作，请参考[使用自定义OAuth或PO Token](UseTokenGuide.md)。

### 视频生成相关

- 生成视频最后出现如下错误：

    ```
    if _WaitForSingleObject(self._handle, 0) == _WAIT_OBJECT_0:
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    OSError: [WinError 6] 句柄无效。
    ```

    这是因为ffmpeg没有正常关闭视频文件导致的，但该问题不影响最终视频生成，可以忽略。

## 鸣谢

- [舞萌 DX 查分器](https://github.com/Diving-Fish/maimaidx-prober) 提供数据库及查询接口

- [Tomsens Nanser](https://space.bilibili.com/255845314) 提供图片生成素材模板以及代码实现

- [bilibili-api](https://github.com/Nemo2011/bilibili-api) 