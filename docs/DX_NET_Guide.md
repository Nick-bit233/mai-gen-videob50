# 导入国际服/日服B50的相关说明

> 基于dxrating网站导出数据的B50读取正在测试中，如遇问题还请在QQ群(994702414)内反馈！

> 对于国服未上线曲目的曲绘获取功能正在测试中！

## 快速使用

进入您所在服务器maimai DX NET的Rating对象乐曲页面，复制HTML源代码备用
或
进入[DXrating](https://dxrating.net/rating)网站导入数据并导出B50的JSON文件，复制文件中的内容备用

按照应用页面引导操作，注意在应用内导入B50时选择`导入B50数据源代码`并粘贴。之后根据您导入的类型选择对应的读取按钮。

## 从maimai DX NET(官网)获取B50数据的HTML源代码

1. 打开[国际服Maimai DX NET](https://maimaidx-eng.com/maimai-mobile/home/ratingTargetMusic/)或[日服Maimai DX NET](https://maimaidx.jp/maimai-mobile/home/ratingTargetMusic/)并进入Rating对象乐曲页面。

> 日服maimai DX NET的rating对象乐曲页面属于SEGA的付费项目，价格为330円/月。

2. 等待页面加载完毕后，按`Ctrl + U` 或 右键>>点击`查看网页源代码`（这个选项卡的名称可能因浏览器不同而有些许差别）。在新打开或跳转至的页面中，全选复制所有内容备用。

## 从DXrating网站获取B50数据的JSON源代码

1. 打开[DXrating](https://dxrating.net/rating)，可以在网页中部右侧找到`IMPORT`、`EXPORT`等按钮。点击`IMPORT`并选择`Import from offical maimai NET...`，然后根据弹窗说明完成数据导入。

2. 导入完毕后，注意页面中央的maimai logo处选择正确的区服。然后点击`EXPORT`并选择`Export JSON (Only B50 records)`，浏览器会下载一个名字形如`dxrating.export-{导出时间}.json`的文件，复制其中的内容备用。
   
   - 打不开Json文件？您可能需要在弹出的打开方式窗口中选择`记事本`，或右键点击`以记事本打开`，或将其后缀改为`.txt`等类似方式。如果都不适用，还请搜索`如何打开Json文件`。

   - 以此法获取的数据可能由于[DXrating](https://dxrating.net/rating)的数据更新缓慢导致部分曲目不正确，或大版本更新前后的B15版本不正确。

## 如何使用获取的源代码

在通过上述操作获取根据一种数据后，请按照[使用说明](../README.md/#使用说明)的步骤继续使用。在应用内获取B50时，选择`导入B50数据源代码`，然后根据指引将复制的内容粘贴到指定输入框内，并点击确定保存。之后，选择对应的含有`读取B50`字样按钮进行数据读取。

   - 若如此做，程序会为您在软件根目录下的`b50_datas/{user_id}`文件夹保存一个`{用户名}.html`或`{用户名}.json`文件用于后续数据处理，这是正常现象。

   - 您也可以通过直接在对应位置放置一个名为`{用户名}.html`或`{用户名}.json`的数据文件跳过上述导入过程。
 
## 插件特性

- 使用保存的Rating对象乐曲网页作为B50信息的读取源，替代国服使用的水鱼查分器获取B50；

- 也可以使用[DXrating](https://dxrating.net/)网站导出的B50 Json文件作为数据源。

## 开发状态与计划

- [x] 支持从[DXrating](https://dxrating.net/)网站获取B50数据；

- [x] 歌曲列表文件的自动更新同步；(NEW!)

- [ ] 改变成绩的获取来源，以获取DX score、FC等级、FS等级；

- [ ] 支持其他数据源的AP50。

## 常见问题

下列是您通过HTML/JSON导入数据时，可能由本插件的代码引发的常见错误情况：

- 读取数据文件时，报错`Error: No HTML/JSON file found in the user's folder.`

请检查是否在网页端正确加载了您的HTML/JSON数据。如果您手动保存了数据文件，请检查是否正确的放置在`b50_datas/{user_id}`文件夹。

- 读取HTML时，报错`Error: HTML screw (type = "XXXXXX") not found.`

请检查查看源代码的网页是否是DX Rating对象乐曲界面。在乐曲加载完毕之前操作也可能导致这个问题。
> 自v0.4.1版本起已经支持**日服**Rating对象乐曲界面的读取，但功能可能不稳定。如果您导入**日服**数据出现了这个问题，请联系开发者。

- 生成B50图片时，报错`list index out of range`

该问题的大概率诱因是您的B50包含某个歌曲数据库未收录的白谱，请参考[歌曲数据库相关](#歌曲数据库相关)。

- 显示`已找到谱面视频的缓存`，但是不是正确的谱面确认视频

如果显示的缓存视频名称结构为`-XX-Y-DX.mp4`，例如`-39-3-DX.mp4`，说明这是上一次下载视频时有缺少内部id的曲目并留下了缓存视频。
您可以删除对应文件或修改其名称，然后尝试重新下载。

- B50定数显示不正确，同时控制台有提示`Warning: song {chart_title} with chart type {type} not found in dataset. Skip filling details.`
  
这是由于软件本地数据库中没有对应乐曲数据导致的，请参考[歌曲数据库相关](#歌曲数据库相关)。

- 下载视频后许多谱面都指向同一个`None-3-DX.mp4`（或相似的以None开头的名称）

这是一个在`v0.3.3`版本的常见问题，原因是太新的曲目并没有一个内部id，请更新到更新版本。

## 歌曲数据库相关

截止**本文档**最后一次更新（v0.5.1），生成器的日服/国际服数据库使用了截止日服在**2025年4月11日**的更新内容（包括Phigros联动等）作为乐曲信息参考。远程数据库每周同步一次，产生的数据误差可以在数分钟内手动修改完成。

如果您急需更新本地数据库，请参考下文的手动同步方式。

> 您可以在下文[引用](#引用)的Github仓库中下载`songs.json`文件，替换`.\music_metadata\maimaidx`文件夹中同名文件来临时更新数据库。注意：在网页端进入首页时会自动覆写一次本地缓存的数据库，请在点击首页的`开始使用`按钮后再进行文件覆盖操作。

## 引用

[maimaiDX-songs](https://github.com/Becods/maimaiDX-songs) 更新更热的歌曲数据库

[DXrating](https://dxrating.net/) 第三方maimai曲库和B50处理网页