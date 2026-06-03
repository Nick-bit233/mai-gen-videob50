导入数据前请进入并登录对应服务器的官网: \([国际服](https://maimaidx-eng.com)/[日服](https://maimaidx.jp)\)

## 1. 官网-MGBL导出

> 推荐！Mai-gen项目的书签页工具！以下为基础教学，但如果您具有JavaScript相关知识，可以在官网直接运行项目文件夹下`./external_scripts/load_maimai_score.js`中的代码以加载成绩数据。

- 拖动下面这个链接到浏览器书签栏以将其保存为书签，可以随意命名这个书签。

<!--MGBL_LINK-->

> 该链接最后更新于`v1.2.3`版本。如果已保存了最新的书签，可以直接使用。

- 将浏览器切换至官网标签页，然后点击刚刚保存的书签。

- 页面左上角会显示成绩读取进度，读取完毕后会出现数据复制按钮。点击按钮以获取数据文本。

![MGBL复制按钮示意](../md_res/mgbl_guide_1.png)

## 2. 官网-HTML导出

- 打开`でらっくすRATING`选项卡。

![Rating对象乐曲入口](../md_res/net_guide_1.png)

- 等待B50曲目信息加载完毕后，查看网页的HTML源代码。Windows系统下大部分浏览器为按`Ctrl+U`，不同操作系统、浏览器的方式可能不同。

![Rating对象乐曲页面示例](../md_res/net_guide_2.png)

- 在查看HTML源代码的窗口，复制以`<!DOCTYPE html>`开头的**全部内容**。

## 3. dxrating导出

- 这个数据源的支持功能 还 在 启 动……

## 4. 官网-MTBL导出

> 这个数据源的解析功能会在将来的版本废弃。

- 前往[Maimai Booklet工具页面](https://myjian.github.io/mai-tools/#howto)，按照说明在官网（[国际服](https://maimaidx-eng.com)/[日服](https://maimaidx.jp)）加载该插件。

![MTBL导入摘要图](../md_res/mtbl_guide_1.png)

- 调整导出选项至包含所有内容，读取分数，点击复制`Copy`按钮。