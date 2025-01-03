# 导入国际服B50 For DX.NET Extension

> 暂不适用于日服。

## 快速使用说明

进入DX NET的Rating对象乐曲页面，复制HTML源代码备用；按照应用页面引导操作，注意在应用内导入B50时选择`导入B50数据源代码（国际服）`并粘贴。

## 如何获取国际服数据的HTML源代码

1. 打开[国际服Maimai DX NET](https://maimaidx-eng.com/maimai-mobile/home/ratingTargetMusic/)并进入Rating对象乐曲页面。

2. 等待页面加载完毕后，按`Ctrl + U` 或 右键>>点击`查看网页源代码`。在新打开或跳转至的页面中，全选复制所有内容备用。

3. 根据[使用说明](../README.md/#使用说明)的步骤继续使用。在应用内获取B50时，选择`导入B50数据源代码`，然后根据指引将`2.`中复制的内容粘贴到指定输入框内，并点击确定保存。之后，选择`从本地HTML读取B50（国际服）`完成数据读取。

   - 若如此做，程序会为您保存一个`{用户名}.html`文件用于后续数据处理，这是正常现象。您可以在B50读取结束后删除该文件。

## 插件特性

- 尽可能保留原仓库的.py文件，避免分支更新产生冲突

- （目前）使用保存的Rating对象乐曲网页作为B50信息的读取源，替代国服使用的水鱼查分器获取B50.

- 支持DX.NET国际服的网页信息解析。但是日本人太坏了，同样的功能在日服收费，暂时做不了日版适配。

## 开发状态与计划

- [x] 支持获取更多非国服乐曲的ID和定数；

- [x] 支持更灵活的上传HTML数据；

- [ ] 为本插件录制一个简单的介绍视频；

- [ ] 改变成绩的获取来源，以获取DX score、FC等级、FS等级；

- [ ] 歌曲列表文件的自动更新同步。

## 常见问题

- 报错`Error: No HTML file found in the root folder.`

请检查是否正确保存了您的HTML数据。如果您手动保存了网页，请检查是否正确的放置在软件根目录。

- 报错`Error: B35(B15) not found. 请检查HTML文件是否正确保存！`

请检查查看源代码的网页是否是DX Rating对象乐曲界面。在乐曲加载完毕之前操作也可能导致这个问题。
> 如果您是日服玩家，这是DX.NET语言不适配导致的。

- 下载视频后许多谱面都指向同一个`None-3-DX.mp4`（或相似的以None开头的名称）

这是一个在`v0.3.3`版本的常见问题，原因是太新的曲目并没有一个内部id，请更新到更新版本。

- 显示`已找到谱面视频的缓存`，但是不是正确的谱面

如果显示的缓存视频名称结构为`-XX-Y-DX.mp4`，例如`-39-3-DX.mp4`，说明这是上一次下载视频时有缺少内部id的曲目并留下了缓存视频。
您可以删除对应文件或修改其名称，然后尝试重新下载。

## 引用

[maimaiDX-songs](https://github.com/Becods/maimaiDX-songs) 更新更热的歌曲数据库