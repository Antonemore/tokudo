"""
tokudo.adapters.discord_adapter
Discord Bot Adapter using discord.py (v2.3+ async).
Handles Gateway events, Slash/Text commands, UI Button Views, and File sending.
"""

from __future__ import annotations
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Union

import discord
from discord.ext import commands

from core.schema import (
    PlatformType,
    UnifiedMessage,
    UnifiedResponse,
    ActionButton,
    ButtonStyle,
)

logger = logging.getLogger("tokudo.adapter.discord")


class DynamicButtonView(discord.ui.View):
    """Interactive Discord View mapping ActionButtons to discord.ui.Button."""

    def __init__(self, buttons: List[ActionButton], engine_ref, timeout: float = 300.0):
        super().__init__(timeout=timeout)
        self.engine = engine_ref

        for btn in buttons:
            style_map = {
                ButtonStyle.SUCCESS: discord.ButtonStyle.green,
                ButtonStyle.DANGER: discord.ButtonStyle.red,
                ButtonStyle.PRIMARY: discord.ButtonStyle.blurple,
                ButtonStyle.SECONDARY: discord.ButtonStyle.grey,
            }
            dc_btn = discord.ui.Button(
                label=btn.label,
                style=style_map.get(btn.style, discord.ButtonStyle.primary),
                custom_id=btn.callback_data,
            )
            dc_btn.callback = self._create_callback(btn.callback_data)
            self.add_item(dc_btn)

    def _create_callback(self, callback_data: str):
        async def _callback(interaction: discord.Interaction):
            await interaction.response.defer()
            if self.engine:
                unified = UnifiedMessage(
                    id=str(interaction.id),
                    platform=PlatformType.DISCORD,
                    channel_id=str(interaction.channel_id),
                    user_id=str(interaction.user.id),
                    user_name=interaction.user.name,
                    text=callback_data,
                    raw_event=interaction,
                )
                resp = await self.engine.process_message(unified)
                if resp:
                    await interaction.followup.send(resp.text)

        return _callback


class DiscordAdapter:
    """
    Adapter bridging Discord Gateway and Tokudo Core Engine.
    """

    def __init__(self, token: Optional[str] = None, engine_ref=None):
        self.token = token or os.getenv("DISCORD_BOT_TOKEN")
        self.engine = engine_ref
        intents = discord.Intents.default()
        intents.message_content = True

        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
        self._setup_events()

    def set_engine(self, engine_ref) -> None:
        self.engine = engine_ref

    def _setup_events(self) -> None:
        @self.bot.event
        async def on_ready():
            logger.info(f"Discord Bot connected as {self.bot.user} (ID: {self.bot.user.id})")

        @self.bot.event
        async def on_message(message: discord.Message):
            # Ignore self messages
            if message.author == self.bot.user or not self.engine:
                return

            attachments = []
            if message.attachments:
                save_dir = Path("data/uploads")
                save_dir.mkdir(parents=True, exist_ok=True)
                for att in message.attachments:
                    local_path = save_dir / f"dc_{att.id}_{att.filename}"
                    await att.save(local_path)
                    attachments.append(str(local_path))

            unified = UnifiedMessage(
                id=str(message.id),
                platform=PlatformType.DISCORD,
                channel_id=str(message.channel.id),
                user_id=str(message.author.id),
                user_name=message.author.name,
                text=message.content,
                attachments=attachments,
                raw_event=message,
            )

            response = await self.engine.process_message(unified)
            if response:
                await self.send_response(response)

    async def start(self) -> None:
        """Starts Discord client."""
        if not self.token or self.token.startswith("your_"):
            logger.warning("Discord Bot Token is missing or placeholder. Discord Adapter will remain inactive.")
            return

        logger.info("Connecting Discord Bot to Gateway...")
        await self.bot.start(self.token)

    async def stop(self) -> None:
        if not self.bot.is_closed():
            await self.bot.close()
            logger.info("Discord Bot closed.")

    @staticmethod
    def _chunk_text(text: str, max_length: int = 1950) -> List[str]:
        """Splits text to adhere to Discord's 2000 character limit."""
        if len(text) <= max_length:
            return [text]
        chunks = []
        while text:
            if len(text) <= max_length:
                chunks.append(text)
                break
            split_idx = text.rfind("\n", 0, max_length)
            if split_idx == -1:
                split_idx = max_length
            chunks.append(text[:split_idx])
            text = text[split_idx:].lstrip()
        return chunks

    async def send_response(self, response: UnifiedResponse) -> None:
        """Renders and sends UnifiedResponse to Discord channel."""
        channel_id = int(response.target_channel_id)
        channel = self.bot.get_channel(channel_id)

        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                logger.error(f"Cannot fetch Discord channel {channel_id}: {e}")
                return

        view = DynamicButtonView(response.buttons, self.engine) if response.buttons else None
        chunks = self._chunk_text(response.text)

        # Prepare attachments
        files = []
        for file_p in response.attachments:
            p = Path(file_p)
            if p.exists():
                files.append(discord.File(str(p), filename=p.name))

        # Send text chunks
        for i, chunk in enumerate(chunks):
            current_view = view if i == len(chunks) - 1 else None
            current_files = files if i == len(chunks) - 1 else []
            try:
                await channel.send(chunk, view=current_view, files=current_files)
            except Exception as e:
                logger.error(f"Failed to send Discord message chunk: {e}")
