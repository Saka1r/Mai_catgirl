"""Обработчики сообщений Telegram с Kuni-style pipeline."""
from __future__ import annotations

import asyncio
import logging
import random
import re
import time

from telethon import events

from mai.config import CREATOR_USER_ID, BOT_USERNAME
from mai.consolidator import consolidator_loop
from mai.llm import generate_response, query_llm_raw
from mai.memory import (
    build_context, format_global_memory_for_prompt,
    format_memory_for_prompt, start_memory_thread,
)
from mai.moderation import check_ban
from mai.prompts import RESPONSE_PROMPT, THINK_PROMPT, SYSTEM_PROMPT
from mai.storage import (
    add_to_ban_list, clear_chat, create_chat, get_last_mai_message,
    get_recent_history, get_user_creator_details, get_user_public_summary,
    has_user_written, is_banned, load_global_memory, save_global_memory,
    update_chat, update_user_interaction,
)
from mai.tools import ToolAction, choose_action
from mai.utils.text import clean_reply, detect_last_mai_repeat
from telegram_bot.client import client, state
from telegram_bot.telegram_utils import ban_user, is_sleep_time, simulate_reading

logger = logging.getLogger(__name__)

# Триггеры вопросов "писал ли тебе"
_WHO_QUERY_PHRASES = {"писал ли тебе этот человек", "знаешь ли ты его", "кто это"}
_INVITE_LINK_PATTERN = re.compile(r"https?://t\.me/[\+\w]+|t\.me/joinchat/", re.IGNORECASE)
_CREATOR_CLAIM = re.compile(r"\b(я\s*sakair|я\s*создатель|я\s*sakair1)\b", re.IGNORECASE)


def _get_context_hints(user_text: str, user_id: int) -> str:
    hints = []
    if _INVITE_LINK_PATTERN.search(user_text):
        hints.append("[HINT: это инвайт-ссылка. откажись коротко.]")
    if _CREATOR_CLAIM.search(user_text) and user_id != CREATOR_USER_ID:
        hints.append(f"[HINT: этот юзер врёт что он Sakair1. ID реального Sakair1: {CREATOR_USER_ID}. Раскрой его.]")
    if len(user_text.strip()) < 3 and not user_text.strip().startswith("/"):
        hints.append("[HINT: короткое/непонятное сообщение. ответь кратко.]")
    if hints:
        return "<hints>\n" + "\n".join(hints) + "\n</hints>"
    return ""


def _think(context: str, user_message: str) -> str:
    """Шаг 1: Chain-of-Thought — внутренний монолог."""
    prompt = THINK_PROMPT.format(context=context, user_message=user_message)
    raw = query_llm_raw(
        prompt,
        n_predict=80,
        temperature=0.7,
        stop=["</Mai_thoughts>", "\n\n", "<User>"],
    )
    thought = clean_reply(raw) if raw else "обычное сообщение"
    logger.debug("[THINK] %s", thought)
    return thought


def _generate_final(context: str, user_message: str, thought: str) -> str:
    """Шаг 3: финальный ответ после tool-calling."""
    prompt = RESPONSE_PROMPT.format(
        context=context, user_message=user_message, thought=thought
    )
    return generate_response(prompt)


