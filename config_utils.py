from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(os.environ.get("A5_ROOT", Path(__file__).resolve().parent)).resolve()
CONFIG_PATH = BASE_DIR / "config.json"
STATUS_PATH = BASE_DIR / "runtime_status.json"
STATS_PATH = BASE_DIR / "runtime_stats.json"
LOG_DIR = BASE_DIR / "logs"


DEFAULT_CONFIG: dict[str, Any] = {
    "trigger_prefix": "/ai ",
    "whitelist": [],
    "claude_timeout": 120,
    "max_chunk_size": 500,
    "thinking_msg": "收到，正在处理...",
    "onebot_api_base": "http://127.0.0.1:3000",
    "onebot_access_token": "",
    "bot_host": "127.0.0.1",
    "bot_port": 18089,
    "config_host": "127.0.0.1",
    "config_port": 7070,
}


def ensure_dirs() -> None:
    LOG_DIR.mkdir(exist_ok=True)


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    merged = DEFAULT_CONFIG.copy()
    merged.update(data)
    merged["whitelist"] = [str(item).strip() for item in merged.get("whitelist", []) if str(item).strip()]
    return merged


def save_config(config: dict[str, Any]) -> None:
    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    merged["whitelist"] = [str(item).strip() for item in merged.get("whitelist", []) if str(item).strip()]
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        json.dump(merged, file, ensure_ascii=False, indent=2)


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default.copy()
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default.copy()


def write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
