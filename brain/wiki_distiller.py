"""
tokudo.brain.wiki_distiller
Knowledge Distillation Engine & SQLite FTS5 Full-Text Search.
"""

from __future__ import annotations
import os
import re
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

logger = logging.getLogger("tokudo.brain.wiki")


class WikiDistiller:
    """
    Distills raw knowledge (notes, articles, code snippets, documentation)
    into structured Markdown files and indexes them via SQLite FTS5 for fast citation.
    """

    def __init__(self, wiki_dir: Optional[str] = None, db_path: Optional[str] = None):
        base_wiki = Path(os.getenv("WIKI_DIR", wiki_dir or "brain/wiki"))
        self.wiki_dir = base_wiki if base_wiki.is_absolute() else Path.cwd() / base_wiki
        self.wiki_dir.mkdir(parents=True, exist_ok=True)

        db_file = Path(os.getenv("INDEX_DB_PATH", db_path or "brain/index.db"))
        self.db_path = db_file if db_file.is_absolute() else Path.cwd() / db_file
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_sqlite()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self) -> None:
        """Initializes tables and SQLite FTS5 virtual table."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wiki_documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    path TEXT NOT NULL,
                    source_url TEXT,
                    tags TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            # Create FTS5 virtual table for lightning-fast search
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
                    id UNINDEXED,
                    title,
                    content,
                    tags,
                    tokenize='unicode61 remove_diacritics 2'
                )
                """
            )
            conn.commit()

    @staticmethod
    def _slugify(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        return re.sub(r"[-\s]+", "-", text).strip("-")[:64] or "document"

    async def distill(
        self,
        title: str,
        raw_content: str,
        source_url: Optional[str] = None,
        tags: Optional[List[str]] = None,
        llm_engine=None,
    ) -> Dict[str, Any]:
        """
        Distills raw material into structured Markdown and updates FTS5 index.
        """
        slug = self._slugify(title)
        tags_list = tags or ["general"]
        tags_str = ", ".join(tags_list)
        now_iso = datetime.now(timezone.utc).isoformat()

        distilled_body = raw_content
        if llm_engine:
            prompt = (
                f"You are the Knowledge Distillation Architect for Tokudo.\n"
                f"Distill the following raw knowledge into a clean, highly structured Markdown document.\n"
                f"Include:\n"
                f"1. Executive Summary (2-3 sentences)\n"
                f"2. Core Concepts & Principles\n"
                f"3. Practical Applications / Code Snippets (if applicable)\n"
                f"4. Key Takeaways\n\n"
                f"Raw input:\n{raw_content[:4000]}"
            )
            try:
                ai_summary = await llm_engine.generate_raw(prompt, temperature=0.3)
                if ai_summary and len(ai_summary) > 50:
                    distilled_body = ai_summary
            except Exception as e:
                logger.warning(f"AI distillation fallback to raw text: {e}")

        # Assemble Markdown with metadata header
        md_content = (
            f"# {title}\n\n"
            f"> **Tags:** `{tags_str}` | **Created:** `{now_iso[:10]}`"
            + (f" | **Source:** [{source_url}]({source_url})" if source_url else "")
            + f"\n\n---\n\n{distilled_body}\n"
        )

        file_path = self.wiki_dir / f"{slug}.md"
        file_path.write_text(md_content, encoding="utf-8")

        # Update SQLite and FTS5
        doc_id = slug
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO wiki_documents (id, title, slug, path, source_url, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title=excluded.title,
                    path=excluded.path,
                    source_url=excluded.source_url,
                    tags=excluded.tags,
                    updated_at=excluded.updated_at
                """,
                (doc_id, title, slug, str(file_path), source_url, tags_str, now_iso, now_iso),
            )

            # Refresh FTS5 index
            conn.execute("DELETE FROM wiki_fts WHERE id = ?", (doc_id,))
            conn.execute(
                "INSERT INTO wiki_fts (id, title, content, tags) VALUES (?, ?, ?, ?)",
                (doc_id, title, distilled_body, tags_str),
            )
            conn.commit()

        logger.info(f"Distilled and indexed wiki page: {slug}.md")
        return {
            "id": doc_id,
            "title": title,
            "path": str(file_path),
            "slug": slug,
            "tags": tags_list,
        }

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Performs full-text search using SQLite FTS5 with BM25 ranking and snippet extraction.
        """
        clean_q = re.sub(r"[^\w\s]", " ", query).strip()
        if not clean_q:
            return []

        # Prepare tokens for FTS MATCH
        tokens = [f'"{token}"*' for token in clean_q.split() if len(token) > 1]
        if not tokens:
            return []
        match_query = " OR ".join(tokens)

        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT f.id, f.title, f.tags,
                           snippet(wiki_fts, 2, '<b>', '</b>', '...', 24) AS snippet,
                           d.path, d.source_url, bm25(wiki_fts) AS rank
                    FROM wiki_fts f
                    JOIN wiki_documents d ON f.id = d.id
                    WHERE wiki_fts MATCH ?
                    ORDER BY rank ASC
                    LIMIT ?
                    """,
                    (match_query, limit),
                )
                for row in cursor.fetchall():
                    results.append(
                        {
                            "id": row["id"],
                            "title": row["title"],
                            "tags": row["tags"],
                            "snippet": row["snippet"],
                            "file_path": row["path"],
                            "source_url": row["source_url"],
                        }
                    )
        except Exception as e:
            logger.error(f"Error querying SQLite FTS5: {e}")

        return results
