"""Точка входа для Telegram-режима."""
from __future__ import annotations

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging

from mai.client import client, state
from mai.config import ensure_dirs
from telegram_bot.proactive import proactive_boredom_loop
import telegram_bot.handlers  #регистрирует event handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("mai.telegram")
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


async def main() -> None:
    ensure_dirs()
    state.me = await client.get_me()
    logger.info("Userbot запущен 🐱 (@%s)", state.me.username)
    asyncio.create_task(proactive_boredom_loop())
    logger.info("[USERBOT] Ожидание сообщений...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    client.start()
    client.loop.run_until_complete(main())
