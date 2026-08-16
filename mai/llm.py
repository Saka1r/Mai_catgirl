"""Клиент для работы с LLM (llama.cpp /completion endpoint)."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

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


def _post_llm(payload: dict[str, Any]) -> Optional[str]:
    """Отправляет запрос к llama.cpp и возвращает сгенерированный текст."""
    try:
        r = requests.post(LLAMA_URL, json=payload, timeout=LLAMA_TIMEOUT)
        r.raise_for_status()
        return r.json().get("content", "").strip()
    except requests.RequestException as e:
        logger.error("LLM request failed: %s", e)
        return None


def ask_llama(context: str, user_message: str) -> str:
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
        "stop": STOP_TOKENS,
    }

    raw = _post_llm(payload)
    if not raw:
        return "чё-то у меня голова болит, потом спрошу)"

    for stop in ("User:", "Mai:", "Пользователь:"):
        if stop in raw:
            raw = raw.split(stop)[0].strip()

    return clean_reply(raw) or "..."


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