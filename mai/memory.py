"""Обработка памяти: извлечение фактов, форматирование контекста."""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from mai.config import CREATOR_USER_ID
from mai.diary import search_diary, write_diary_entry
from mai.llm import query_llm_raw
from mai.prompts import MEMORY_EXTRACT_PROMPT
from mai.utils.text import clean_reply, clean_diary_text
from mai.storage import (
    add_user_fact, append_thought, load_chat, load_user,
    save_chat, save_user, update_user_global_after_analysis,
)

logger = logging.getLogger(__name__)


def parse_memory_text(text: str) -> dict[str, str]:
    """Парсит ответ LLM-анализатора."""
    data: dict[str, str] = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key_part, val_part = line.split(":", 1)
        key = key_part.strip().lower()
        val = val_part.strip()
        if not val or val.upper() in ("НЕТ", "NONE", ""):
            continue

        if any(k in key for k in ("итог", "сумма", "summary", "выжимка")):
            data["SUMMARY"] = val
        elif any(k in key for k in ("факт о пользователе", "user_fact")):
            data["USER_FACT"] = val
        elif any(k in key for k in ("факт о ситуации", "chat_fact")):
            data["CHAT_FACT"] = val
        elif any(k in key for k in ("мысль маи", "mai_thought")):
            data["THOUGHT"] = val
        elif any(k in key for k in ("настроение", "user_mood")):
            data["USER_MOOD"] = val
        elif any(k in key for k in ("эмоция маи", "mai_emotion", "эмоция")):
            data["EMOTION"] = val
    return data


def process_memory(chat_id: str | int, user_id: Optional[int], username: str = "") -> None:
    """Фоновый процесс: анализирует диалог и обновляет память."""
    try:
        chat = load_chat(chat_id)
        mem = chat.get("memory", {})
        start = mem.get("last_processed_index", 0)
        messages = chat.get("messages", [])

        if len(messages) - start < 3:
            return

        new_messages = messages[start:][-10:]
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in new_messages)
        
        # Добавляем chat_id в промпт
        prompt = MEMORY_EXTRACT_PROMPT.format(transcript=transcript)
        # Передаём chat_id для записи в дневник
        prompt = prompt.replace("{chat_id_hint}", str(chat_id))

        raw = query_llm_raw(
            prompt,
            n_predict=250,  # ⬆️ Увеличили для подробных записей
            temperature=0.3,
            stop=["\n\n", "User:", "Mai:", "Пользователь:", "<output>", "</dialogue>"],
        )
        data = parse_memory_text(raw) if raw else {}

        mem["last_processed_index"] = len(messages)

        if data:
            if data.get("SUMMARY"):
                mem["summary"] = data["SUMMARY"]
            if data.get("CHAT_FACT"):
                mem.setdefault("facts", []).append(data["CHAT_FACT"])
                mem["facts"] = mem["facts"][-20:]

            if user_id:
                user = load_user(user_id)
                user["user_id"] = str(user_id)
                if data.get("USER_FACT"):
                    add_user_fact(user_id, data["USER_FACT"])
                if data.get("SUMMARY"):
                    user["summary"] = data["SUMMARY"]
                if data.get("USER_MOOD"):
                    user["mood"] = data["USER_MOOD"]
                try:
                    delta = int(data.get("RELATIONSHIP_DELTA", 0))
                except (ValueError, TypeError):
                    delta = 0
                user["relationship"] = max(-10, min(10, user.get("relationship", 0) + delta))
                save_user(user_id, user)

                if data.get("THOUGHT"):
                    # ─── Чистим мысль от мусора ───
                    thought = clean_diary_text(data["THOUGHT"])
                    emotion = clean_diary_text(data.get("EMOTION", "нейтральная"))
                    append_thought(user_id, thought, emotion, chat_id)

                # Синхронизация с глобальной памятью
                update_user_global_after_analysis(
                    user_id=user_id,
                    emotion=emotion if thought else None,
                    detailed_summary=data.get("SUMMARY"),
                    key_facts=[data["USER_FACT"]] if data.get("USER_FACT") else None,
                )

                # Запись в markdown дневник
                if data.get("SUMMARY") or data.get("USER_FACT"):
                    try:
                        write_diary_entry({
                            "username": username or "неизвестно",
                            "emotion": clean_diary_text(data.get("EMOTION", "нейтральная")),
                            "summary": clean_diary_text(data.get("SUMMARY", "")),
                            "facts": [clean_diary_text(data["USER_FACT"])] if data.get("USER_FACT") else [],
                            "thought": clean_diary_text(data.get("THOUGHT", "")),
                            "chat_id": str(chat_id),  # ⬅️ НОВОЕ
                            "key_messages": data.get("KEY_MESSAGES", ""),  # ⬅️ НОВОЕ
                        })
                    except Exception as e:
                        logger.error("[DIARY] write error: %s", e)

        chat["memory"] = mem
        save_chat(chat_id, chat)

    except Exception as e:
        logger.exception("Memory processing error: %s", e)


