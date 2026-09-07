"""Telegram-клиент и глобальное состояние бота."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import User

from mai.config import API_ID, API_HASH, SESSION_NAME


@dataclass
class BotState:
    me: Optional[User] = None


client = TelegramClient(
    SESSION_NAME, API_ID, API_HASH,
    connection_retries=None,
    device_model="Mai Userbot",
    system_version="2.0",
    app_version="Mai 2.0",
    lang_code="ru",
    use_ipv6=False,
)

state = BotState()