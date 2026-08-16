"""Telegram-клиент и глобальное состояние бота."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import User

from mai.config import API_ID, API_HASH, SESSION_NAME


@dataclass
class BotState:
    """Хранит runtime-состояние бота."""

    me: Optional[User] = None


client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
state = BotState()