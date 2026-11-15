"""
tokudo.automation.kanban_worker
Background Kanban Task Queue (TODO -> DOING -> DONE) with SQLite persistence
and automatic completion notifications with result files back to the originating channel.
"""

from __future__ import annotations
import os
import json
import uuid
import sqlite3
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union

from core.schema import PlatformType, UnifiedResponse

logger = logging.getLogger("tokudo.automation.kanban")


class KanbanTaskStatus:
    TODO = "TODO"
    DOING = "DOING"
    DONE = "DONE"
    FAILED = "FAILED"


class KanbanWorker:
    """
    Asynchronous Background Worker maintaining a persistent Kanban board in SQLite.
    Picks tasks from TODO, transitions to DOING, executes work, and dispatches DONE report.
    """

    def __init__(self, db_path: Optional[str] = None, engine_ref=None):
        base_db = Path(os.getenv("KANBAN_DB_PATH", db_path or "data/kanban.db"))
        self.db_path = base_db if base_db.is_absolute() else Path.cwd() / base_db
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = engine_ref
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._is_running = False
        self._init_sqlite()

    def set_engine(self, engine_ref) -> None:
        self.engine = engine_ref

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kanban_tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    origin_platform TEXT NOT NULL,
                    origin_channel_id TEXT NOT NULL,
                    origin_user_id TEXT NOT NULL,
                    skill_name TEXT,
                    payload TEXT,
                    result_text TEXT,
                    result_files TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                )
                """
            )
            conn.commit()

    async def submit_task(
        self,
        title: str,
        description: str,
        origin_platform: PlatformType,
        origin_channel_id: Union[int, str],
        origin_user_id: Union[int, str],
        skill_name: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Enqueues a new background task into the Kanban queue."""
        task_id = str(uuid.uuid4())[:8]
        now_iso = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload or {})

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO kanban_tasks (
                    id, title, description, status, origin_platform,
                    origin_channel_id, origin_user_id, skill_name, payload,
                    result_text, result_files, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', '[]', ?)
                """,
                (
                    task_id,
                    title,
                    description,
                    KanbanTaskStatus.TODO,
                    origin_platform.value,
                    str(origin_channel_id),
                    str(origin_user_id),
                    skill_name or "",
                    payload_json,
                    now_iso,
                ),
            )
            conn.commit()

        await self.queue.put(task_id)
        logger.info(f"Enqueued Kanban task {task_id}: {title}")
        return task_id

    async def start(self) -> None:
        """Starts the background worker processing loop."""
        self._is_running = True
        logger.info("Background Kanban Worker started.")
        while self._is_running:
            try:
                task_id = await self.queue.get()
                await self._process_task(task_id)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Kanban worker loop error: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def stop(self) -> None:
        self._is_running = False

    async def _process_task(self, task_id: str) -> None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM kanban_tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return

            # Transition to DOING
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE kanban_tasks SET status = ?, started_at = ? WHERE id = ?",
                (KanbanTaskStatus.DOING, now_iso, task_id),
            )
            conn.commit()

        title = row["title"]
        skill_name = row["skill_name"]
        payload = json.loads(row["payload"] or "{}")
        platform = PlatformType(row["origin_platform"])
        channel_id = row["origin_channel_id"]

        logger.info(f"Processing Kanban task [{task_id}] '{title}' via skill '{skill_name}'...")
        result_text = ""
        result_files = []
        status = KanbanTaskStatus.DONE

        try:
            if skill_name and self.engine and self.engine.skill_registry:
                # Execute registered skill in background
                skill_res = await self.engine.skill_registry.execute(skill_name, payload)
                if isinstance(skill_res, dict):
                    result_text = skill_res.get("message") or skill_res.get("formatted_text") or str(skill_res)
                    if "file_path" in skill_res:
                        result_files.append(skill_res["file_path"])
                else:
                    result_text = str(skill_res)
            else:
                # Mock heavy job simulation if generic task
                await asyncio.sleep(3)
                result_text = f"Tác vụ `{title}` đã được xử lý hoàn tất trong luồng ngầm."

        except Exception as e:
            logger.error(f"Failed to execute background task {task_id}: {e}", exc_info=True)
            status = KanbanTaskStatus.FAILED
            result_text = f"❌ Gặp lỗi khi thực thi tác vụ: {str(e)}"

        # Transition to DONE / FAILED
        completed_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE kanban_tasks SET status = ?, result_text = ?, result_files = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, result_text, json.dumps(result_files), completed_iso, task_id),
            )
            conn.commit()

        # Push notification back to the origin channel
        if self.engine:
            notify_text = (
                f"📋 **BÁO CÁO HOÀN THÀNH TÁC VỤ KANBAN**\n"
                f"• **Mã việc:** `#{task_id}`\n"
                f"• **Tiêu đề:** {title}\n"
                f"• **Trạng thái:** `{status}`\n"
                f"• **Kết quả:**\n{result_text}"
            )
            resp = UnifiedResponse(
                target_platform=platform,
                target_channel_id=channel_id,
                text=notify_text,
                attachments=result_files,
            )
            await self.engine.dispatch_response(resp)

    def get_summary(self) -> str:
        """Returns visual status of Kanban board."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT status, count(*) as cnt FROM kanban_tasks GROUP BY status"
            ).fetchall()
            counts = {r["status"]: r["cnt"] for r in rows}

            recent = conn.execute(
                "SELECT id, title, status FROM kanban_tasks ORDER BY created_at DESC LIMIT 5"
            ).fetchall()

        board = (
            f"📊 **BẢNG KANBAN TÁC VỤ NỀN**\n"
            f"• 📝 **TODO:** {counts.get(KanbanTaskStatus.TODO, 0)}\n"
            f"• ⚙️ **DOING:** {counts.get(KanbanTaskStatus.DOING, 0)}\n"
            f"• ✅ **DONE:** {counts.get(KanbanTaskStatus.DONE, 0)}\n"
            f"• ❌ **FAILED:** {counts.get(KanbanTaskStatus.FAILED, 0)}\n\n"
            f"**5 tác vụ gần nhất:**\n"
        )
        if not recent:
            board += "*(Trống)*"
        else:
            for r in recent:
                icon = "⚙️" if r["status"] == "DOING" else ("✅" if r["status"] == "DONE" else "📝")
                board += f"- {icon} `#{r['id']}` {r['title']} `[{r['status']}]`\n"

        return board
