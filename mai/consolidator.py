"""Sleep-time консолидация дневника."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

from mai.config import DIARY_FILE
from mai.diary import rewrite_diary
from mai.llm import query_llm_raw
from mai.prompts import SLEEP_CONSOLIDATOR_PROMPT

logger = logging.getLogger(__name__)


async def run_sleep_consolidation() -> None:
    """Консолидирует дневник — как сон для человеческого мозга."""
    if not os.path.exists(DIARY_FILE):
        return

    with open(DIARY_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    entries = content.split("---\n")
    if len(entries) < 20:
        logger.info("[SLEEP] Недостаточно записей для консолидации")
        return

    # Берём старые записи (пропуская последние 20 свежих)
    old_entries = "\n---\n".join(entries[:-20])

    prompt = SLEEP_CONSOLIDATOR_PROMPT.format(entries=old_entries)
    result = query_llm_raw(
        prompt,
        n_predict=2000,
        temperature=0.3,
        timeout=300,
    )

    if not result:
        logger.warning("[SLEEP] Пустой ответ LLM")
        return

    # Сохраняем свежие + консолидированные старые
    fresh = "\n---\n".join(entries[-20:])
    new_content = result + "\n\n---\n\n" + fresh
    rewrite_diary(new_content)
    logger.info("[SLEEP] ✅ Консолидация завершена")


async def consolidator_loop() -> None:
    """Фоновый цикл: запускает консолидацию раз в сутки в 4 утра."""
    logger.info("[SLEEP] Консолидатор запущен")
    last_run_date = None

    while True:
        try:
            now = datetime.now()
            if now.hour == 4 and last_run_date != now.date():
                await run_sleep_consolidation()
                last_run_date = now.date()
        except Exception as e:
            logger.exception("[SLEEP ERROR] %s", e)
        await asyncio.sleep(300)