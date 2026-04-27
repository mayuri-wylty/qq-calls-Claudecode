from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from claude_runner import ask_claude_reply
from config_utils import LOG_DIR, STATUS_PATH, STATS_PATH, ensure_dirs, load_config, read_json, write_json
from qq_client import OneBotClient


ACTIVE_SESSIONS: dict[str, str | None] = {}
SESSION_WORKDIRS: dict[str, str] = {}
SESSION_PERMISSION_MODES: dict[str, str | None] = {}
STOP_COMMANDS = {"/stop", "/ai stop", "/ai 退出", "/退出"}
NEW_COMMANDS = {"/new", "/ai new", "/ai 新会话"}
HELP_TEXT = """可用命令：
/ai 问题 - 激活 AI 会话，后续可直接发消息
/stop - 退出 AI 会话
/new - 清空当前 AI 会话
/cd 路径 - 切换当前 QQ 会话的 Claude 工作目录
/pwd - 查看当前工作目录
/mode - 查看当前权限模式
/mode none - 无额外权限，Claude 需要授权时会停止
/mode accept - 自动接受文件编辑权限
/mode bypass - 完全跳过权限检查，风险较高
/help - 查看帮助"""


def setup_logging() -> None:
    ensure_dirs()
    log_file = LOG_DIR / f"{datetime.now():%Y-%m-%d}.log"
    logging.basicConfig(
        force=True,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def write_event_log(event_type: str, payload: dict[str, Any]) -> None:
    ensure_dirs()
    path = LOG_DIR / f"events-{datetime.now():%Y-%m-%d}.jsonl"
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "event_type": event_type,
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def update_status(**kwargs: Any) -> None:
    status = read_json(STATUS_PATH, {})
    status.update(kwargs)
    status["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_json(STATUS_PATH, status)


def increment_trigger_count() -> None:
    today = f"{datetime.now():%Y-%m-%d}"
    stats = read_json(STATS_PATH, {"days": {}})
    days = stats.setdefault("days", {})
    current = days.setdefault(today, {"trigger_count": 0})
    current["trigger_count"] = int(current.get("trigger_count", 0)) + 1
    write_json(STATS_PATH, stats)


def split_message(text: str, max_size: int) -> list[str]:
    max_size = max(100, int(max_size or 500))
    if len(text) <= max_size:
        return [text]

    chunks = [text[i : i + max_size] for i in range(0, len(text), max_size)]
    total = len(chunks)
    return [f"[{index}/{total}]\n{chunk}" for index, chunk in enumerate(chunks, start=1)]


def send_chunks(client: OneBotClient, user_id: int, text: str, max_size: int) -> None:
    chunks = split_message(text, max_size)
    for index, chunk in enumerate(chunks, start=1):
        response = client.send_private_msg(user_id, chunk)
        write_event_log("send_private_msg", {"user_id": user_id, "chunk": chunk, "response": response})
        logging.info("已发送回复给 QQ %s：第 %s/%s 段，长度 %s", user_id, index, len(chunks), len(chunk))
        time.sleep(0.3)


def is_allowed(user_id: int, whitelist: list[str]) -> bool:
    return not whitelist or str(user_id) in {str(item) for item in whitelist}


def handle_private_message(event: dict[str, Any]) -> None:
    config = load_config()
    user_id = int(event.get("user_id", 0) or 0)
    raw_message = str(event.get("raw_message") or event.get("message") or "")
    prefix = str(config["trigger_prefix"])
    user_key = str(user_id)
    text = raw_message.strip()

    if text == "/help":
        client = OneBotClient(config["onebot_api_base"], config.get("onebot_access_token", ""))
        client.send_private_msg(user_id, HELP_TEXT)
        logging.info("已向 QQ %s 发送帮助信息", user_id)
        return

    if text == "/pwd":
        client = OneBotClient(config["onebot_api_base"], config.get("onebot_access_token", ""))
        current = SESSION_WORKDIRS.get(user_key, os.getcwd())
        client.send_private_msg(user_id, f"当前工作目录：{current}")
        logging.info("已向 QQ %s 发送当前工作目录：%s", user_id, current)
        return

    if text == "/mode":
        client = OneBotClient(config["onebot_api_base"], config.get("onebot_access_token", ""))
        current = SESSION_PERMISSION_MODES.get(user_key) or "none"
        client.send_private_msg(user_id, f"当前权限模式：{current}\n可用：/mode none、/mode accept、/mode bypass")
        logging.info("已向 QQ %s 发送当前权限模式：%s", user_id, current)
        return

    if text.startswith("/mode "):
        client = OneBotClient(config["onebot_api_base"], config.get("onebot_access_token", ""))
        value = text[6:].strip().lower()
        mode_map = {
            "none": None,
            "default": None,
            "accept": "acceptEdits",
            "acceptedits": "acceptEdits",
            "bypass": "bypassPermissions",
            "skip": "bypassPermissions",
        }
        if value not in mode_map:
            client.send_private_msg(user_id, "未知权限模式。可用：/mode none、/mode accept、/mode bypass")
            return
        SESSION_PERMISSION_MODES[user_key] = mode_map[value]
        ACTIVE_SESSIONS.pop(user_key, None)
        label = SESSION_PERMISSION_MODES[user_key] or "none"
        warning = "\n注意：bypass 会跳过权限检查，只建议在可信目录中使用。" if label == "bypassPermissions" else ""
        client.send_private_msg(user_id, f"已切换权限模式：{label}\n已清空当前 Claude 会话。发送 /ai 问题 开启新会话。{warning}")
        logging.info("QQ %s 切换 Claude 权限模式为 %s，并清空 Claude session", user_id, label)
        return

    if text.startswith("/cd"):
        client = OneBotClient(config["onebot_api_base"], config.get("onebot_access_token", ""))
        target = text[3:].strip()
        if not target:
            client.send_private_msg(user_id, "用法：/cd C:\\Users\\20323\\Downloads")
            return
        expanded = Path(os.path.expandvars(os.path.expanduser(target)))
        if not expanded.is_absolute():
            expanded = Path(SESSION_WORKDIRS.get(user_key, os.getcwd())) / expanded
        try:
            resolved = expanded.resolve(strict=True)
        except OSError:
            client.send_private_msg(user_id, f"目录不存在：{target}")
            return
        if not resolved.is_dir():
            client.send_private_msg(user_id, f"不是目录：{resolved}")
            return
        SESSION_WORKDIRS[user_key] = str(resolved)
        ACTIVE_SESSIONS.pop(user_key, None)
        client.send_private_msg(user_id, f"已切换工作目录：{resolved}\n已清空当前 Claude 会话。发送 /ai 问题 开启新会话。")
        logging.info("QQ %s 切换工作目录为 %s，并清空 Claude session", user_id, resolved)
        return

    if text in STOP_COMMANDS:
        ACTIVE_SESSIONS.pop(user_key, None)
        client = OneBotClient(config["onebot_api_base"], config.get("onebot_access_token", ""))
        client.send_private_msg(user_id, "已退出 AI 会话。再次发送 /ai 问题 可重新激活。")
        logging.info("QQ %s 已退出 AI 会话", user_id)
        return

    if text in NEW_COMMANDS:
        ACTIVE_SESSIONS.pop(user_key, None)
        client = OneBotClient(config["onebot_api_base"], config.get("onebot_access_token", ""))
        client.send_private_msg(user_id, "已清空当前 AI 会话。发送 /ai 问题 可开启新会话。")
        logging.info("QQ %s 已清空 AI 会话", user_id)
        return

    is_activation = raw_message.startswith(prefix)
    is_active = user_key in ACTIVE_SESSIONS

    if not is_activation and not is_active:
        logging.info("忽略 QQ %s 的私聊消息：未以触发词 %r 开头。原文：%s", user_id, prefix, raw_message)
        return

    if not user_id:
        logging.warning("忽略缺少 user_id 的事件：%s", event)
        return

    if not is_allowed(user_id, config["whitelist"]):
        logging.info("忽略非白名单 QQ：%s", user_id)
        return

    prompt = raw_message[len(prefix) :].strip() if is_activation else text
    if not prompt:
        ACTIVE_SESSIONS[user_key] = None
        client = OneBotClient(config["onebot_api_base"], config.get("onebot_access_token", ""))
        client.send_private_msg(user_id, "已进入 AI 会话。后续直接发送消息即可继续；发送 /stop 退出，/new 新建会话。")
        return

    client = OneBotClient(config["onebot_api_base"], config.get("onebot_access_token", ""))
    if is_activation:
        ACTIVE_SESSIONS[user_key] = None
    increment_trigger_count()
    logging.info(
        "收到 QQ %s 的%s消息：%s；当前 Claude session_id=%s",
        user_id,
        "激活" if is_activation else "会话",
        prompt,
        ACTIVE_SESSIONS.get(user_key),
    )

    thinking = str(config.get("thinking_msg", "")).strip()
    if thinking:
        try:
            client.send_private_msg(user_id, thinking)
        except Exception as exc:
            logging.warning("发送处理中提示失败：%s", exc)

    workdir = SESSION_WORKDIRS.get(user_key, os.getcwd())
    permission_mode = SESSION_PERMISSION_MODES.get(user_key)
    reply = ask_claude_reply(
        prompt,
        int(config.get("claude_timeout", 120)),
        ACTIVE_SESSIONS.get(user_key),
        workdir,
        permission_mode,
    )
    result = reply.text
    ACTIVE_SESSIONS[user_key] = reply.session_id
    logging.info(
        "Claude 返回给 QQ %s 的结果长度：%s，session_id=%s，预览：%s",
        user_id,
        len(result),
        reply.session_id,
        result[:120].replace("\n", " "),
    )
    send_chunks(client, user_id, result, int(config.get("max_chunk_size", 500)))


class OneBotHandler(BaseHTTPRequestHandler):
    server_version = "QQClaudeBot/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        logging.info("%s - %s", self.address_string(), format % args)

    def _json_response(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json_response(200, {"ok": True})
            return
        self._json_response(404, {"error": "not found"})

    def _read_request_body(self) -> str:
        transfer_encoding = self.headers.get("Transfer-Encoding", "").lower()
        if "chunked" in transfer_encoding:
            chunks: list[bytes] = []
            while True:
                size_line = self.rfile.readline().strip()
                if not size_line:
                    continue
                size = int(size_line.split(b";", 1)[0], 16)
                if size == 0:
                    self.rfile.readline()
                    break
                chunks.append(self.rfile.read(size))
                self.rfile.readline()
            return b"".join(chunks).decode("utf-8", errors="replace")

        length = int(self.headers.get("Content-Length", "0") or 0)
        return self.rfile.read(length).decode("utf-8", errors="replace")

    def do_POST(self) -> None:
        body = self._read_request_body()
        try:
            event = json.loads(body or "{}")
        except json.JSONDecodeError:
            write_event_log("invalid_json", {"headers": dict(self.headers), "body": body})
            self._json_response(400, {"error": "invalid json"})
            return

        write_event_log("raw_post", {"path": self.path, "headers": dict(self.headers), "body": body, "event": event})
        self._json_response(200, {"status": "ok"})

        if event.get("post_type") == "message" and event.get("message_type") == "private":
            logging.info("收到 OneBot 私聊事件：%s", json.dumps(event, ensure_ascii=False))
            threading.Thread(target=handle_private_message_safe, args=(event,), daemon=True).start()
        else:
            logging.info("忽略非私聊消息事件：%s", json.dumps(event, ensure_ascii=False))


def handle_private_message_safe(event: dict[str, Any]) -> None:
    try:
        handle_private_message(event)
    except Exception:
        logging.exception("处理 OneBot 私聊事件失败：%s", json.dumps(event, ensure_ascii=False))


def main() -> None:
    setup_logging()
    config = load_config()
    host = str(config.get("bot_host", "127.0.0.1"))
    port = int(config.get("bot_port", 8088))
    update_status(bot_running=True, bot_host=host, bot_port=port, bot_pid=os.getpid())
    logging.info("QQ Claude Bot 启动，监听 OneBot 上报：http://%s:%s", host, port)
    logging.info("请在 NapCatQQ 中配置 HTTP 上报地址：http://%s:%s/", host, port)

    try:
        server = ThreadingHTTPServer((host, port), OneBotHandler)
        server.serve_forever()
    finally:
        update_status(bot_running=False)


if __name__ == "__main__":
    main()
