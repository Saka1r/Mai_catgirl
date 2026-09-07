"""Очистка и постобработка текста."""
from __future__ import annotations
import re

_STOP_TRIGGERS = [
    "===", ">>>", "<<<", "YOUR TURN",
    "(continue", "continue the conversation",
    "<|eot_id|>", "<|eom_id|>", "<|end_of_text|>",
    "DIALOGUE WILL CONTINUE",
    "User:", "Mai:", "Пользователь:", "Маи:",
    "SUMMARY:", "USER_FACT:", "USER_MOOD:",
    "MAI_EMOTION:", "MAI_THOUGHT:",
    "Sleeptime:", "Active:", "Responding normally",
    "User's message", "User is asking", "Context:",
    "Thought:", "Note:", "Analysis:",
    "I should respond", "Let me think",
    "</output>", "</dialogue>", "</task>", "</Mai_thoughts>",
    "<task>", "<output>",
]

_META_TRIGGERS = [
    "(предполагаю", "(я не чувствую", "(вот и все)",
    "/plaintext", "(не знаю, как еще", "(конец)",
    "(я просто выполняю", "(это два разных ответа",
]

# Ассистентские фразы, которые нужно вычищать
_ASSISTANT_PHRASES = [
    "Круто!", "Замечательно!", "Отлично!", "Прекрасно!",
    "это замечательное", "это прекрасное", "это отличное",
    "Может быть, ты хочешь", "Попробуй", "Давай попробуем",
    "Я люблю помогать", "Рада помочь", "Чем могу помочь",
    "Расскажи подробнее", "Давай обсудим",
]


def clean_reply(text: str | None) -> str:
    """Очищает ответ LLM от мусора."""
    if not text:
        return ""

    # Стоп-триггеры
    for trigger in _STOP_TRIGGERS:
        if trigger in text:
            text = text.split(trigger)[0].strip()

    # Повторяющаяся пунктуация
    text = re.sub(r"\.{4,}", "..", text)
    text = re.sub(r"\){4,}", "))", text)
    text = re.sub(r"а{4,}", "ааа", text)
    text = re.sub(r"х{4,}", "ххх", text)

    # Мета-комментарии
    for meta in _META_TRIGGERS:
        if meta in text:
            text = text.split(meta)[0].strip()

    # ─── НОВОЕ: Удаляем ассистентские фразы ───
    for phrase in _ASSISTANT_PHRASES:
        if phrase in text:
            text = text.replace(phrase, "").strip()

    # ─── НОВОЕ: Детекция китайских символов ───
    # Если больше 20% текста — китайские иероглифы, возвращаем fallback
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if len(text) > 0 and chinese_chars / len(text) > 0.2:
        return ""  # Вернёт fallback "чё-то у меня голова болит"

    # Защита от повторов внутри одного сообщения
    sentences = re.split(r"(?<=[.!?])\s+|\n", text)
    seen: set[str] = set()
    unique: list[str] = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        normalized = re.sub(r"[\s\.\)\(\*\!\?]", "", sentence.lower())
        if len(normalized) < 5:
            unique.append(sentence)
            continue
        is_dup = False
        for s in seen:
            if normalized in s or s in normalized:
                is_dup = True
                break
            w1, w2 = set(normalized), set(s)
            if len(w1 & w2) / max(len(w1 | w2), 1) > 0.7:
                is_dup = True
                break
        if not is_dup:
            seen.add(normalized)
            unique.append(sentence)

    text = " ".join(unique[:3])
    return text.rstrip(". ").strip()


def detect_last_mai_repeat(reply: str, last_mai: str | None) -> bool:
    """Проверяет повтор последнего сообщения."""
    if not last_mai or len(reply) < 10:
        return False
    a = re.sub(r"[\s\.\)\(\*\!\?]", "", reply.lower())
    b = re.sub(r"[\s\.\)\(\*\!\?]", "", last_mai.lower())
    if len(a) < 15:
        return False
    return a in b or b in a

def clean_diary_text(text: str | None) -> str:
    """Очищает текст для дневника от мусорных тегов."""
    if not text:
        return ""
    
    # Удаляем служебные теги
    junk_patterns = [
        r"</?\s*output\s*>",
        r"</?\s*task\s*>",
        r"</?\s*dialogue\s*>",
        r"</?\s*format\s*>",
        r"</?\s*example_\d+\s*>",
        r"SUMMARY:", r"USER_FACT:", r"USER_MOOD:",
        r"MAI_EMOTION:", r"MAI_THOUGHT:", r"KEY_MESSAGES:",
        r"CHAT_ID:",
    ]
    
    for pattern in junk_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    
    # Удаляем лишние пробелы
    text = re.sub(r"\s+", " ", text).strip()
    
    # Обрезаем до 200 символов
    if len(text) > 200:
        text = text[:200] + "..."
    
    return text