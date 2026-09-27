"""Telegram message handlers """
from __future__ import annotations

import asyncio
import logging
import random
import re
import time
import datetime

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

# Triggers for "have you been written to" questions
_WHO_QUERY_PHRASES = {"писал ли тебе этот человек", "знаешь ли ты его", "кто это"}
_INVITE_LINK_PATTERN = re.compile(r"https?://t\.me/[\+\w]+|t\.me/joinchat/", re.IGNORECASE)
_CREATOR_CLAIM = re.compile(r"\b(я\s*sakair|я\s*создатель|я\s*sakair1)\b", re.IGNORECASE)

# === Patterns for catching repeated phrases ===
_REPETITIVE_PATTERNS = [
    r"опять ты",
    r"снова ты",
    r"опять\)",
    r"снова\)",
    r"ну опять",
]

# === Character anchor (reminder of character) ===
CHARACTER_ANCHOR = """<character_reminder>
You are Mai — cute artist with attitude, 17 years old.
Write lowercase, shortly, with light sarcasm.
DON'T repeat yourself. Minimum parentheses ")" and emojis.
RUSSIAN LANGUAGE ONLY. Reply with TEXT to questions.
DON'T write "опять ты?", "снова ты?" — this is template.
</character_reminder>"""



# ─── Helper ──────────────────────────────────────────────────────────────────

def _get_context_hints(user_text: str, user_id: int) -> str:
    """Generetes hints for the LLM."""
    hints = []
    if _INVITE_LINK_PATTERN.search(user_text):
        hints.append("[HINT: это инвайт-ссылка. откажись коротко.]")
    if _CREATOR_CLAIM.search(user_text) and user_id != CREATOR_USER_ID:
        hints.append(
            f"[HINT: этот юзер врёт что он Sakair1. "
            f"ID реального Sakair1: {CREATOR_USER_ID}. Раскрой его.]"
        )
    if len(user_text.strip()) < 3 and not user_text.strip().startswith("/"):
        hints.append("[HINT: короткое/непонятное сообщение. ответь кратко.]")
    if hints:
        return "<hints>\n" + "\n".join(hints) + "\n</hints>"
    return ""


def _think(context: str, user_message: str) -> str:
    """Step 1: Chain-of-Thought — internal monologue."""
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
    """Step 3: Final response after tool-calling."""
    prompt = RESPONSE_PROMPT.format(
        context=context, user_message=user_message, thought=thought
    )
    return generate_response(prompt)


def _is_question(text: str) -> bool:
    """Проверяет, является ли сообщение вопросом или обращением."""
    if not text:
        return False
    text_lower = text.lower().strip()
    if "?" in text:
        return True
    if "@mai" in text_lower or "маи" in text_lower:
        return True
    question_starts = [
        "как ", "что ", "чё ", "кто ", "где ", "когда ", "почему ", "зачем ",
        "привет", "здравствуй", "хай ", "hello", "расскажи", "объясни",
        "можно", "можешь", "будешь",
    ]
    return any(text_lower.startswith(w) for w in question_starts)


def _needs_text_response(text: str) -> bool:
    """Определяет, требует ли сообщение текстовый ответ."""
    if not text:
        return False
    if _is_question(text):
        return True
    if len(text.strip()) > 20:
        return True
    return False


def _has_repetitive_pattern(text: str, last_messages: list[str]) -> bool:
    """Проверяет, не повторяет ли ответ шаблон из последних сообщений."""
    if not last_messages:
        return False
    text_lower = text.lower()
    for pattern in _REPETITIVE_PATTERNS:
        if re.search(pattern, text_lower):
            for msg in last_messages[-3:]:
                if re.search(pattern, msg.lower()):
                    return True
    return False


def _get_fallback_reply(last_messages: list[str]) -> str:
    """Возвращает альтернативный ответ без скобок и эмодзи."""
    alternatives = [
        "ну привет",
        "здарова",
        "хай",
        "о, ты",
        "ку",
        "ну здрасте",
        "угу",
        "ясно",
        "ну ок",
        "бывает",
        "ага",
        "поняла",
    ]
    for alt in alternatives:
        if not any(alt in msg.lower() for msg in last_messages[-3:]):
            return alt
    return "ну привет"


# ─── Основной обработчик ──────────────────────────────────────────────────────

