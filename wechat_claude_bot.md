# QQ x Claude Code 自动回复机器人 - 设计方案

> **目标**：手机 QQ 发私聊消息 -> NapCatQQ 接收并上报 -> 本地 Bot 调用 Claude Code -> 结果回复到 QQ 私聊  
> **方案选择**：个人 QQ + NapCatQQ + OneBot v11 HTTP  
> **适用系统**：Windows 10/11

---

## 一、整体架构

```
手机 QQ
    ↕ 正常私聊
电脑端 QQ / NapCatQQ
    ↕ OneBot v11 HTTP 上报与 API
main.py - 私聊消息监听与分发
    ↓ 过滤触发词 / QQ 白名单
claude_runner.py - 子进程调用 Claude Code CLI
    ↓ 解析输出，提取最终结果
main.py - 分段回复
    ↑
NapCatQQ OneBot API
    ↕
手机 QQ 收到回复
```

### 关键技术选型

| 组件 | 选型 | 原因 |
|------|------|------|
| QQ 接入 | NapCatQQ + OneBot v11 | 适合个人 QQ 私聊自动回复，接口稳定清晰 |
| Claude 调用 | `claude CLI` 子进程 | 直接复用已安装的 Claude Code 环境 |
| 输出解析 | `--output-format json` | 优先读取最终 `result` 字段 |
| 配置管理 | 本地网页 + JSON 文件 | 可视化配置，无需改代码 |

---

## 二、项目文件结构

```
wechat_claude_bot.md      # 当前说明文档，已改为 QQ 方案
打开配置页.bat            # 双击打开配置网页
一键启动A5.bat           # 启动 Claude Code、NapCatQQ、Bot、配置页和 WebUI
启动NapCatQQ.ps1         # 当前 NapCatQQ 启动脚本，由配置页切换 QQ 时自动更新
requirements.txt          # Python 依赖

main.py                   # OneBot HTTP 上报入口，处理 QQ 私聊消息
qq_client.py              # OneBot HTTP API 客户端
claude_runner.py          # Claude Code 调用与输出过滤
config_server.py          # 配置网页的本地 HTTP 服务
config_utils.py           # 配置、状态、统计文件读写
config.json               # 配置数据

web/
  index.html              # 配置界面网页
logs/
  YYYY-MM-DD.log          # 运行日志，启动后自动生成
NapCatCompat/
  NapCat.41785.Shell/     # 当前主用 NapCatQQ 兼容版
  NapCat.41785.Shell/versions/9.9.23-41785/resources/app/napcat/config/onebot11.json
                          # 已预置 OneBot HTTP API 与事件上报
```

---

## 三、NapCatQQ 配置要求

本项目使用 OneBot v11 的 HTTP 通信：

1. NapCatQQ 提供 HTTP API，Bot 用它发送私聊消息。
2. NapCatQQ 向 Bot 的 HTTP 地址 POST 上报消息事件。

默认配置：

| 项目 | 默认值 | 说明 |
|------|--------|------|
| NapCat API 地址 | `http://127.0.0.1:3000` | 配置项 `onebot_api_base` |
| Bot 上报监听地址 | `http://127.0.0.1:18089/` | NapCatQQ 的 HTTP 上报地址填这个 |
| 配置页地址 | `http://127.0.0.1:7070` | 本地配置网页 |
| Access Token | 空 | 如果 NapCatQQ 设置了 token，这里也要填一致 |

NapCatQQ 中需要开启：

- OneBot v11 HTTP 服务
- HTTP API 调用
- HTTP POST 事件上报
- 上报地址：`http://127.0.0.1:18089/`

---

## 四、配置项

配置存储在 `config.json`，通过网页界面读写。

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `trigger_prefix` | 字符串 | 触发词，默认 `/ai ` |
| `whitelist` | 字符串列表 | 允许触发的 QQ 号，空列表表示全部放行 |
| `claude_timeout` | 整数 | Claude 调用超时秒数，默认 120 |
| `max_chunk_size` | 整数 | 单条 QQ 消息最大长度，默认 500 |
| `thinking_msg` | 字符串 | 收到消息后立即回复的提示语 |
| `onebot_api_base` | 字符串 | NapCatQQ OneBot HTTP API 地址 |
| `onebot_access_token` | 字符串 | NapCatQQ Access Token，未启用则留空 |
| `bot_host` | 字符串 | Bot 监听地址，默认 `127.0.0.1` |
| `bot_port` | 整数 | Bot 监听端口，默认 `18089` |
| `config_host` | 字符串 | 配置页监听地址，默认 `127.0.0.1` |
| `config_port` | 整数 | 配置页端口，默认 `7070` |

安全建议：正式使用时必须填写 `whitelist`，只允许自己的 QQ 号触发，避免他人消耗 Claude 额度。

---

## 五、配置页切换机器人 QQ

配置页地址：`http://127.0.0.1:7070`。

在“机器人账号”区域可以执行：

| 操作 | 说明 |
|------|------|
| 切换并重启 NapCat | 关闭当前 NapCat/QQ，更新 `启动NapCatQQ.ps1` 中的快速登录 QQ，然后重新启动 |
| 按当前配置重启 | 不修改 QQ，只重启当前 NapCat |
| 二维码登录 | 取消快速登录参数，重启后在 NapCat 窗口扫码登录 |

