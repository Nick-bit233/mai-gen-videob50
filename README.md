# mai-gen-videob50

自动从流媒体上搜索并构建你的舞萌DX B50视频

Auto search and generate your best 50 videoes of MaimaiDX

## 快速开始

想要一键（几乎）自动地生成你的B50视频？参考你是否符合以下条件：

- 你拥有一个[水鱼查分器](https://www.diving-fish.com/maimaidx/prober/)账号，并允许公开获取你的B50数据

- 你的网络环境可以正常访问[Youtube](https://www.youtube.com/)

> 由于目前的谱面确认视频获取方法为从Youtube上抓取，你可能需要开启网络代理🪜才可以正常使用，造成的不便敬请谅解（请放心生成器只抓取360p的预览视频，因此对网络速度和流量的要求很低）。

> 我们正在考虑后续开发抓取B站的可选项，敬请期待。

- 你具有基本的计算机知识，可以按照说明（或GPT辅助）完成python脚本操作

如果一切OK，请参考[使用说明](#使用说明)开始生成你的B50视频!

效果展示和教程请参考视频：

[【舞萌2024/工具发布】还在手搓b50视频？我写了一个自动生成器！](https://www.bilibili.com/video/BV1bJi2YVEiE)

## 当前生成效果预览

![alt text](md_res/image.png)

## 使用说明

### 环境安装和准备工作

1. 推荐使用 `conda` 安装python环境和依赖（可选）

    ```bash
    conda create -n mai-gen-videob50 python=3.10
    conda activate mai-gen-videob50
    ```

2. 从 requirements.txt 安装依赖

    ```bash
    pip install -r requirements.txt
    ```

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

### 测试系统的功能是否正常

运行 `test.py` ：

```bash
python test.py
```

如果程序输出以下内容，并可以在`./videos/test`文件夹下获得一个`test_video.mp4`的17秒钟视频文件，则说明系统功能正常。

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

### 相关参数配置

在 `global_congfig.yaml` 文件中，配置以下信息：

- `USER_ID` ：设置为你的水鱼用户ID。

- `USE_PROXY` ：设置是否启用网络代理，如果设置为`true`，则启用代理，否则不启用。

- `HTTP_PROXY` 如果开启网络代理，将其设置为你的代理地址（如果你使用clash等代理工具，请设置为`"127.0.0.1:7890"`）。

    > 为了能抓取到精确的成绩信息，请在[舞萌 DX | 中二节奏查分器](https://www.diving-fish.com/maimaidx/prober/)中点击“编辑个人资料”，并取消勾选“对非网页查询的成绩使用掩码”。

- `USE_CUSTOM_PO_TOKEN, USE_AUTO_PO_TOKEN, USE_OAUTH, CUSTOMER_PO_TOKEN` ：设置抓取视频时的额外验证Token，一般情况下无需修改，特殊情况请参考文档[使用自定义OAuth或PO Token](UseTokenGuide.md)。

- `SEARCH_MAX_RESULTS` ：设置为从youtube上搜索视频时，最多搜索到的视频数量。

- `SEARCH_WAIT_TIME` ：设置从youtube上搜索视频时，每次搜索后等待的时间，格式为`[min, max]`，单位为秒。

- `VIDEO_RES` ：设置输出视频的分辨率，格式为`(width, height)`。

- `VIDEO_TRANS_ENABLE` ：设置生成完整视频时，是否启用视频片段之间的过渡效果，默认为`true`，会在每个视频片段之间添加过渡效果。

- `VIDEO_TRANS_TIME` ：设置生成完整视频时，两个视频片段之间的过渡时间，单位为秒。

- `USE_ALL_CACHE` ：生成图片和视频需要一定时间。如果设置为`true`，则使用本地已经生成的缓存，从而跳过重新生成的步骤，推荐在已经获取过数据但是合成视频失败或中断后使用。如果你需要从水鱼更新新的b50数据，请设置为`false`。

- `ONLY_GENERATE_CLIPS` ：设置为是否只生成视频片段，如果设置为`true`，则只会在`./videos/{USER_ID}`文件夹下生成每个b的视频片段，而不会生成完整的视频。


### 完整B50视频生成操作流程

0. 配置好`global_congfig.yaml`文件，主要是配置代理以及填写`USER_ID`为你的水鱼用户名。

    按照下面的步骤开始生成你的b50视频：

1. 运行`pre_gen.py`文件，程序将会自动查询您的最新b50数据，并抓取相关谱面确认视频。

    ```bash
    python pre_gen.py
    ```

    > 如果网络连接异常，请检查`global_congfig.yaml`文件中`HTTP_PROXY`是否配置正确。持续出现异常请参考[常见问题](#视频抓取相关)一节。

    > 视网络情况，通常抓取完整的一份b50视频素材需要30-60分钟。如果在这一步骤期间遇到网络异常等问题导致程序中断，可以重新运行`pre_gen.py`文件，程序将会从上一次中断处继续执行。

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

- urlopen error或SSLEOFError异常：

    ```
    <urlopen error [Errno 2] No such file or directory>

    ssl.SSLEOFError: EOF occurred in violation of protocol (_ssl.c:2423)
    ```

    请重启脚本，从断点处重新执行。

- 搜索和下载视频期间出现如下错误：

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