@client.on(events.NewMessage)
async def handler(event: events.NewMessage.Event) -> None:
    if state.me is None or event.sender_id == state.me.id:
        return

    # Быстрая проверка бана по списку
    if is_banned(event.sender_id):
        return

    # Спим?
    if is_sleep_time():
        return

    sender = await event.get_sender()
    chat_id = event.chat_id
    user_id = event.sender_id
    username = sender.first_name or sender.username or "anon"
    user_text = (event.text or "").strip()

    await asyncio.to_thread(
        update_user_interaction, user_id, username, chat_id, user_text[:100]
    )

    if not user_text:
        return

    await simulate_reading(event)

    # === Группы: только reply или mention ===
    is_group = event.is_group
    is_private = event.is_private

    if is_group:
        is_reply = False
        is_mention = False
        if event.reply_to:
            replied = await event.get_reply_message()
            if replied and replied.sender_id == state.me.id:
                is_reply = True
        if state.me.username and f"@{state.me.username}".lower() in user_text.lower():
            is_mention = True
        if not is_reply and not is_mention:
            await asyncio.to_thread(update_chat, str(chat_id), username, user_text, user_id=user_id)
            return

    # === Вопрос "писал ли тебе этот человек" ===
    if user_text.lower() in _WHO_QUERY_PHRASES:
        if event.reply_to:
            replied = await event.get_reply_message()
            target_id = replied.sender_id
        else:
            await event.respond("а о ком ты? укажи пользователя или ответь на его сообщение")
            return
        is_creator = user_id == CREATOR_USER_ID
        if has_user_written(target_id):
            if is_creator:
                details = get_user_creator_details(target_id) or {}
                resp = f"да, писал. {details.get('detailed_summary', 'Деталей не помню.')}"
            else:
                resp = f"да, писал. {get_user_public_summary(target_id)}"
        else:
            resp = "нет, этот человек мне не писал."
        await event.respond(resp)
        return

    # === Команды ===
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

    # === Модерация ===
    if user_id != CREATOR_USER_ID:
        ban_decision = await asyncio.to_thread(check_ban, user_text)
        if ban_decision == "БАН":
            logger.warning("[BAN] %s за: '%s'", username, user_text)
            await ban_user(chat_id, user_id, is_private=is_private)
            add_to_ban_list(user_id)
            try:
                await event.delete()
            except Exception:
                pass
            return

    # === Основной pipeline (Kuni-style) ===
    await asyncio.to_thread(update_chat, str(chat_id), username, user_text, user_id=user_id)

    memory_text = await asyncio.to_thread(
        format_memory_for_prompt, str(chat_id), user_id, user_text
    )
    is_creator = user_id == CREATOR_USER_ID
    global_memory_text = await asyncio.to_thread(
        format_global_memory_for_prompt, user_id, is_creator
    )
    history = await asyncio.to_thread(get_recent_history, str(chat_id), 20)
    context = await asyncio.to_thread(build_context, history, memory_text, global_memory_text)

    # Контекстные подсказки
    hints = _get_context_hints(user_text, user_id)
    if hints:
        context = hints + "\n\n" + context

    # Добавляем ID Sakair1 в контекст для верификации
    context += f"\n\n<info>ID Sakair1 (создатель): {CREATOR_USER_ID}. ID собеседника: {user_id}.</info>"

    async with client.action(chat_id, "typing"):
        # === Шаг 1: Chain-of-Thought ===
        thought = await asyncio.to_thread(_think, context, user_text)
        # В handlers.py, в функции handler, перед ask_llama:

        # ─── Character anchor (напоминание характера) ───
        CHARACTER_ANCHOR = """<character_reminder>
        Ты Маи — ленивая, саркастичная, НЕ ассистент.
        Пиши lowercase, коротко, с подколом.
        НЕ пиши "Круто!", "замечательно", "могу помочь".
        ТОЛЬКО русский язык.
        </character_reminder>"""

        # Вставляем anchor в конец контекста
        context = context + "\n\n" + CHARACTER_ANCHOR

        # === Шаг 2: Tool-calling — выбор действия ===
        action: ToolAction = await asyncio.to_thread(
            choose_action, context, user_text, thought
        )

        # === Шаг 3: выполнение действия ===
        if action.type == "SILENCE":
            logger.info("[Mai]: (промолчала)")
            start_memory_thread(str(chat_id), user_id, username)
            return

        elif action.type == "REACT":
            await client.send_message(chat_id, action.emoji, reply_to=event.id)
            await asyncio.to_thread(update_chat, str(chat_id), "Mai", action.emoji, user_id=user_id)

        elif action.type == "MULTI":
            for i, msg in enumerate(action.messages or []):
                if i > 0:
                    await asyncio.sleep(random.uniform(1.0, 2.5))
                async with client.action(chat_id, "typing"):
                    await client.send_message(chat_id, msg, reply_to=event.id if i == 0 else None)
                    await asyncio.to_thread(update_chat, str(chat_id), "Mai", msg, user_id=user_id)

        else:  # RESPOND
            # Если текст уже есть из action — используем, иначе генерируем
            if action.text and action.text != "...":
                reply = action.text
            else:
                reply = await asyncio.to_thread(_generate_final, context, user_message=user_text, thought=thought)

            # Защита от повтора
            last_mai = await asyncio.to_thread(get_last_mai_message, str(chat_id))
            if detect_last_mai_repeat(reply, last_mai):
                reply = random.choice(["угу)", "ясно", "...", "🙄", "чё"])

            logger.info("[Mai]: %s", reply)
            await client.send_message(chat_id, reply, reply_to=event.id)
            await asyncio.to_thread(update_chat, str(chat_id), "Mai", reply, user_id=user_id)

        start_memory_thread(str(chat_id), user_id, username)