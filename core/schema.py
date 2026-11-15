"""
tokudo.core.schema
Defines unified message structures and platform-agnostic models.
"""

from __future__ import annotations
from enum import Enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class PlatformType(str, Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SYSTEM = "system"
    INTERNAL = "internal"


class ButtonStyle(str, Enum):
    PRIMARY = "primary"      # Blue / Default
    SUCCESS = "success"      # Green (Approve)
    DANGER = "danger"        # Red (Reject)
    SECONDARY = "secondary"  # Grey


class ActionButton(BaseModel):
    """Platform-agnostic representation of an interactive button."""
    id: str
    label: str
    callback_data: str
    style: ButtonStyle = ButtonStyle.PRIMARY
    url: Optional[str] = None


class UnifiedMessage(BaseModel):
    """
    Normalized incoming message schema from Telegram or Discord.
    Ensures Core Engine receives a standardized payload regardless of frontend.
    """
    id: str
    platform: PlatformType
    channel_id: Union[int, str]
    user_id: Union[int, str]
    user_name: Optional[str] = None
    text: str = ""
    attachments: List[str] = Field(default_factory=list)  # Local file paths or URLs
    reply_to_message_id: Optional[Union[int, str]] = None
    raw_event: Optional[Any] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def clean_text(self) -> str:
        return self.text.strip()


class UnifiedResponse(BaseModel):
    """
    Standardized outgoing response produced by the Core Engine.
    Adapters transform this into platform-specific elements (Markdown/Embeds/Buttons).
    """
    target_platform: PlatformType
    target_channel_id: Union[int, str]
    text: str
    attachments: List[str] = Field(default_factory=list)  # File paths to send
    buttons: List[ActionButton] = Field(default_factory=list)
    reply_to_message_id: Optional[Union[int, str]] = None
    is_approval_request: bool = False
    approval_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApprovalRequest(BaseModel):
    """
    Human-in-the-loop approval record for high-risk operations.
    """
    id: str
    skill_name: str
    command: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    origin_platform: PlatformType
    origin_channel_id: Union[int, str]
    origin_user_id: Union[int, str]
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
