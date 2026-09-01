"""Обработчики сообщений Telegram."""

from __future__ import annotations

import os
import asyncio          
import logging  
import re
import datetime

from telethon import events
from dotenv import load_dotenv

from typing import Optional

from mai.config import CREATOR_USER_ID
from mai.llm import ask_llama
from mai.memory import (
    build_context,
    format_global_memory_for_prompt,
    format_memory_for_prompt,
    start_memory_thread,
)
from mai.moderation import check_ban
from mai.storage import (
    clear_chat,
    create_chat,
    get_recent_history,
    has_user_written,
    get_user_creator_details,
    get_user_public_summary,
    load_global_memory,
    save_global_memory,
    update_chat,
    update_user_interaction,
    get_ban_list,
    add_ban_list
)

from telegram_bot.client import client, state
from telegram_bot.telegram_utils import ban_user, simulate_reading

logger = logging.getLogger(__name__)

_WHO_QUERY_PHRASES: set[str] = {
    "писал ли тебе этот человек",
    "знаешь ли ты его",
    "кто это",
}

_INVITE_LINK_PATTERN = re.compile(r'https?://t\.me/[\+\w]+|t\.me/joinchat/', re.IGNORECASE)
_CLAIMS_CREATOR_PATTERN = re.compile(
    r'\b(я\s*sakair|я\s*создатель|я\s*sakair1|i\s*am\s*sakair)\b', 
    re.IGNORECASE
)

load_dotenv()
SLEEP_TIME = os.getenv("SLEEP_TIME")

def _get_context_hints(user_text: str, user_id: int) -> str:
    """Генерирует системные подсказки для LLM на основе сообщения."""
    hints = []
    
    # 1. Инвайт-ссылка
    if _INVITE_LINK_PATTERN.search(user_text):
        hints.append("[SYSTEM HINT: This is a Telegram invite link. Mai hates these and refuses to join.]")
    
    # 2. Самозванство (притворяется Sakair1)
    if _CLAIMS_CREATOR_PATTERN.search(user_text) and user_id != CREATOR_USER_ID:
        hints.append(f"[SYSTEM HINT: This user (ID {user_id}) is LYING about being Sakair1. Real Sakair1 has different ID. Call them out.]")
    
    # 3. Очень короткое / странное сообщение
    if len(user_text.strip()) < 3 and not user_text.strip().startswith("/"):
        hints.append("[SYSTEM HINT: Message is too short/unclear. Respond with 'чё?' or emoji.]")
    
    if hints:
        return "<hints>\n" + "\n".join(hints) + "\n</hints>"
    return ""


def _get_last_mai_message(chat_id: str) -> Optional[str]:
    """Получает последнее сообщение Маи в чате для защиты от повторов."""
    try:
        history = get_recent_history(chat_id, 5)
        for msg in reversed(history):
            if msg["role"] == "Mai":
                return msg["content"]
    except Exception:
        pass
    return None

