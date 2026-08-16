"""Структуры данных (схемы JSON-хранилищ)."""

from __future__ import annotations

from typing import Any

CHAT_SCHEMA: dict[str, Any] = {
    "chat_id": None,
    "messages": [],
    "short_term": [],
    "memory": {
        "summary": "",
        "facts": [],
        "last_processed_index": 0,
    },
}

USER_SCHEMA: dict[str, Any] = {
    "user_id": None,
    "username": None,
    "facts": [],
    "summary": "",
    "mood": "neutral",
    "relationship": 0,
    "thought_journal": [],
}

GLOBAL_MEMORY_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "last_updated": "",
    "users_index": {},
    "global_stats": {
        "total_unique_users": 0,
        "total_messages_processed": 0,
        "most_active_user": None,
        "busiest_day": None,
        "average_messages_per_user": 0,
    },
    "global_facts": ["Создатель Маи — Sakair1."],
}