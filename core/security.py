"""
tokudo.core.security
Strict whitelist verification and Human-in-the-Loop (HITL) approval manager.
"""

from __future__ import annotations
import os
import uuid
import asyncio
import logging
from typing import Dict, Set, Optional, Tuple, Union
from core.schema import (
    PlatformType,
    UnifiedResponse,
    ActionButton,
    ButtonStyle,
    ApprovalRequest,
    ApprovalStatus,
)

logger = logging.getLogger("tokudo.security")


class SecurityManager:
    """
    Handles access control (whitelisting) and asynchronous approvals
    for sensitive system commands and OS manipulations.
    """

    def __init__(self):
        self.telegram_whitelist: Set[str] = set()
        self.discord_whitelist: Set[str] = set()
        self.require_approval: bool = True
        self.approval_timeout: int = 300  # 5 minutes default
        self._pending_approvals: Dict[str, asyncio.Future[bool]] = {}
        self._approval_records: Dict[str, ApprovalRequest] = {}
        self.reload_config()

    def reload_config(self) -> None:
        """Reads whitelist and security flags from environment."""
        tg_raw = os.getenv("TELEGRAM_ALLOWED_USER_ID", "")
        self.telegram_whitelist = {
            item.strip() for item in tg_raw.replace(";", ",").split(",") if item.strip()
        }

        dc_raw = os.getenv("DISCORD_ALLOWED_USER_ID", "")
        self.discord_whitelist = {
            item.strip() for item in dc_raw.replace(";", ",").split(",") if item.strip()
        }

        self.require_approval = os.getenv("SECURITY_REQUIRE_APPROVAL", "true").lower() in ("true", "1", "yes")
        try:
            self.approval_timeout = int(os.getenv("APPROVAL_TIMEOUT_SECONDS", "300"))
        except ValueError:
            self.approval_timeout = 300

        logger.info(
            f"Security configured: Telegram IDs={len(self.telegram_whitelist)}, "
            f"Discord IDs={len(self.discord_whitelist)}, HITL={self.require_approval}"
        )

    def is_authorized(self, platform: PlatformType, user_id: Union[int, str]) -> bool:
        """
        Validates if user_id is in the strict whitelist.
        Returns False for unauthorized users so request can be silently dropped.
        """
        uid_str = str(user_id).strip()
        if platform == PlatformType.TELEGRAM:
            allowed = uid_str in self.telegram_whitelist
        elif platform == PlatformType.DISCORD:
            allowed = uid_str in self.discord_whitelist
        elif platform in (PlatformType.SYSTEM, PlatformType.INTERNAL):
            return True
        else:
            allowed = False

        if not allowed:
            logger.warning(f"Unauthorized access attempt blocked: platform={platform.value}, user_id={uid_str}")
        return allowed

    def create_approval_request(
        self,
        skill_name: str,
        command_desc: str,
        arguments: dict,
        origin_platform: PlatformType,
        origin_channel_id: Union[int, str],
        origin_user_id: Union[int, str],
    ) -> Tuple[ApprovalRequest, UnifiedResponse]:
        """
        Creates an asynchronous approval barrier. Returns request record and
        an interactive confirmation message with Approve/Reject buttons.
        """
        approval_id = str(uuid.uuid4())[:8]
        req = ApprovalRequest(
            id=approval_id,
            skill_name=skill_name,
            command=command_desc,
            arguments=arguments,
            origin_platform=origin_platform,
            origin_channel_id=origin_channel_id,
            origin_user_id=origin_user_id,
        )

        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending_approvals[approval_id] = future
        self._approval_records[approval_id] = req

        # Format prompt with formatted buttons
        prompt_text = (
            f"⚠️ **XÁC NHẬN BẢO MẬT (Human-in-the-Loop)**\n"
            f"Yêu cầu thực thi lệnh nhạy cảm trên máy tính:\n"
            f"• **Hành động / Skill:** `{skill_name}`\n"
            f"• **Chi tiết lệnh:** `{command_desc}`\n"
            f"• **Mã phê duyệt:** `{approval_id}`\n\n"
            f"Vui lòng nhấn nút bên dưới để cấp quyền thực thi (hết hạn sau {self.approval_timeout}s):"
        )

        buttons = [
            ActionButton(
                id=f"approve_{approval_id}",
                label="✅ Chấp thuận",
                callback_data=f"hitl:approve:{approval_id}",
                style=ButtonStyle.SUCCESS,
            ),
            ActionButton(
                id=f"reject_{approval_id}",
                label="❌ Từ chối",
                callback_data=f"hitl:reject:{approval_id}",
                style=ButtonStyle.DANGER,
            ),
        ]

        response = UnifiedResponse(
            target_platform=origin_platform,
            target_channel_id=origin_channel_id,
            text=prompt_text,
            buttons=buttons,
            is_approval_request=True,
            approval_id=approval_id,
        )

        return req, response

    async def wait_for_approval(self, approval_id: str) -> bool:
        """
        Awaits user decision asynchronously up to approval_timeout.
        """
        future = self._pending_approvals.get(approval_id)
        if not future:
            return False

        try:
            approved = await asyncio.wait_for(future, timeout=self.approval_timeout)
            record = self._approval_records.get(approval_id)
            if record:
                record.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            return approved
        except asyncio.TimeoutError:
            logger.warning(f"Approval request {approval_id} timed out.")
            record = self._approval_records.get(approval_id)
            if record:
                record.status = ApprovalStatus.EXPIRED
            return False
        finally:
            self._pending_approvals.pop(approval_id, None)

    def resolve_approval(self, approval_id: str, approved: bool) -> bool:
        """
        Invoked when user clicks the inline button on Telegram/Discord.
        Resolves the awaiting future.
        """
        future = self._pending_approvals.get(approval_id)
        if future and not future.done():
            future.set_result(approved)
            record = self._approval_records.get(approval_id)
            if record:
                record.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            logger.info(f"Approval {approval_id} resolved: approved={approved}")
            return True
        return False
