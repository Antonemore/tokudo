"""
tokudo.automation.scheduler
Cron Job & Reminder Scheduler utilizing APScheduler for periodic alerts and background triggers.
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from core.schema import PlatformType, UnifiedResponse

logger = logging.getLogger("tokudo.automation.scheduler")


class TaskScheduler:
    """
    Manages reminders and scheduled recurring tasks.
    Triggers automated notifications dispatched through Tokudo Engine to Telegram/Discord.
    """

    def __init__(self, engine_ref=None):
        self.engine = engine_ref
        self.scheduler = AsyncIOScheduler()

    def set_engine(self, engine_ref) -> None:
        self.engine = engine_ref

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("TaskScheduler initialized and running.")

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("TaskScheduler stopped.")

    async def _send_notification(
        self,
        text: str,
        platform: PlatformType,
        channel_id: Union[int, str],
        attachment_path: Optional[str] = None,
    ) -> None:
        """Internal callback invoked when a timer or cron trigger fires."""
        if not self.engine:
            logger.warning("No engine reference to send scheduled notification.")
            return

        resp = UnifiedResponse(
            target_platform=platform,
            target_channel_id=channel_id,
            text=f"⏰ **NHẮC VIỆC & LỊCH TRÌNH ĐỊNH KỲ**\n{text}",
            attachments=[attachment_path] if attachment_path else [],
        )
        await self.engine.dispatch_response(resp)

    def add_reminder(
        self,
        run_date: datetime,
        message: str,
        platform: PlatformType,
        channel_id: Union[int, str],
    ) -> str:
        """Schedules a one-off reminder at a specific datetime."""
        job_id = f"reminder_{int(run_date.timestamp())}"
        self.scheduler.add_job(
            self._send_notification,
            trigger=DateTrigger(run_date=run_date),
            args=[message, platform, channel_id],
            id=job_id,
            replace_existing=True,
        )
        logger.info(f"Scheduled reminder {job_id} at {run_date}")
        return job_id

    def add_interval_job(
        self,
        job_id: str,
        minutes: int,
        message: str,
        platform: PlatformType,
        channel_id: Union[int, str],
    ) -> str:
        """Schedules a recurring notification every N minutes."""
        self.scheduler.add_job(
            self._send_notification,
            trigger=IntervalTrigger(minutes=minutes),
            args=[message, platform, channel_id],
            id=job_id,
            replace_existing=True,
        )
        logger.info(f"Scheduled interval job {job_id} every {minutes}m")
        return job_id

    def get_active_jobs_summary(self) -> str:
        jobs = self.scheduler.get_jobs()
        if not jobs:
            return "Không có lịch hẹn hay cron job nào đang chạy."

        lines = ["📅 **DANH SÁCH LỊCH TRÌNH ĐANG KÍCH HOẠT:**"]
        for j in jobs:
            next_run = j.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if j.next_run_time else "N/A"
            lines.append(f"• `{j.id}` — Chạy kế tiếp lúc: `{next_run}`")
        return "\n".join(lines)
