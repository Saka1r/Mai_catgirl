"""Очистка и постобработка текста."""

from __future__ import annotations

import re

# Триггеры, по которым обрезаем генерацию
_STOP_TRIGGERS: list[str] = [
    "===", ">>>", "<<<", "YOUR TURN",
    "(continue", "continue the conversation",
    "<|eot_id|>", "<|eom_id|>", "<|end_of_text|>",
    "DIALOGUE WILL CONTINUE",
    "User:", "Mai:", "Пользователь:", "Маи:",
    "SUMMARY:", "USER_FACT:",
]

# Мета-комментарии, которые модель может "проглатить" в текст
_META_TRIGGERS: list[str] = [
    "(предполагаю", "(я не чувствую", "(вот и все)",
    "/plaintext", "(не знаю, как еще", "(конец)",
    "(я просто выполняю", "(это два разных ответа",
]


def clean_reply(text: str | None) -> str:
    """Очищает ответ LLM от мусора, повторов и мета-комментариев."""
    if not text:
        return ""

    # Обрезаем по стоп-триггерам
    for trigger in _STOP_TRIGGERS:
        if trigger in text:
            text = text.split(trigger)[0].strip()

    # Убираем повторяющуюся пунктуацию
    text = re.sub(r"\.{4,}", "..", text)
    text = re.sub(r"\){4,}", "))", text)
    text = re.sub(r"а{4,}", "ааа", text)
    text = re.sub(r"х{4,}", "ххх", text)

    # Убираем мета-комментарии
    for meta in _META_TRIGGERS:
        if meta in text:
            text = text.split(meta)[0].strip()

    return text.rstrip(". ").strip()