@client.on(events.NewMessage)
async def handler(event: events.NewMessage.Event) -> None:

    if state.me is None:
        return

    if event.sender_id == state.me.id:
        return


    start_time_str, end_time_str = SLEEP_TIME.split('-')

    # Преобразование времени начала и конца в объекты datetime.time
    start_hour, start_minute = map(int, start_time_str.split(':'))
    end_hour, end_minute = map(int, end_time_str.split(':'))

    start_time = datetime.time(start_hour, start_minute)
    end_time = datetime.time(end_hour, end_minute)

    now = datetime.datetime.now()
    current_time = now.time()

    # Проверяем, находится ли текущее время в диапазоне sleep_time
    if start_time <= end_time:
        if start_time <= current_time < end_time:
            return
    else:
        if start_time <= current_time or current_time < end_time:
            return

    sender = await event.get_sender()
    chat_id = event.chat_id
    user_id = event.sender_id
    username = sender.first_name or sender.username or "anon"
    user_text = (event.text or "").strip()

    await asyncio.to_thread(
        update_user_interaction,
        user_id, username, chat_id, user_text[:100],
    )

    if not user_text:
        return

    await simulate_reading(event)

    is_group = event.is_group
    is_private = event.is_private

    if is_group:
        is_reply_to_bot = False
        is_mentioned = False

        if event.reply_to:
            replied_msg = await event.get_reply_message()
            if replied_msg and replied_msg.sender_id == state.me.id:
                is_reply_to_bot = True

        if state.me.username and f"@{state.me.username}".lower() in user_text.lower():
            is_mentioned = True

        if not is_reply_to_bot and not is_mentioned:
            await asyncio.to_thread(
                update_chat, str(chat_id), username, user_text, user_id=user_id
            )
            return

    if user_text.lower() in _WHO_QUERY_PHRASES:
        if event.reply_to:
            replied_msg = await event.get_reply_message()
            target_user_id = replied_msg.sender_id
        else:
            await event.respond("а о ком ты? укажи пользователя или ответь на его сообщение")
            return

        is_creator = user_id == CREATOR_USER_ID
        if has_user_written(target_user_id):
            if is_creator:
                details = get_user_creator_details(target_user_id) or {}
                response = f"да, писал. {details.get('detailed_summary', 'Деталей не помню.')}"
            else:
                response = f"да, писал. {get_user_public_summary(target_user_id)}"
        else:
            response = "нет, этот человек мне не писал."
        await event.respond(response)
        return

    if user_text.startswith("/clear"):
        await asyncio.to_thread(clear_chat, str(chat_id))
        await asyncio.to_thread(create_chat, str(chat_id))
        await event.respond("история стёрта) помню только тебя 😏")
        return

    if user_text.startswith("/forget_me"):
        memory = load_global_memory()
        if str(user_id) in memory["users_index"]:
            del memory["users_index"][str(user_id)]
            save_global_memory(memory)
            await event.respond("забыла тебя) как в первый раз")
        else:
            await event.respond("я тебя и не помню)")
        return

    if user_text.startswith("/start"):
        await event.respond(":3")
        await asyncio.to_thread(create_chat, str(chat_id))
        return

    logger.info("[%s]: %s", username, user_text)

    if user_id != CREATOR_USER_ID:

        ban_list = get_ban_list()
        
        for i in ban_list:
            if user_id == i:
                return

        ban_decision = await asyncio.to_thread(check_ban, user_text)
        if ban_decision == "БАН":
            logger.warning("[BAN] %s (%s) за: '%s'", username, user_id, user_text)
            await ban_user(chat_id, user_id, is_private=is_private)
            add_ban_list(user_id)
            try:
                await event.delete()
            except Exception:
                pass
            return

        # ─── Основной ответ ───────────────────────────────────────────────
    await asyncio.to_thread(update_chat, str(chat_id), username, user_text, user_id=user_id)

    memory_text = await asyncio.to_thread(format_memory_for_prompt, str(chat_id), user_id)
    is_creator = user_id == CREATOR_USER_ID
    global_memory_text = await asyncio.to_thread(
        format_global_memory_for_prompt, user_id, is_creator
    )
    history = await asyncio.to_thread(get_recent_history, str(chat_id), 20)
    context = await asyncio.to_thread(build_context, history, memory_text) 

    # ⬇️ НОВОЕ: Контекстные подсказки + последнее сообщение Маи
    context_hints = _get_context_hints(user_text, user_id)
    last_mai_msg = await asyncio.to_thread(_get_last_mai_message, str(chat_id))
    
    
    # Вставляем подсказки перед историей
    if context_hints:
        context = context_hints + "\n\n" + context

    async with client.action(chat_id, "typing"):
        # ⬇️ Передаём last_mai_message для детекции повторов
        reply = await asyncio.to_thread(ask_llama, context, user_text, last_mai_msg)
        logger.info("[Mai]: %s", reply)
        await client.send_message(chat_id, reply, reply_to=event.id)
        await asyncio.to_thread(update_chat, str(chat_id), "Mai", reply, user_id=user_id)
        start_memory_thread(str(chat_id), user_id)
