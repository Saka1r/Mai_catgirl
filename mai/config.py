"""Конфигурация приложения. Загружает переменные из .env."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Telegram
API_ID: int = int(os.getenv("API_ID", "0"))
API_HASH: str = os.getenv("API_HASH", "")
SESSION_NAME: str = os.getenv("SESSION_NAME", "mai_userbot")
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "mai_catgirl")

# Creator
CREATOR_USER_ID: int = int(os.getenv("CREATOR_USER_ID", "0"))

# Dirs
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
CHATS_DIR: str = str(DATA_DIR / "chats")
USERS_DIR: str = str(DATA_DIR / "users")
GLOBAL_MEMORY_FILE: str = str(DATA_DIR / "memory" / "global.json")
DIARY_FILE: str = str(DATA_DIR / "diary.md")
DIARY_EMBEDDINGS: str = str(DATA_DIR / "diary_embeddings.npy")

# LLM
LLAMA_URL: str = os.getenv("LLAMA_URL", "http://localhost:8080/completion")
LLAMA_TIMEOUT: int = int(os.getenv("LLAMA_TIMEOUT", "120"))

# Generation
GEN_N_PREDICT: int = int(os.getenv("GEN_N_PREDICT", "120"))
GEN_TEMPERATURE: float = float(os.getenv("GEN_TEMPERATURE", "0.82"))
GEN_TOP_P: float = float(os.getenv("GEN_TOP_P", "0.92"))
GEN_TOP_K: int = int(os.getenv("GEN_TOP_K", "45"))
GEN_REPEAT_PENALTY: float = float(os.getenv("GEN_REPEAT_PENALTY", "1.40"))
GEN_MIN_P: float = float(os.getenv("GEN_MIN_P", "0.06"))

# Sleep
SLEEP_TIME: str = os.getenv("SLEEP_TIME", "02:00-07:00")

# Proactive
PROACTIVE_INTERVAL_SEC: int = int(os.getenv("PROACTIVE_INTERVAL_SEC", "1800"))
PROACTIVE_BOREDOM_HOURS: int = int(os.getenv("PROACTIVE_BOREDOM_HOURS", "3"))
PROACTIVE_CHANCE: float = float(os.getenv("PROACTIVE_CHANCE", "0.20"))


def ensure_dirs() -> None:
    """Создаёт необходимые директории."""
    for d in (CHATS_DIR, USERS_DIR, os.path.dirname(GLOBAL_MEMORY_FILE), os.path.dirname(DIARY_FILE)):
        os.makedirs(d, exist_ok=True)