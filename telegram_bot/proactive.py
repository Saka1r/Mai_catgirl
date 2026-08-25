"""Проактивный loop: Маи пишет первая, когда заскучала."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import datetime

from mai.client import client
from mai.config import (
    CHATS_DIR,
    PROACTIVE_INTERVAL_SEC,
    PROACTIVE_BOREDOM_HOURS,
    PROACTIVE_CHANCE,
)
from mai.llm import generate_proactive
from mai.memory import build_context
from mai.prompts import SYSTEM_PROMPT, PROACTIVE_PROMPT
from mai.storage import load_chat, update_chat

logger = logging.getLogger(__name__)


async def proactive_boredom_loop() -> None:
    """Фоновый цикл: периодически пишет в чаты, где давно тишина."""
    logger.info("[PROACTIVE] Запущен фоновый поток инициативы...")

    while True:
        await asyncio.sleep(PROACTIVE_INTERVAL_SEC)
        try:
            if not os.path.exists(CHATS_DIR):
                continue

            chat_files = [f for f in os.listdir(CHATS_DIR) if f.endswith(".json")]
            if not chat_files:
                continue

            for chat_file in chat_files:
                chat_id_str = chat_file.replace(".json", "")
                try:
                    chat_id = int(chat_id_str)
                except ValueError:
                    continue

                chat_data = await asyncio.to_thread(load_chat, chat_id_str)
                messages = chat_data.get("messages", [])
                if not messages:
                    continue

                last_msg = messages[-1]
                last_ts = datetime.strptime(last_msg["ts"], "%Y-%m-%d %H:%M:%S")
                hours_passed = (datetime.now() - last_ts).total_seconds() / 3600

                if hours_passed > PROACTIVE_BOREDOM_HOURS and random.random() < PROACTIVE_CHANCE:
                    logger.info("[PROACTIVE] Маи заскучала → чат %s", chat_id)

                    init_prompt = PROACTIVE_PROMPT.format(system_prompt=SYSTEM_PROMPT)
                    reply = await asyncio.to_thread(generate_proactive, init_prompt)

                    if reply:
                        try:
                            async with client.action(chat_id, "typing"):
                                await asyncio.sleep(max(1, len(reply) * 0.15))
                                await client.send_message(chat_id, reply)
                                await asyncio.to_thread(update_chat, chat_id_str, "Mai", reply)
                        except Exception as e:
                            logger.error("[PROACTIVE SEND ERROR] %s", e)

        except Exception as e:
            logger.exception("[PROACTIVE ERROR] %s", e)