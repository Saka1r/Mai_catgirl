"""Клиент для работы с LLM (llama.cpp /completion)."""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

from mai.config import (
    LLAMA_URL, LLAMA_TIMEOUT,
    GEN_N_PREDICT, GEN_TEMPERATURE, GEN_TOP_P, GEN_TOP_K,
    GEN_REPEAT_PENALTY, GEN_MIN_P,
)
from mai.utils.text import clean_reply

logger = logging.getLogger(__name__)

STOP_TOKENS = [
    "<User>", "</User>", "<Mai>", "</Mai>",
    "[User]", "[Mai]",
    "\n\n", "=== ", ">>>", "<<<",
    "<|eot_id|>", "<|eom_id|>", "<|end_of_text|>",
    "User:", "Пользователь:", "Mai:", "Маи:",
    "</output>", "</dialogue>", "</task>",
    "SUMMARY:", "USER_FACT:",
]


def _post_llm(payload: dict[str, Any], timeout: int | None = None) -> Optional[str]:
    """Отправляет запрос к llama.cpp."""
    try:
        r = requests.post(LLAMA_URL, json=payload, timeout=timeout or LLAMA_TIMEOUT)
        r.raise_for_status()
        return r.json().get("content", "").strip()
    except requests.RequestException as e:
        logger.error("LLM request failed: %s", e)
        return None


def query_llm_raw(
    prompt: str,
    n_predict: int = 80,
    temperature: float = 0.2,
    stop: Optional[list[str]] = None,
    timeout: int | None = None,
) -> Optional[str]:
    """Универсальный запрос к LLM."""
    payload = {
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": temperature,
        "top_p": 0.9,
        "repeat_penalty": 1.2,
        "stop": stop or ["\n\n"],
    }
    return _post_llm(payload, timeout=timeout)


def generate_response(prompt: str, n_predict: int | None = None) -> str:
    """Генерация ответа Маи с параметрами из конфига."""
    payload = {
        "prompt": prompt,
        "n_predict": n_predict or GEN_N_PREDICT,
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