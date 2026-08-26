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

from telegram_bot.client import client
from mai.config import SLEEP_START_HOUR, SLEEP_END_HOUR

logger = logging.getLogger(__name__)


async def ban_user(chat_id: int, user_id: int, is_private: bool = False) -> None:
    """Бан в группах или блокировка в ЛС."""
    try:
        if is_private:
            await client(BlockRequest(user_id))
            logger.info("[BLOCK] 🚫 Заблокировала %s в ЛС", user_id)
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
            logger.info("[BAN] 🔨 Полный бан %s в чате %s", user_id, chat_id)
        except Exception as e1:
            logger.warning("[BAN WARNING] Полный бан не удался (%s), кикаю...", e1)
            try:
                await client.kick_participant(entity, user_id)
                logger.info("[KICK] 👢 Кикнула %s из чата %s", user_id, chat_id)
            except Exception as e2:
                logger.error("[KICK ERROR] Не удалось кикнуть: %s", e2)

    except Exception as e:
        logger.error("[BAN CRITICAL] Не удалось забанить %s: %s", user_id, e)


async def simulate_reading(event: events.NewMessage.Event) -> None:
    """Симулирует чтение сообщения глазами Маи."""
    hour = datetime.now().hour
    if SLEEP_START_HOUR <= hour < SLEEP_END_HOUR:
        logger.debug("[SLEEP] Маи спит, сообщение не прочитано")
        return

    text_len = len(event.text or "")
    read_time = random.uniform(1.0, 2.5) + min(text_len / 300, 1.5)
    await asyncio.sleep(read_time)
    await event.mark_read()
