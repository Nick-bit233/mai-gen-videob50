# 这个文档已被弃用！

懒得改了，直接重写了个新的。

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
