"""Клиент для работы с LLM (llama.cpp /completion endpoint)."""

from __future__ import annotations

import logging
import time
import re

from typing import Any, Optional

import requests
import random

from mai.config import (
    LLAMA_URL,
    LLAMA_TIMEOUT,
    GEN_N_PREDICT,
    GEN_TEMPERATURE,
    GEN_TOP_P,
    GEN_TOP_K,
    GEN_REPEAT_PENALTY,
    GEN_MIN_P,
)
from mai.prompts import SYSTEM_PROMPT
from mai.utils.text import clean_reply

logger = logging.getLogger(__name__)

# Стоп-токены для генерации
STOP_TOKENS: list[str] = [
    "<User>", "</User>", "<Mai>", "</Mai>",
    "[User]", "[Mai]",
    "\n\n", "=== ", ">>>", "<<<",
    "<|eot_id|>", "<|eom_id|>", "<|end_of_text|>",
    "User:", "Пользователь:", "Mai:", "Маи:",
]

# Триггеры, по которым обрезаем генерацию
_STOP_TRIGGERS: list[str] = [
    "===", ">>>", "<<<", "YOUR TURN",
    "(continue", "continue the conversation",
    "<|eot_id|>", "<|eom_id|>", "<|end_of_text|>",
    "DIALOGUE WILL CONTINUE",
    "User:", "Mai:", "Пользователь:", "Маи:",
    "SUMMARY:", "USER_FACT:",
    # Системные артефакты (Gemma-подобные модели любят это писать)
    "Sleeptime:", "Active:", "Responding normally",
    "User's message", "User is asking", "Context:",
    "Thought:", "Note:", "Analysis:",
    "I should respond", "Let me think",
]

# Мета-комментарии
_META_TRIGGERS: list[str] = [
    "(предполагаю", "(я не чувствую", "(вот и все)",
    "/plaintext", "(не знаю, как еще", "(конец)",
    "(я просто выполняю", "(это два разных ответов",
]


def _post_llm(payload: dict[str, Any]) -> Optional[str]:
    """Отправляет запрос к llama.cpp и возвращает сгенерированный текст."""
    try:
        r = requests.post(LLAMA_URL, json=payload, timeout=LLAMA_TIMEOUT)
        r.raise_for_status()
        return r.json().get("content", "").strip()
    except requests.RequestException as e:
        logger.error("LLM request failed: %s", e)
        return None

def clean_reply(text: str) -> str:
    """Очищает ответ LLM от мусора, повторов и мета-комментариев."""
    if not text:
        return ""

    # Stop triggers
    triggers = [
        "===", ">>>", "<<<", "YOUR TURN",
        "(continue", "continue the conversation",
        "<|eot_id|>", "<|eom_id|>", "<|end_of_text|>",
        "DIALOGUE WILL CONTINUE",
        "User:", "Mai:", "Пользователь:", "Маи:",
        "SUMMARY:", "USER_FACT:",
        "Sleeptime:", "Thought:", "User's message",
    ]
    for trigger in triggers:
        if trigger in text:
            text = text.split(trigger)[0].strip()

    # Убираем повторяющуюся пунктуацию
    text = re.sub(r'\.{4,}', '..', text)
    text = re.sub(r'\){4,}', '))', text)
    text = re.sub(r'а{4,}', 'ааа', text)
    text = re.sub(r'х{4,}', 'ххх', text)

    # Убираем мета-комментарии
    meta_triggers = [
        "(предполагаю", "(я не чувствую", "(вот и все)",
        "/plaintext", "(не знаю, как еще", "(конец)",
        "(я просто выполняю", "(это два разных ответа"
    ]
    for meta in meta_triggers:
        if meta in text:
            text = text.split(meta)[0].strip()

    # ─── КРИТИЧЕСКИ ВАЖНО: Защита от повторов фраз внутри одного сообщения ───
    # Разбиваем на предложения и удаляем дубликаты
    sentences = re.split(r'(?<=[.!?])\s+|\n', text)
    seen_phrases = set()
    unique_sentences = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # Нормализуем для сравнения (убираем пунктуацию и пробелы)
        normalized = re.sub(r'[\s\.\)\(\*\!\?]', '', sentence.lower())
        
        # Если фраза короче 5 символов или уже была — пропускаем
        if len(normalized) < 5:
            unique_sentences.append(sentence)
            continue
            
        # Проверяем на дубликат (с точностью до 80% совпадения)
        is_duplicate = False
        for seen in seen_phrases:
            # Простая проверка: если одна фраза содержит другую
            if normalized in seen or seen in normalized:
                is_duplicate = True
                break
            # Или если совпадает больше 70% слов
            words1 = set(normalized)
            words2 = set(seen)
            if len(words1 & words2) / max(len(words1 | words2), 1) > 0.7:
                is_duplicate = True
                break
        
        if not is_duplicate:
            seen_phrases.add(normalized)
            unique_sentences.append(sentence)
    
    text = ' '.join(unique_sentences)
    
    # Ограничиваем максимум 3 предложениями (даже если clean не сработал)
    if len(unique_sentences) > 3:
        text = ' '.join(unique_sentences[:3])
    
    return text.rstrip('. ').strip()


def ask_llama(context: str, user_message: str, last_mai_message: Optional[str] = None) -> str:
    """Генерирует ответ Маи на сообщение пользователя."""
    t = time.localtime()
    time_str = f"{t.tm_year}-{t.tm_mon:02d}-{t.tm_mday:02d} {t.tm_hour:02d}:{t.tm_min:02d}"

    full_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"<current_context>\nВремя сейчас: {time_str}\n</current_context>\n\n"
        f"{context}\n\n"
        f"<User>\n{user_message}\n</User>\n\n"
        f"<Mai>"
    )

    payload = {
        "prompt": full_prompt,
        "n_predict": GEN_N_PREDICT,
        "temperature": GEN_TEMPERATURE,
        "top_p": GEN_TOP_P,
        "top_k": GEN_TOP_K,
        "repeat_penalty": GEN_REPEAT_PENALTY,     
        "min_p": GEN_MIN_P,
        "stop": STOP_TOKENS + ["Sleeptime:", "Thought:", "User's message"],
    }

    try:
        r = requests.post(LLAMA_URL, json=payload, timeout=60)
        r.raise_for_status()
        reply = r.json().get("content", "").strip()
        for stop in ["User:", "Mai:", "Пользователь:"]:
            if stop in reply:
                reply = reply.split(stop)[0].strip()
        return clean_reply(reply) if reply else "..."
    except Exception as e:
        print(f"[LLAMA ERROR] {e}")
        return "чё-то у меня голова болит, потом спрошу)"


def generate_proactive(init_prompt: str) -> Optional[str]:
    """Генерирует проактивное сообщение (когда Маи пишет первая)."""
    payload = {
        "prompt": init_prompt,
        "n_predict": 120,
        "temperature": 1.0,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.15,
        "min_p": 0.05,
        "stop": STOP_TOKENS,
    }

    raw = _post_llm(payload)
    if not raw:
        return None

    for stop in ("User:", "Mai:", "Пользователь:"):
        if stop in raw:
            raw = raw.split(stop)[0].strip()

    return clean_reply(raw)


def query_llm_raw(
    prompt: str,
    n_predict: int = 80,
    temperature: float = 0.2,
    stop: Optional[list[str]] = None,
) -> Optional[str]:
    """Универсальный запрос к LLM для служебных задач (модерация, память)."""
    payload = {
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": temperature,
        "top_p": 0.9,
        "repeat_penalty": 1.2,
        "stop": stop or ["\n\n"],
    }
    return _post_llm(payload)