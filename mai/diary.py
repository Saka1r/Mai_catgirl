"""Markdown-дневник с vector-based RAG поиском."""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Optional

import numpy as np

from mai.config import DIARY_FILE, DIARY_EMBEDDINGS, CREATOR_USER_ID

logger = logging.getLogger(__name__)

# Lazy-loaded embedding model
_embedding_model = None


def _get_embedding_model():
    """Lazy-load sentence-transformers."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            logger.info("[DIARY] Embedding model loaded")
        except Exception as e:
            logger.error("[DIARY] Failed to load embedding model: %s", e)
            return None
    return _embedding_model


def write_diary_entry(entry: dict) -> None:
    """Записывает новую запись в markdown дневник."""
    os.makedirs(os.path.dirname(DIARY_FILE), exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry_id = f"{timestamp}_{os.urandom(4).hex()}"

    facts_md = "\n".join(f"- {f}" for f in entry.get("facts", [])) or "- нет"
    tags = entry.get("tags", [])
    if not tags and entry.get("username"):
        tags = [entry["username"].lower()]

    # ─── НОВОЕ: чат и ключевые сообщения ───
    chat_id_str = entry.get("chat_id", "")
    key_messages = entry.get("key_messages", "")

    md_entry = f"""---
## {timestamp}
**ID:** {entry_id}
**Собеседник:** {entry.get('username', 'неизвестно')}
**Чат:** {chat_id_str}
**Эмоция:** {entry.get('emotion', 'нейтральная')}
**Событие:** {entry.get('summary', '')}

**Факты:**
{facts_md}

**Ключевые реплики:** {key_messages}

**Мысли:** {entry.get('thought', '')}

**Теги:** {', '.join(tags)}
---

"""
    with open(DIARY_FILE, "a", encoding="utf-8") as f:
        f.write(md_entry)

    build_embeddings()


def _parse_entries() -> list[tuple[str, str]]:
    """Парсит дневник в список (id, text)."""
    if not os.path.exists(DIARY_FILE):
        return []
    with open(DIARY_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    raw_entries = content.split("---\n")
    entries = []
    for e in raw_entries:
        e = e.strip()
        if not e:
            continue
        id_match = re.search(r"\*\*ID:\*\*\s*(\S+)", e)
        entry_id = id_match.group(1) if id_match else ""
        entries.append((entry_id, e))
    return entries


def build_embeddings() -> None:
    """Строит векторные представления для всех записей."""
    model = _get_embedding_model()
    if model is None:
        return

    entries = _parse_entries()
    if not entries:
        return

    texts = []
    for _, text in entries:
        # Берём суть для embedding
        summary_match = re.search(r"\*\*Событие:\*\*\s*(.+)", text)
        facts_match = re.search(r"\*\*Факты:\*\*\s*\n(.*?)(?=\n\n|\n\*\*)", text, re.DOTALL)
        tags_match = re.search(r"\*\*Теги:\*\*\s*(.+)", text)

        parts = []
        if summary_match:
            parts.append(summary_match.group(1))
        if facts_match:
            parts.append(facts_match.group(1).replace("- ", ""))
        if tags_match:
            parts.append(tags_match.group(1))
        texts.append(" ".join(parts))

    if not texts:
        return

    embeddings = model.encode(texts)
    np.save(DIARY_EMBEDDINGS, embeddings)
    logger.debug("[DIARY] Built %d embeddings", len(embeddings))


def search_diary(query: str, top_k: int = 3) -> str:
    """Ищет релевантные записи через vector similarity."""
    if not os.path.exists(DIARY_EMBEDDINGS):
        build_embeddings()
    if not os.path.exists(DIARY_EMBEDDINGS):
        return ""

    try:
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        logger.error("scikit-learn not installed")
        return ""

    model = _get_embedding_model()
    if model is None:
        return ""

    entries = _parse_entries()
    if not entries:
        return ""

    embeddings = np.load(DIARY_EMBEDDINGS)
    if len(embeddings) != len(entries):
        build_embeddings()
        embeddings = np.load(DIARY_EMBEDDINGS)
        if len(embeddings) != len(entries):
            return ""

    query_emb = model.encode([query])
    sims = cosine_similarity(query_emb, embeddings)[0]
    top_idx = np.argsort(sims)[::-1][:top_k]

    results = []
    for idx in top_idx:
        if sims[idx] > 0.35:
            results.append(entries[idx][1])

    return "\n\n---\n\n".join(results[:3])


def rewrite_diary(new_content: str) -> None:
    """Полностью перезаписывает дневник (для консолидации)."""
    with open(DIARY_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)
    build_embeddings()