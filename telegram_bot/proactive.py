"""Проактивный loop: Маи пишет первой, когда скучно."""
from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import datetime

from mai.config import (
    CHATS_DIR, PROACTIVE_INTERVAL_SEC,
    PROACTIVE_BOREDOM_HOURS, PROACTIVE_CHANCE,
)
from mai.llm import generate_response
from mai.memory import format_global_memory_for_prompt
from mai.prompts import PROACTIVE_PROMPT, SYSTEM_PROMPT
from mai.storage import load_chat, update_chat
from telegram_bot.client import client

logger = logging.getLogger(__name__)


async def proactive_boredom_loop() -> None:
    logger.info("[PROACTIVE] Запущен")
    while True:
        await asyncio.sleep(PROACTIVE_INTERVAL_SEC)
        try:
            if not os.path.exists(CHATS_DIR):
                continue
            for chat_file in os.listdir(CHATS_DIR):
                if not chat_file.endswith(".json"):
                    continue
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
                hours = (datetime.now() - last_ts).total_seconds() / 3600

                if hours > PROACTIVE_BOREDOM_HOURS and random.random() < PROACTIVE_CHANCE:
                    logger.info("[PROACTIVE] чат %s", chat_id)
                    
                    # Получаем user_id из последнего сообщения пользователя
                    user_id = None
                    for msg in reversed(messages):
                        if msg["role"] != "Mai" and msg.get("user_id"):
                            try:
                                user_id = int(msg["user_id"])
                                break
                            except (ValueError, TypeError):
                                continue
                    
                    if user_id:
                        about_user = await asyncio.to_thread(
                            format_global_memory_for_prompt, user_id, False
                        )
                    else:
                        about_user = "Ничего не помню об этом человеке."
                    
                    prompt = PROACTIVE_PROMPT.format(
                        system_prompt=SYSTEM_PROMPT,
                        username="собеседник",
                        about_user=about_user,
                    )
                    reply = await asyncio.to_thread(generate_response, prompt, n_predict=120)
                    if reply and reply != "...":
                        try:
                            async with client.action(chat_id, "typing"):
                                await asyncio.sleep(max(1, len(reply) * 0.15))
                                await client.send_message(chat_id, reply)
                                await asyncio.to_thread(update_chat, chat_id_str, "Mai", reply)
                        except Exception as e:
                            logger.error("[PROACTIVE SEND ERROR] %s", e)
        except Exception as e:
            logger.exception("[PROACTIVE ERROR] %s", e)