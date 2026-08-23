"""Работа с файловым хранилищем: чаты, пользователи, глобальная память."""

from __future__ import annotations

import json
import logging
import os
import time
from copy import deepcopy
from datetime import datetime
from typing import Any, Optional

from mai.config import CHATS_DIR, USERS_DIR, GLOBAL_MEMORY_FILE
from mai.models import CHAT_SCHEMA, USER_SCHEMA, GLOBAL_MEMORY_SCHEMA

logger = logging.getLogger(__name__)


# ─── Базовые операции с JSON ─────────────────────────────────────────────────

def load_json(path: str, default: dict) -> dict[str, Any]:
    """Загружает JSON из файла. Возвращает копию default, если файла нет."""
    if not os.path.exists(path):
        return deepcopy(default)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Ошибка чтения %s: %s", path, e)
        return deepcopy(default)


def save_json(path: str, data: dict[str, Any]) -> None:
    """Сохраняет dict в JSON-файл, создавая директории при необходимости."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        logger.error("Ошибка записи %s: %s", path, e)


# ─── Чаты ─────────────────────────────────────────────────────────────────────

def chat_path(chat_id: str | int) -> str:
    return f"{CHATS_DIR}/{chat_id}.json"


def load_chat(chat_id: str | int) -> dict[str, Any]:
    data = load_json(chat_path(chat_id), CHAT_SCHEMA)
    data.setdefault("messages", [])
    data.setdefault("short_term", [])
    data.setdefault("memory", {"summary": "", "facts": [], "last_processed_index": 0})
    return data


def save_chat(chat_id: str | int, data: dict[str, Any]) -> None:
    save_json(chat_path(chat_id), data)


def create_chat(chat_id: str | int) -> None:
    path = chat_path(chat_id)
    if os.path.exists(path):
        return
    chat_data = deepcopy(CHAT_SCHEMA)
    chat_data["chat_id"] = str(chat_id)
    save_chat(chat_id, chat_data)


def update_chat(
    chat_id: str | int,
    role: str,
    message: str,
    user_id: Optional[int] = None,
) -> None:
    create_chat(chat_id)
    chat_data = load_chat(chat_id)
    chat_data["messages"].append(
        {
            "id": len(chat_data["messages"]) + 1,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "role": role,
            "user_id": str(user_id) if user_id is not None else None,
            "content": message,
        }
    )
    chat_data["short_term"] = chat_data["messages"][-20:]
    save_chat(chat_id, chat_data)


def get_recent_history(chat_id: str | int, limit: int = 20) -> list[dict[str, Any]]:
    return load_chat(chat_id)["messages"][-limit:]


def clear_chat(chat_id: str | int) -> None:
    path = chat_path(chat_id)
    if os.path.exists(path):
        os.remove(path)


# ─── Пользователи ─────────────────────────────────────────────────────────────

def user_path(user_id: str | int) -> str:
    return f"{USERS_DIR}/{user_id}.json"


def load_user(user_id: str | int) -> dict[str, Any]:
    return load_json(user_path(user_id), USER_SCHEMA)


def save_user(user_id: str | int, data: dict[str, Any]) -> None:
    save_json(user_path(user_id), data)


def add_user_fact(user_id: str | int, fact: str) -> None:
    fact = fact.strip()
    if not fact:
        return
    user = load_user(user_id)
    if fact not in user["facts"]:
        user["facts"].append(fact)
    user["facts"] = user["facts"][-50:]
    save_user(user_id, user)


def append_thought(
    user_id: str | int,
    thought: str,
    emotion: str = "neutral",
    chat_id: Optional[str | int] = None,
) -> None:
    user = load_user(user_id)
    user["thought_journal"].append(
        {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "chat_id": str(chat_id),
            "emotion": emotion,
            "thought": thought.strip(),
        }
    )
    user["thought_journal"] = user["thought_journal"][-20:]
    save_user(user_id, user)


# ─── Глобальная память ────────────────────────────────────────────────────────

def update_user_global_after_analysis(
    user_id: int,
    emotion: str | None = None,
    detailed_summary: str | None = None,
    key_facts: list[str] | None = None,
) -> None:
    """Обновляет глобальную память после анализа диалога (из process_memory)."""
    memory = load_global_memory()
    users = memory.setdefault("users_index", {})
    user_id_str = str(user_id)

    if user_id_str not in users:
        return

    user = users[user_id_str]
    creator_only = user.setdefault("creator_only", {})

    # Обновляем эмоцию Маи
    if emotion:
        emotions = creator_only.setdefault("emotional_history", [])
        emotions.append(emotion)
        creator_only["emotional_history"] = emotions[-10:]

    # Обновляем детальное описание
    if detailed_summary:
        creator_only["detailed_summary"] = detailed_summary

    # Обновляем ключевые факты
    if key_facts:
        facts = creator_only.setdefault("key_facts", [])
        for fact in key_facts:
            fact = fact.strip()
            if fact and fact not in facts:
                facts.append(fact)
        creator_only["key_facts"] = facts[-10:]

    save_global_memory(memory)

def load_global_memory() -> dict[str, Any]:
    return load_json(GLOBAL_MEMORY_FILE, GLOBAL_MEMORY_SCHEMA)


def save_global_memory(data: dict[str, Any]) -> None:
    data["last_updated"] = datetime.now().isoformat()
    save_json(GLOBAL_MEMORY_FILE, data)


def has_user_written(user_id: str | int) -> bool:
    """Быстрая проверка: писал ли этот человек Маи?"""
    memory = load_global_memory()
    return str(user_id) in memory.get("users_index", {})


def get_user_public_summary(user_id: str | int) -> str:
    """Публичная информация о пользователе (для всех)."""
    memory = load_global_memory()
    user = memory.get("users_index", {}).get(str(user_id))
    if not user:
        return "Этот человек мне не писал."
    return user.get("public_summary", "Я не помню деталей.")


def get_user_creator_details(user_id: str | int) -> Optional[dict[str, Any]]:
    """Полная информация о пользователе (только для создателя)."""
    memory = load_global_memory()
    user = memory.get("users_index", {}).get(str(user_id))
    if not user:
        return None
    return user.get("creator_only", {})


def update_user_interaction(
    user_id: int,
    username: str,
    chat_id: int,
    message_preview: str,
    emotion: str | None = None,
) -> None:
    """Обновляет глобальную память при каждом взаимодействии."""
    memory = load_global_memory()
    users = memory.setdefault("users_index", {})
    user_id_str = str(user_id)
    now = datetime.now().isoformat()

    if user_id_str not in users:
        users[user_id_str] = {
            "user_id": user_id_str,
            "username": username,
            "first_seen": now,
            "last_seen": now,
            "total_messages": 1,
            "total_chats": 1,
            "relationship": 0,
            "is_blocked": False,
            "tags": [],
            "public_summary": f"Этот человек написал мне впервые. Имя: {username}.",
            "creator_only": {
                "detailed_summary": f"Новый пользователь {username} написал в чат {chat_id}.",
                "key_facts": [],
                "emotional_history": [emotion] if emotion else [],
                "last_conversation_preview": message_preview[:100],
                "chat_ids": [str(chat_id)],
            },
        }
    else:
        user = users[user_id_str]
        user["last_seen"] = now
        user["total_messages"] += 1

        chat_ids = user["creator_only"].setdefault("chat_ids", [])
        if str(chat_id) not in chat_ids:
            chat_ids.append(str(chat_id))
            user["total_chats"] += 1

        user["creator_only"]["last_conversation_preview"] = message_preview[:100]
        user["public_summary"] = (
            f"Этот человек писал мне {user['total_messages']} раз. "
            f"Последнее сообщение: {now.split('T')[0]}."
        )

    memory["users_index"] = users
    stats = memory.setdefault("global_stats", {})
    stats["total_unique_users"] = len(users)
    stats["total_messages_processed"] = stats.get("total_messages_processed", 0) + 1
    
    # Самый активный пользователь
    if users:
        most_active = max(users.values(), key=lambda u: u["total_messages"])
        stats["most_active_user"] = most_active["user_id"]
    
    # Среднее число сообщений
    if users:
        stats["average_messages_per_user"] = round(
            stats["total_messages_processed"] / len(users), 1
        )
    save_global_memory(memory)


def can_access_user_details(requester_id: int, target_user_id: int) -> str | bool:
    """Проверка прав доступа к деталям пользователя."""
    from mai.config import CREATOR_USER_ID

    if requester_id == CREATOR_USER_ID:
        return True
    if requester_id == target_user_id:
        return "public_only"
    return "fact_only"