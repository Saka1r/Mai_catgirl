"""Точка входа для Telegram-режима."""
from __future__ import annotations

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging

from mai.config import ensure_dirs
from mai.consolidator import consolidator_loop
from telegram_bot.client import client, state
from telegram_bot.proactive import proactive_boredom_loop
import telegram_bot.handlers  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("mai")
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)


async def main():
    ensure_dirs()
    state.me = await client.get_me()
    logger.info("🐱 Mai запущена (@%s)", state.me.username)
    asyncio.create_task(proactive_boredom_loop())
    asyncio.create_task(consolidator_loop())
    logger.info("[USERBOT] Ожидание сообщений...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        client.start()
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Остановка")