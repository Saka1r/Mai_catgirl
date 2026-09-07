"""Tool-calling система — Маи выбирает действие, а не просто пишет текст."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from mai.llm import query_llm_raw
from mai.prompts import TOOLS_PROMPT, TOOL_DECISION_PROMPT
from mai.utils.text import clean_reply

logger = logging.getLogger(__name__)


@dataclass
class ToolAction:
    """Действие, выбранное Маи."""
    type: Literal["RESPOND", "MULTI", "REACT", "SILENCE"]
    text: str = ""
    messages: list[str] | None = None
    emoji: str = ""


def parse_action(raw: str) -> ToolAction:
    """Парсит сырой вывод LLM в ToolAction."""
    if not raw:
        return ToolAction(type="RESPOND", text="...")

    raw = raw.strip()
    raw_lower = raw.lower()

    # ─── Ловим объяснения модели вместо чистого формата ───
    # Модель может написать "Использовать SILENCE потому что..."
    # или "Выбираю MULTI, так как..."
    if any(kw in raw_lower for kw in ("silenсe", "silence", "молч")):
        return ToolAction(type="SILENCE")
    
    if any(kw in raw_lower for kw in ("react", "реаг")) and "|" not in raw:
        # Модель хочет реагировать, но не дала эмодзи
        return ToolAction(type="REACT", emoji="😐")

    # ─── Стандартный парсинг ───
    if raw.startswith("SILENCE"):
        return ToolAction(type="SILENCE")

    if raw.startswith("REACT|"):
        emoji = raw.split("|", 1)[1].strip()
        emoji = re.sub(r"[^\U00010000-\U0010ffff\U00002600-\U000027BF]", "", emoji)
        if not emoji:
            emoji = "😐"
        return ToolAction(type="REACT", emoji=emoji)

    if raw.startswith("MULTI|"):
        parts = [p.strip() for p in raw.split("|")[1:] if p.strip()]
        parts = [clean_reply(p) for p in parts][:4]
        if not parts:
            return ToolAction(type="SILENCE")
        return ToolAction(type="MULTI", messages=parts)

    if raw.startswith("RESPOND|"):
        text = clean_reply(raw.split("|", 1)[1].strip())
        return ToolAction(type="RESPOND", text=text)

    # ─── Fallback: если в тексте есть ключевые слова действий ───
    if "MULTI" in raw.upper():
        # Пытаемся вытащить сообщения после "MULTI"
        parts = re.split(r'\|', raw)
        if len(parts) > 1:
            messages = [clean_reply(p.strip()) for p in parts[1:] if p.strip()]
            if messages:
                return ToolAction(type="MULTI", messages=messages[:4])

    # Всё остальное считаем текстом ответа
    cleaned = clean_reply(raw)
    if not cleaned:
        return ToolAction(type="SILENCE")
    
    # Защита: если в тексте остались слова-маркеры инструментов
    tool_markers = ["SILENCE", "RESPOND", "MULTI", "REACT", "Использовать", "Выбираю"]
    if any(m in cleaned.upper() for m in tool_markers[:4]) or any(m in cleaned for m in tool_markers[4:]):
        return ToolAction(type="SILENCE")
    
    return ToolAction(type="RESPOND", text=cleaned)

def choose_action(context: str, user_message: str, thought: str) -> ToolAction:
    """LLM выбирает действие через tool-calling."""
    prompt = TOOL_DECISION_PROMPT.format(
        tools=TOOLS_PROMPT,
        context=context,
        user_message=user_message,
        thought=thought,
    )

    raw = query_llm_raw(
        prompt,
        n_predict=80,
        temperature=0.4,  # низкая для точности решения
        stop=["\n", "</decision>"],
    )

    if raw:
        logger.debug("[TOOL RAW] %s", raw)
        action = parse_action(raw)
        logger.info("[ACTION] %s", action)
        return action

    return ToolAction(type="RESPOND", text="...")