"""Конфигурация приложения. Загружает переменные из .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ─── Telegram API ────────────────────────────────────────────────────────────
API_ID: int = int(os.getenv("API_ID", "0"))
API_HASH: str = os.getenv("API_HASH", "")
SESSION_NAME: str = os.getenv("SESSION_NAME", "mai_userbot")

# ─── Пользователи ────────────────────────────────────────────────────────────
CREATOR_USER_ID: int = int(os.getenv("CREATOR_USER_ID", "0"))

# ─── Директории ──────────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent.parent

CHATS_DIR: str = os.getenv("CHATS_DIR", str(BASE_DIR / "data" / "chats"))
USERS_DIR: str = os.getenv("USERS_DIR", str(BASE_DIR / "data" / "users"))
GLOBAL_MEMORY_FILE: str = os.getenv(
    "GLOBAL_MEMORY_FILE", str(BASE_DIR / "data" / "memory" / "global.json")
)
GLOBAL_MEMORY_BAN_LIST: str = os.getenv(
    "GLOBAL_MEMORY_FILE", str(BASE_DIR / "data" / "memory" / "ban_list.json")
)


# ─── LLM ─────────────────────────────────────────────────────────────────────
LLAMA_URL: str = os.getenv("LLAMA_URL", "http://localhost:8080/completion")
LLAMA_TIMEOUT: int = int(os.getenv("LLAMA_TIMEOUT", "60"))

# ─── Параметры генерации ─────────────────────────────────────────────────────
GEN_N_PREDICT: int = int(os.getenv("GEN_N_PREDICT", "150"))
GEN_TEMPERATURE: float = float(os.getenv("GEN_TEMPERATURE", "0.85"))
GEN_TOP_P: float = float(os.getenv("GEN_TOP_P", "0.95"))
GEN_TOP_K: int = int(os.getenv("GEN_TOP_K", "50"))
GEN_REPEAT_PENALTY: float = float(os.getenv("GEN_REPEAT_PENALTY", "1.25"))
GEN_MIN_P: float = float(os.getenv("GEN_MIN_P", "0.05"))

# ─── Проактивность ───────────────────────────────────────────────────────────
PROACTIVE_INTERVAL_SEC: int = 1800  # 30 минут
PROACTIVE_BOREDOM_HOURS: int = 3
PROACTIVE_CHANCE: float = 0.20

# ─── Сон ─────────────────────────────────────────────────────────────────────
SLEEP_START_HOUR: int = 2
SLEEP_END_HOUR: int = 8


def ensure_dirs() -> None:
    """Создаёт необходимые директории при первом запуске."""
    for d in (CHATS_DIR, USERS_DIR, os.path.dirname(GLOBAL_MEMORY_FILE)):
        os.makedirs(d, exist_ok=True)
