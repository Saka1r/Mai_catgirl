"""Telegram-действия: бан, симуляция чтения."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime

from telethon import events
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.functions.contacts import BlockRequest
from telethon.tl.types import ChatBannedRights

from mai.config import SLEEP_TIME
from telegram_bot.client import client

logger = logging.getLogger(__name__)


def is_sleep_time() -> bool:
    """Проверяет, спит ли Маи сейчас."""
    try:
        start_str, end_str = SLEEP_TIME.split("-")
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        start = sh * 60 + sm
        end = eh * 60 + em
        now = datetime.now().hour * 60 + datetime.now().minute

        if start <= end:
            return start <= now < end
        else:
            return now >= start or now < end
    except Exception:
        return False


async def ban_user(chat_id: int, user_id: int, is_private: bool = False) -> None:
    try:
        if is_private:
            await client(BlockRequest(user_id))
            logger.info("[BLOCK] 🚫 %s", user_id)
            return

        entity = await client.get_entity(chat_id)
        try:
            rights = ChatBannedRights(
                until_date=None,
                view_messages=True,
                send_messages=True,
                send_media=True,
                send_stickers=True,
            )
            await client(EditBannedRequest(entity, user_id, rights))
            logger.info("[BAN] 🔨 %s in %s", user_id, chat_id)
        except Exception as e1:
            logger.warning("[BAN WARNING] %s, kicking...", e1)
            try:
                await client.kick_participant(entity, user_id)
                logger.info("[KICK] 👢 %s", user_id)
            except Exception as e2:
                logger.error("[KICK ERROR] %s", e2)
    except Exception as e:
        logger.error("[BAN CRITICAL] %s: %s", user_id, e)


async def simulate_reading(event: events.NewMessage.Event) -> None:
    if is_sleep_time():
        logger.debug("[SLEEP] спит")
        return
    text_len = len(event.text or "")
    read_time = random.uniform(1.0, 2.5) + min(text_len / 300, 1.5)
    await asyncio.sleep(read_time)
    await event.mark_read()