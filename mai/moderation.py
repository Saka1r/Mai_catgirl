"""Модерация: проверка сообщений на токсичность."""

from __future__ import annotations

import logging
from typing import Optional

from mai.config import CREATOR_USER_ID
from mai.llm import query_llm_raw
from mai.prompts import BAN_CHECK_PROMPT

logger = logging.getLogger(__name__)

# Быстрый фильтр жесткого мата и угроз (без LLM)
_TOXIC_KEYWORDS: list[str] = [
    "тварь", "сука", "шлюха", "блядь", "пидор", "пидар", "мудак",
    "еблан", "долбоёб", "дебил", "урод", "чмо", "лох", "дура", "тупая",
    "иди на хуй", "пошла на", "отсоси", "отъебись", "заткнись",
    "убью", "ненавижу", "убейся", "сдохни", "шкура", "мразь",
]

_BAN_MARKERS: tuple[str, ...] = ("БАН", "BAN", "TOXIC", "ОСА")


def check_ban(user_text: str) -> str:
    """
    Проверяет сообщение на токсичность.
    Возвращает "БАН" или "ПРОПУСК".
    """
    user_text_lower = user_text.lower().strip()

    # 1. Быстрый фильтр по ключевым словам
    if any(kw in user_text_lower for kw in _TOXIC_KEYWORDS):
        logger.warning("[BAN FALLBACK] 🚨 Токсичное слово в: '%s'", user_text)
        return "БАН"

    if len(user_text) < 3:
        return "ПРОПУСК"

    # 2. Проверка через LLM
    prompt = BAN_CHECK_PROMPT.format(user_message=user_text)
    raw = query_llm_raw(
        prompt,
        n_predict=10,
        temperature=0.1,
        stop=["\n", "Сообщение:", "Твой ответ:", "ПРИМЕРЫ:"],
    )

    if not raw:
        return "ПРОПУСК"

    reply = raw.strip().upper()
    logger.debug("[BAN LLM RAW] '%s' на текст: '%s'", reply, user_text)

    if any(marker in reply for marker in _BAN_MARKERS):
        logger.info("[BAN DECISION] ✅ ЗАБАНИТЬ за: '%s'", user_text)
        return "БАН"

    logger.debug("[BAN DECISION] ❌ Пропустить")
    return "ПРОПУСК"