切换账号前，目标 QQ 需要在当前 Windows QQ/NapCat 环境里登录过，才可快速登录；否则请用“二维码登录”完成一次扫码授权。

---

## 六、QQ 端命令

| 命令 | 说明 |
|------|------|
| `/ai 内容` | 激活会话并发送第一条消息 |
| 普通文本 | 会话激活后继续沿用同一个 Claude session |
| `/new` | 新建 Claude 会话 |
| `/stop` | 停止当前 QQ 的会话激活状态 |
| `/pwd` | 查看当前工作目录 |
| `/cd 路径` | 切换当前 QQ 会话的 Claude 工作目录，并清空旧 session |
| `/mode` | 查看当前 Claude 权限模式 |
| `/mode none` | 默认权限模式 |
| `/mode accept` | 自动接受编辑权限 |
| `/mode bypass` | 跳过权限检查，等同完全放开 Claude Code 权限 |
| `/help` | 查看命令帮助 |

---

## 七、消息处理流程

```
收到 OneBot 上报事件
  │
  ├─ post_type == message？ 否 -> 忽略
  │
  ├─ message_type == private？ 否 -> 忽略
  │
  ├─ 已激活会话或 raw_message 以触发词开头？ 否 -> 忽略
  │
  ├─ user_id 在 QQ 白名单？ 否 -> 忽略（白名单为空则跳过）
  │
  ├─ 发送 thinking_msg
  │
  ├─ 截取触发词后的内容作为 Prompt
  │
  ├─ 调用 claude_runner.py
  │
  └─ 将结果分段发送到该 QQ 私聊
```

`main.py` 每次处理消息前重新读取 `config.json`，所以保存配置后无需重启即可更新触发词、白名单、超时、分段长度等设置。

---

## 八、Claude 调用设计

调用方式：

```
claude -p "<prompt>" --output-format json
```

解析策略：

1. 优先解析 JSON，读取 `result`、`content`、`text` 等最终文本字段。
2. 如果当前 QQ 已有 Claude session，则使用 `--resume <session_id>` 保持会话。
3. `/cd` 会改变该 QQ 的工作目录，并清空旧 session，避免旧目录上下文混用。
4. `/mode accept` 和 `/mode bypass` 会映射到 Claude Code 的 `--permission-mode` 参数。
5. 超时、找不到 Claude、空响应等情况会返回明确错误消息给 QQ。

---

## 九、配置服务接口

配置页运行在 `http://127.0.0.1:7070`。

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/config` | GET | 读取配置 |
| `/api/config` | POST | 保存配置 |
| `/api/status` | GET | 读取 Bot 状态、OneBot 连接状态、今日触发次数 |
| `/api/me` | GET | 调用 NapCatQQ `get_login_info` 获取当前登录 QQ |
| `/api/restart` | POST | 启动或重启由配置服务管理的 `main.py` |
| `/api/napcat/status` | GET | 读取 NapCat 进程状态、启动脚本 QQ、WebUI 地址 |
| `/api/napcat/switch` | POST | 切换快速登录 QQ 并重启 NapCat |
| `/api/napcat/restart` | POST | 按当前启动脚本重启 NapCat |
| `/api/napcat/qrcode` | POST | 取消快速登录参数并重启为二维码登录 |

---

## 十、启动顺序

```
1. 双击 `一键启动A5.bat`
2. 配置页会打开到 `http://127.0.0.1:7070`
3. 在配置页检查 OneBot 连接状态，并按需填写自己的 QQ 白名单
4. 如需更换机器人账号，在“机器人账号”区域输入 QQ 并点击“切换并重启 NapCat”
5. 手机 QQ 私聊发送：/ai 你的问题
```

---

## 十一、环境前提

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11 |
| Python | 3.9 以上 |
| QQ 接入 | NapCatQQ + OneBot v11 |
| Claude Code | 已安装，`claude -p "hi"` 可正常输出 |

安装 Python 依赖：

```
pip install -r requirements.txt
```

---

## 十二、当前实现边界

当前版本只处理 **个人 QQ 私聊**：

- 不响应群聊。
- 白名单只使用 QQ 号。
- 支持 Claude session 级别的多轮会话。
- 不解析图片、语音、文件等非文本内容。

后续可扩展：

| 功能 | 实现思路 |
|------|----------|
| `/clear` 指令 | 清除某个 QQ 的历史上下文 |
| 群聊支持 | 处理 `message_type == group`，增加群号白名单 |
| 更详细统计 | 记录平均响应时长、失败次数、每日 token 估算 |

---

## 十三、安全注意事项

1. **白名单建议必填**：避免任意好友触发 Claude 调用。
2. **仅限本地访问**：`bot_host` 和 `config_host` 默认绑定 `127.0.0.1`。
3. **账号风控风险**：个人 QQ 自动化存在平台风控风险，建议先用测试号。
4. **费用控制**：每次触发都会调用 Claude Code，请设置白名单和合理超时。
