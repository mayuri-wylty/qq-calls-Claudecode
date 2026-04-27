# qq-calls-Claudecode

通过 QQ 远程调用 Windows 端 Claude Code 的个人自动回复机器人。

## 功能

- 使用 NapCatQQ + OneBot v11 接收 QQ 私聊消息。
- 通过 `/ai` 激活会话，后续可连续对话。
- 支持 QQ 白名单，限制允许触发的用户。
- 支持 `/help`、`/stop`、`/new`、`/pwd`、`/cd`、`/mode` 等会话命令。
- 提供本地配置页面，默认地址为 `http://127.0.0.1:7070/`。
- 支持一键启动 Bot、配置页和 NapCatQQ。

## 目录说明

- `main.py`：OneBot HTTP 上报入口，处理 QQ 私聊消息。
- `claude_runner.py`：调用本机 Claude Code CLI。
- `qq_client.py`：OneBot HTTP API 客户端。
- `config_server.py`：本地配置页服务。
- `config_utils.py`：配置读写与默认配置。
- `web/index.html`：配置页前端。
- `Start-A5.ps1`：一键启动核心脚本。
- `启动NapCatQQ.ps1`：NapCatQQ 启动脚本。
- `config.example.json`：配置示例。

## 使用前准备

1. 在电脑上安装并登录 Claude Code CLI。
2. 安装并登录 NapCatQQ。
3. 在 NapCatQQ 中启用 OneBot v11 HTTP 服务：
   - HTTP API：`http://127.0.0.1:3000`
   - HTTP 上报：`http://127.0.0.1:18089/`
4. 复制 `config.example.json` 为 `config.json`，按需填写 QQ 白名单和端口。

## 启动

运行：

```powershell
.\Start-A5.ps1
```

或双击：

```text
一键启动A5.bat
```

启动后打开配置页：

```text
http://127.0.0.1:7070/
```

## QQ 命令

- `/ai 问题`：激活 AI 会话并提问。
- `/stop`：退出当前 AI 会话。
- `/new`：清空当前 AI 会话。
- `/pwd`：查看当前 Claude Code 工作目录。
- `/cd 路径`：切换当前会话工作目录。
- `/mode none`：默认权限模式。
- `/mode accept`：自动接受文件编辑权限。
- `/mode bypass`：跳过权限检查，风险较高。
- `/help`：查看帮助。

## 安全说明

仓库不提交以下本地文件：

- `config.json`
- `runtime_status.json`
- `runtime_stats.json`
- `logs/`
- `NapCatCompat/`
- 打包产物和缓存文件

请不要把个人 QQ 号、Token、API Key 或登录缓存提交到公开仓库。
