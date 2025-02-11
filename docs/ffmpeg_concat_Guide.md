# 使用 ffmpeg-concat 实现高级过渡效果

## Node.js 环境配置

1. 从官网下载 Node.js LTS 版本：
   - 访问 [https://nodejs.org/](https://nodejs.org/)
   - 下载并安装 LTS（长期支持）版本

2. 安装完成后，打开命令提示符（终端）并运行以下命令验证安装：  
   ```bash
   node --version
   npm --version   
   ```

## 安装 ffmpeg-concat

首先，确保你已经安装了上述 Node.js 和 npm。然后，你可以通过以下命令安装 `ffmpeg-concat`：

```sh
npm install --save ffmpeg-concat
```

如果在中途卡住或失败，请尝试先运行如下命令更换源：

```
npm config set registry https://registry.npmmirror.com
```

安装完成后，刷新页面即可开始生成。

> 注意：使用ffmpeg-concat的进行视频拼接的过程中（阶段2）会占用大量硬盘读写空间，推荐使用高速SSD固态硬盘并预留足够的存储空间。拼接过程中使用操作系统很可能产生卡顿，请耐心等待生成结束。

## 转场效果

`ffmpeg-concat` 支持多种转场效果，包括：

- `fade`: 淡入淡出
- `directionalWipe`: 方向擦除
- `circleOpen`: 圆形打开
- `circleClose`: 圆形关闭

转场效果的预览可以在[此链接](https://github.com/transitive-bullshit/ffmpeg-concat/blob/master/readme.zh.md#%E8%BF%87%E6%B8%A1)查看

你可以在下方“片段过渡效果”中指定转场效果的名称。过渡持续时间将和上方配置一致。

## 参考链接

更多详细信息，请参考 [ffmpeg-concat 的 GitHub 仓库](https://github.com/transitive-bullshit/ffmpeg-concat)。
