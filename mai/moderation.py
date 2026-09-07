"""Модерация: проверка сообщений на токсичность."""
from __future__ import annotations

import logging

from mai.llm import query_llm_raw
from mai.prompts import BAN_CHECK_PROMPT

logger = logging.getLogger(__name__)

_TOXIC_KEYWORDS = [
    "тварь", "сука", "шлюха", "блядь", "пидор", "пидар", "мудак",
    "еблан", "долбоёб", "дебил", "урод", "чмо", "лох", "дура", "тупая",
    "иди на хуй", "пошла на", "отсоси", "отъебись", "заткнись",
    "убью", "ненавижу", "убейся", "сдохни", "шкура", "мразь",
]


def check_ban(user_text: str) -> str:
    """Возвращает 'БАН' или 'ПРОПУСК'."""
    user_text_lower = user_text.lower().strip()

    if any(kw in user_text_lower for kw in _TOXIC_KEYWORDS):
        logger.warning("[BAN FALLBACK] 🚨 Токсичное слово: '%s'", user_text)
        return "БАН"

    if len(user_text) < 3:
        return "ПРОПУСК"

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
    if any(m in reply for m in ("БАН", "BAN", "TOXIC", "ОСА")):
        logger.info("[BAN] ✅ за: '%s'", user_text)
        return "БАН"
    return "ПРОПУСК"