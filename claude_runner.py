import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, NamedTuple


CLAUDE_TERMINAL_SCRIPT = Path(
    os.environ.get("CLAUDE_TERMINAL_SCRIPT", str(Path.home() / "claude-terminal.ps1"))
)


class ClaudeReply(NamedTuple):
    text: str
    session_id: str | None = None


def _find_claude() -> str | None:
    for name in ("claude.cmd", "claude.exe", "claude"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _load_claude_env() -> dict[str, str]:
    env = os.environ.copy()
    if not CLAUDE_TERMINAL_SCRIPT.exists():
        return env

    text = CLAUDE_TERMINAL_SCRIPT.read_text(encoding="utf-8", errors="replace")
    for name, value in re.findall(r'\$env:([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"', text):
        if "$env:PATH" in value:
            value = value.replace("$env:PATH", env.get("PATH", ""))
        env[name] = value
    return env


def _extract_result(payload: Any) -> str:
    if isinstance(payload, dict):
        if payload.get("is_error") is True:
            value = payload.get("result")
            if isinstance(value, str) and "Not logged in" in value:
                return "Claude Code 未登录。请先在电脑终端运行 claude auth login，或运行 claude 后按提示执行 /login。登录完成后再从 QQ 发送 /ai。"
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("result", "content", "text", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(payload.get("messages"), list):
            parts = []
            for item in payload["messages"]:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return "\n".join(parts)
    return ""


def _extract_session_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        value = payload.get("session_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _filter_text_output(text: str) -> str:
    ignored_prefixes = (
        "Running",
        "Tool:",
        "Thinking",
        "Using",
        "Claude",
        "╭",
        "│",
        "╰",
        ">",
    )
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(ignored_prefixes):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def ask_claude_reply(
    prompt: str,
    timeout: int = 120,
    session_id: str | None = None,
    cwd: str | None = None,
    permission_mode: str | None = None,
) -> ClaudeReply:
    claude = _find_claude()
    if not claude:
        return ClaudeReply("错误：找不到 Claude Code 命令，请确认终端中可以运行 claude。", session_id)

    command = [claude, "-p", prompt, "--output-format", "json"]
    if permission_mode:
        command.extend(["--permission-mode", permission_mode])
    if session_id:
        command.extend(["--resume", session_id])

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=_load_claude_env(),
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return ClaudeReply(f"错误：Claude 调用超过 {timeout} 秒，请简化问题后重试。", session_id)
    except OSError as exc:
        return ClaudeReply(f"错误：Claude 调用失败：{exc}", session_id)

    output = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if output:
        try:
            payload = json.loads(output)
            result = _extract_result(payload)
            if result:
                return ClaudeReply(result, _extract_session_id(payload) or session_id)
        except json.JSONDecodeError:
            filtered = _filter_text_output(output)
            if filtered:
                return ClaudeReply(filtered, session_id)

    if stderr:
        filtered = _filter_text_output(stderr)
        return ClaudeReply(filtered or f"错误：Claude 返回异常，退出码 {completed.returncode}。", session_id)

    return ClaudeReply("错误：Claude 返回空响应。", session_id)


def ask_claude(prompt: str, timeout: int = 120) -> str:
    return ask_claude_reply(prompt, timeout).text


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--permission-mode", default=None)
    args = parser.parse_args()
    print(ask_claude_reply(args.prompt, args.timeout, args.session_id, args.cwd, args.permission_mode).text)