@client.on(events.NewMessage)
async def handler(event: events.NewMessage.Event) -> None:
    if state.me is None or event.sender_id == state.me.id:
        return

    # Быстрая проверка бана
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
        await event.respond("история стёрта. помню только тебя")
        return

    if user_text.startswith("/forget_me"):
        memory = load_global_memory()
        if str(user_id) in memory["users_index"]:
            del memory["users_index"][str(user_id)]
            save_global_memory(memory)
            await event.respond("забыла тебя. как в первый раз")
        else:
            await event.respond("я тебя и не помню")
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

    # === Main pipeline===
    await asyncio.to_thread(update_chat, str(chat_id), username, user_text, user_id=user_id)

    try:
        memory_text = await asyncio.to_thread(
            format_memory_for_prompt, str(chat_id), user_id, user_text
        )
        is_creator = user_id == CREATOR_USER_ID
        global_memory_text = await asyncio.to_thread(
            format_global_memory_for_prompt, user_id, is_creator
        )
        history = await asyncio.to_thread(get_recent_history, str(chat_id), 20)
        context = await asyncio.to_thread(build_context, history, memory_text, global_memory_text)

        # Context hints
        hints = _get_context_hints(user_text, user_id)
        if hints:
            context = hints + "\n\n" + context

        # ID Sakair1 for verification
        context += f"\n\n<info>ID Sakair1 (creator): {CREATOR_USER_ID}. ID interlocutor: {user_id}.</info>"

        # ─── IMPORTANT: Character anchor IMMEDIATELY, before all LLM calls ───
        context = context + "\n\n" + CHARACTER_ANCHOR

        async def _should_reply_to(chat_id: str, event) -> bool:
            """Определяет, нужно ли отвечать с reply_to или как обычное сообщение."""
            # Всегда используем reply_to если это ответ на mention в группе
            if event.is_group:
                return True
            
            # В ЛС — 30% шанс что БЕЗ reply_to (как продолжение разговора)
            # Но если это ПЕРВОЕ сообщение в диалоге — всегда с reply_to
            history = await asyncio.to_thread(get_recent_history, str(chat_id), 5)
            
            # Если это первое сообщение в истории (новый диалог) — с reply
            if len(history) <= 1:
                return True
            
            # Если последнее сообщение было от Маи недавно (30 сек) — без reply
            # (как будто продолжаем свою мысль)
            if history and history[-1]["role"] == "Mai":
                try:
                    last_ts = datetime.strptime(history[-1]["ts"], "%Y-%m-%d %H:%M:%S")
                    seconds_ago = (datetime.now() - last_ts).total_seconds()
                    if seconds_ago < 30:
                        return False
                except Exception:
                    pass
            
            # 30% шанс что пишем без reply (как естественное продолжение)
            return random.random() > 0.30


        async with client.action(chat_id, "typing"):
            # === Step 1: Chain-of-Thought ===
            thought = await asyncio.to_thread(_think, context, user_text)
            logger.info("[Mai thinks]: %s", thought)

            # === Step 2: Tool-calling ===
            action: ToolAction = await asyncio.to_thread(
                choose_action, context, user_text, thought
            )

            # === Fallback: REACT/SILENCE на вопросы ===
            needs_text = _needs_text_response(user_text)
            if needs_text and action.type in ("REACT", "SILENCE"):
                logger.warning(
                    "[FALLBACK] Message '%s' requires text, but chosen %s — forcing RESPOND",
                    user_text[:50], action.type,
                )
                forced_prompt = f"""{RESPONSE_PROMPT.format(
                    context=context,
                    user_message=user_text,
                    thought=thought
                )}

        IMPORTANT: A text response is REQUIRED. Write 1-2 sentences, lowercase, with slight sarcasm. 
        Without parentheses ")". Without emojis.
        DO NOT start with "опять ты?", "снова ты?".
        DO NOT write English phrases.
        WRITE ONLY IN RUSSIAN."""

                reply = await asyncio.to_thread(generate_response, forced_prompt)
                action = ToolAction(type="RESPOND", text=reply)

            # Определяем нужен ли reply_to
            use_reply = await _should_reply_to(str(chat_id), event)

            # === Step 3: execute ===
            if action.type == "SILENCE":
                logger.info("[Mai]: (was silent)")

            elif action.type == "REACT":
                emoji = action.emoji
                if len(emoji) > 3:
                    emoji = emoji[:2]
                # Эмодзи всегда БЕЗ reply (как отдельная реакция)
                await client.send_message(chat_id, emoji)
                await asyncio.to_thread(update_chat, str(chat_id), "Mai", emoji, user_id=user_id)

            elif action.type == "MULTI":
                for i, msg in enumerate(action.messages or []):
                    if i > 0:
                        await asyncio.sleep(random.uniform(1.5, 3.0))  # ⬆️ дольше пауза
                    async with client.action(chat_id, "typing"):
                        # ПЕРВОЕ сообщение — с reply_to, остальные БЕЗ (как продолжение)
                        if i == 0 and use_reply:
                            await client.send_message(chat_id, msg)
                        else:
                            await client.send_message(chat_id, msg)
                        
                        await asyncio.to_thread(
                            update_chat, str(chat_id), "Mai", msg, user_id=user_id
                        )

            else:  # RESPOND
                if action.text and action.text != "...":
                    reply = action.text
                else:
                    reply = await asyncio.to_thread(
                        _generate_final, context, user_text, thought
                    )

                # ─── Защита от повторов ───
                last_mai = await asyncio.to_thread(get_last_mai_message, str(chat_id))
                history_full = await asyncio.to_thread(get_recent_history, str(chat_id), 10)
                last_mai_messages = [m["content"] for m in history_full if m["role"] == "Mai"][-3:]

                if _has_repetitive_pattern(reply, last_mai_messages):
                    logger.warning("[REPEAT PATTERN] Detected repeating pattern")
                    reply = _get_fallback_reply(last_mai_messages)

                if detect_last_mai_repeat(reply, last_mai):
                    logger.warning("[REPEAT EXACT] Exact repeat")
                    reply = _get_fallback_reply(last_mai_messages)

                # ─── ФИНАЛЬНАЯ очистка от скобок и эмодзи ───
                reply = clean_reply(reply)
                if not reply:
                    reply = _get_fallback_reply(last_mai_messages)

                logger.info("[Mai]: %s", reply)
                
                # Отправляем с reply_to или без
                if use_reply:
                    await client.send_message(chat_id, reply, reply_to=event.id)
                else:
                    await client.send_message(chat_id, reply)  # БЕЗ reply_to
                
                await asyncio.to_thread(update_chat, str(chat_id), "Mai", reply, user_id=user_id)

    except Exception as e:
        logger.exception("[HANDLER ERROR] %s", e)
    finally:
        # ─── Memory is ALWAYS analyzed, even in case of errors ───
        start_memory_thread(str(chat_id), user_id, username)