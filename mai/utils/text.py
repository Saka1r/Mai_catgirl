"""Text cleaning and post-processing."""
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

_ASSISTANT_PHRASES = [
    "Круто!", "Замечательно!", "Отлично!", "Прекрасно!",
    "это замечательное", "это прекрасное", "это отличное",
    "Может быть, ты хочешь", "Попробуй", "Давай попробуем",
    "Я люблю помогать", "Рада помочь", "Чем могу помочь",
    "Расскажи подробнее", "Давай обсудим",
]

_REPETITIVE_PATTERNS = [
    r"опять ты",
    r"снова ты",
    r"прив\)",
    r"опять\)",
    r"снова\)",
]

# Новые стоп-фразы для блокировки утечек промпта
_PROMPT_LEAK_TRIGGERS = [
    "Use the internal thought",
    "Use it as basis",
    "as the basis of your reply",
    "Your internal thought:",
    "internal thought",
    "as basis for",
    "Based on my thought",
    "According to my thought",
]

# Разрешённые эмодзи (остальные удаляем)
_ALLOWED_EMOJIS = {"😳", "😴", "🙄", ":3", "😏", "👍", "😐", "❤️"}


def clean_reply(text: str | None) -> str:
    """Очищает ответ LLM от мусора, утечек промпта и лишних символов."""
    if not text:
        return ""

    # ─── Стоп-триггеры (старые + новые) ───
    for trigger in _STOP_TRIGGERS + _PROMPT_LEAK_TRIGGERS:
        if trigger.lower() in text.lower():
            text = text.split(trigger)[0].strip()

    # ─── Удаляем утечки промпта (английские фразы) ───
    for leak in _PROMPT_LEAK_TRIGGERS:
        text = re.sub(re.escape(leak), "", text, flags=re.IGNORECASE)

    # ─── Удаляем неразрешённые эмодзи ───
    # Оставляем только из _ALLOWED_EMOJIS
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    
    def filter_emoji(match):
        emoji = match.group(0)
        # Оставляем только разрешённые
        if emoji in _ALLOWED_EMOJIS:
            return emoji
        return ""  # удаляем неразрешённые
    
    text = emoji_pattern.sub(filter_emoji, text)

    # ─── КРИТИЧЕСКИ ВАЖНО: удаляем избыточные скобки ")" ───
    # Заменяем "прив)" на "прив", "норм)" на "норм", "ок)" на "ок"
    text = re.sub(r"(\w)\)", r"\1", text)
    # Удаляем одиночные ")" в начале/конце
    text = re.sub(r"^\s*\)\s*", "", text)
    text = re.sub(r"\s*\)\s*$", "", text)
    # Удаляем множественные "))"
    text = re.sub(r"\){2,}", "", text)

    # Повторяющаяся пунктуация
    text = re.sub(r"\.{4,}", "..", text)
    text = re.sub(r"а{4,}", "ааа", text)
    text = re.sub(r"х{4,}", "ххх", text)

    # Мета-комментарии
    for meta in _META_TRIGGERS:
        if meta in text:
            text = text.split(meta)[0].strip()

    # Ассистентские фразы
    for phrase in _ASSISTANT_PHRASES:
        if phrase in text:
            text = text.replace(phrase, "").strip()

    # Детекция китайских символов
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if len(text) > 0 and chinese_chars / len(text) > 0.2:
        return ""

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
    
    # Удаляем двойные пробелы
    text = re.sub(r"\s+", " ", text).strip()
    
    return text.rstrip(". ").strip()

def detect_repetitive_pattern(text: str, last_messages: list[str]) -> bool:
    """Checks if the response repeats a pattern from the last messages."""
    if not last_messages:
        return False
    
    text_lower = text.lower()
    
    for pattern in _REPETITIVE_PATTERNS:
        if re.search(pattern, text_lower):
            for msg in last_messages[-3:]:
                if re.search(pattern, msg.lower()):
                    return True
    
    return False


def get_alternative_response(last_messages: list[str]) -> str:
    """Returns an alternative response if a repetition is detected."""
    alternatives = [
        "ну привет",
        "здарова",
        "хай",
        "о, ты",
        "ку",
        "ну здрасте",
        "привет",
    ]
    
    for alt in alternatives:
        if not any(alt in msg.lower() for msg in last_messages[-3:]):
            return alt
    
    return "привет"

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