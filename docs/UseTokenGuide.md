## 使用自定义OAuth 或 PO Token

注意：附带验证信息以抓取视频需要使用 Node.js 来生成访问令牌。因此涉及到额外的环境配置操作：

### Node.js 环境配置

1. 从官网下载 Node.js LTS 版本：
   - 访问 [https://nodejs.org/](https://nodejs.org/)
   - 下载并安装 LTS（长期支持）版本

2. 安装完成后，打开命令提示符（终端）并运行以下命令验证安装：  
   ```bash
   node --version
   npm --version   
   ```
   如果安装正确，这两个命令都会显示版本号。

在默认配置无法运行视频下载程序时，请先尝试配置PO Token：

## 配置 PO Token 使用

你可以选择两种方式在运行视频生成器时使用 POToken：

- 手动配置：手动获取 PO Token，并填入 `global_config.yaml` 文件中。

   - 如果你有浏览器前端调试经验，可以参考[此教程](https://github.com/JuanBindez/pytubefix/pull/209)从浏览器控制台抓取 PO Token。

   - 通过手动部署相关的开源项目获取 PO Token，例如：

      - [youtube-po-token-generator](https://github.com/YunzheZJU/youtube-po-token-generator)

      - [youtube-trusted-session-generator](https://github.com/iv-org/youtube-trusted-session-generator?tab=readme-ov-file)

   > 注意：生成的PO Token通常有效期有限，你可能需要定期更新

- 自动获取：我们提供了一个自动化函数，根据下面的指南安装 youtube-po-token-generator 生成器，每次运行视频生成器时，通过子进程自动运行生成 PO Token。此方法无需手动填写，但不保证成功率。

### PO Token生成器安装

本项目使用 [youtube-po-token-generator](https://github.com/YunzheZJU/youtube-po-token-generator) 来生成 YouTube 访问令牌。按照如下步骤配置：

1. 在项目根目录中打开终端，或在终端中导航到项目根目录：   
   ```
   cd path/to/project/root
   ```

2. 执行以下命令：

   ```
   npm install global-agent youtube-po-token-generator
   ```

3. 如果卡住或失败，请尝试先运行如下命令更换源：

   ```
   npm config set registry https://registry.npmmirror.com
   ```

4. 如果安装正确，你可以在项目根目录中看到`node_modules`文件夹以及`package.json`文件。`package.json`文件内容如下：
   ```
   {
      "dependencies": {
         "global-agent": "^3.0.0",
         "youtube-po-token-generator": "^0.3.0"
      }
   }
   ```

5、配置生成器脚本：打开`external_scripts/po_token_generator.js`文件，你只需要确认其中的代理配置一行（确保端口号正确）：
   ```javascript
   global.GLOBAL_AGENT.HTTP_PROXY = 'http://127.0.0.1:7890'
   ```
   如果你不需要使用代理，请删除或注释掉该行。

### 具体配置

打开 `global_config.yaml` 并修改以下配置：
   ```yaml
   # 是否使用手动 PO Token 抓取视频
   #（注意该选项和自动获取 PO Token 互斥，系统优先使用手动配置的 PO Token）
   USE_CUSTOM_PO_TOKEN: false

   # 配置自行抓取的 PO Token，包括两个部分，visitor_data 和 po_token
   CUSTOMER_PO_TOKEN:  
      visitor_data: ""  
      po_token: "" 

   # 是否自动获取 PO Token 抓取视频（请先阅读相关文档并确保已安装 Node.js 环境）
   USE_AUTO_PO_TOKEN: true
   ```

注意：PO Token生成器需要能够访问 YouTube 的网络环境。通常只有在你的ip被ban的情况下，PO Token才会有效。如果你的ip地址已经变动，请尝试先在不配置PO Token的情况下抓取视频，如果仍然失败，再尝试配置。

## 配置 OAuth 使用

如果更改ip地址和PO Token后仍然无法抓取视频，你最后可以尝试使用OAuth登录抓取视频。但这需求你有一个Google账号。

在`global_config.yaml` 中配置如下字段：

```yaml
# 是否使用 OAuth 登录抓取视频
#（注意：使用 OAuth 与使用PO Token互斥，优先选择使用PO Token，
# 使用 OAuth 可能存在风险）
USE_OAUTH: true
```

程序运行时会输出绑定链接及验证码，在浏览器中输入验证码并登录你的Google账号即可。

登录后，程序会缓存你的OAuth Token，在配置`USE_OAUTH: true`的情况下，重新启动程序，运行时将自动使用。

**注意：OAuth 登录可能存在风险，短时间大量访问可能被识别为恶意程序，使用OAuth 登录如果造成账号封禁等后果自负。**


## 常见问题

1. **找不到 npm / Node.js**
   - 确保 Node.js 已正确安装
   - 安装完成后尝试重启终端或 IDE
   - 检查 Node.js 是否已添加到系统环境变量 PATH 中

2. **令牌生成器报错**
   - 确保所有依赖都已正确安装
   - 检查网络是否能够访问 YouTube
   - 确认使用的是最新版本的令牌生成器


## 贡献指南

欢迎提交 Pull Request 或创建 Issue。在提交之前，请：
1. 确保代码已经过测试
2. 遵循项目的代码规范
3. 更新相关文档