def start_memory_thread(chat_id: str | int, user_id: Optional[int], username: str = "") -> None:
    """Запускает обработку памяти в фоновом потоке."""
    threading.Thread(
        target=process_memory,
        args=(str(chat_id), user_id, username),
        daemon=True,
    ).start()


def format_memory_for_prompt(
    chat_id: str | int,
    user_id: Optional[int] = None,
    user_message: str = "",
) -> str:
    """Форматирует память для вставки в промпт."""
    parts: list[str] = []
    chat = load_chat(chat_id)
    mem = chat.get("memory", {})

    if mem.get("summary"):
        parts.append(f"Контекст текущего чата: {mem['summary']}")
    if mem.get("facts"):
        facts_str = ", ".join(mem["facts"][-5:])
        parts.append(f"Важное из чата: {facts_str}")

    if user_id:
        user = load_user(user_id)
        if user.get("summary"):
            parts.append(f"Что Маи помнит об этом человеке: {user['summary']}")
        if user.get("facts"):
            facts_str = ", ".join(user["facts"][-5:])
            parts.append(f"Факты о человеке: {facts_str}")
        if user.get("mood"):
            parts.append(f"Настроение собеседника: {user['mood']}")
        thoughts = user.get("thought_journal", [])[-2:]
        if thoughts:
            t_str = " | ".join(f"({t['emotion']}) {t['thought']}" for t in thoughts)
            parts.append(f"Недавние мысли Маи: {t_str}")

    # RAG по дневнику
    if user_message:
        diary_ctx = search_diary(user_message, top_k=2)
        if diary_ctx:
            parts.append(f"<diary_recall>\n{diary_ctx}\n</diary_recall>")

    return "\n".join(parts)


def format_global_memory_for_prompt(user_id: int, is_creator: bool = False) -> str:
    """Форматирует глобальную память для промпта."""
    from mai.storage import load_global_memory

    memory = load_global_memory()
    parts: list[str] = []

    if memory.get("global_facts"):
        facts_str = " | ".join(memory["global_facts"][-5:])
        parts.append(f"Глобальные факты: {facts_str}")

    user = memory.get("users_index", {}).get(str(user_id))
    if user:
        if is_creator:
            details = user.get("creator_only", {})
            parts.append(
                f"Что я знаю: {details.get('detailed_summary', 'Ничего особенного.')}"
            )
            if details.get("key_facts"):
                facts_str = ", ".join(details["key_facts"][-5:])
                parts.append(f"Ключевые факты: {facts_str}")
        else:
            parts.append(f"Что я помню: {user.get('public_summary', 'Не помню.')}")
    else:
        parts.append("Этот человек мне не писал. Я его не знаю.")

    return "\n".join(parts)


def build_context(
    history: list[dict[str, Any]],
    memory_text: str = "",
    global_memory_text: str = "",
) -> str:
    """Собирает полный контекст для LLM."""
    parts: list[str] = []
    if global_memory_text:
        parts.append(f"<global_memory>\n{global_memory_text}\n</global_memory>")
    if memory_text:
        parts.append(f"<memory>\n{memory_text}\n</memory>")

    dialog_lines = []
    for msg in history:
        role = "User" if msg["role"] != "Mai" else "Mai"
        dialog_lines.append(f"{role}: {msg['content']}")
    if dialog_lines:
        parts.append("<history>\n" + "\n".join(dialog_lines) + "\n</history>")

    return "\n\n".join(parts)