"""
tokudo.adapters.telegram_adapter
Telegram Bot Adapter using python-telegram-bot (v20+ async).
Handles Long-polling, Inline Keyboards, File/Voice sending, and Message Splitting.
"""

from __future__ import annotations
import os
import io
import logging
from pathlib import Path
from typing import Optional, List, Union

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from core.schema import (
    PlatformType,
    UnifiedMessage,
    UnifiedResponse,
    ActionButton,
)

logger = logging.getLogger("tokudo.adapter.telegram")


class TelegramAdapter:
    """
    Adapter bridging Telegram Bot API and Tokudo Core Engine.
    """

    def __init__(self, token: Optional[str] = None, engine_ref=None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.engine = engine_ref
        self.app: Optional[Application] = None

    def set_engine(self, engine_ref) -> None:
        self.engine = engine_ref

    async def initialize(self) -> None:
        """Initializes python-telegram-bot application with handlers."""
        if not self.token or self.token.startswith("your_"):
            logger.warning("Telegram Bot Token is missing or placeholder. Telegram Adapter will remain inactive.")
            return

        self.app = ApplicationBuilder().token(self.token).build()

        # Register message & interaction handlers
        self.app.add_handler(CommandHandler("start", self._on_message))
        self.app.add_handler(CommandHandler("help", self._on_message))
        self.app.add_handler(CommandHandler("status", self._on_message))
        self.app.add_handler(CommandHandler("remember", self._on_message))
        self.app.add_handler(CommandHandler("wiki", self._on_message))
        self.app.add_handler(CommandHandler("queue", self._on_message))
        self.app.add_handler(CommandHandler("skills", self._on_message))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._on_message))
        self.app.add_handler(MessageHandler(filters.PHOTO | filters.VOICE | filters.Document.ALL, self._on_media))
        self.app.add_handler(CallbackQueryHandler(self._on_callback_query))

        await self.app.initialize()
        logger.info("Telegram Adapter initialized successfully.")

    async def start(self) -> None:
        """Starts Telegram polling."""
        if not self.app:
            return
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram Bot long-polling started.")

    async def stop(self) -> None:
        """Gracefully stops Telegram bot."""
        if self.app and self.app.updater:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info("Telegram Bot stopped.")

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self.engine:
            return

        unified = UnifiedMessage(
            id=str(update.message.message_id),
            platform=PlatformType.TELEGRAM,
            channel_id=update.message.chat_id,
            user_id=update.effective_user.id,
            user_name=update.effective_user.username or update.effective_user.first_name,
            text=update.message.text or "",
            raw_event=update,
        )

        response = await self.engine.process_message(unified)
        if response:
            await self.send_response(response)

    async def _on_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles incoming photos, voice, or files."""
        if not update.message or not update.effective_user or not self.engine:
            return

        attachments = []
        caption = update.message.caption or ""

        # Download photo if present
        if update.message.photo:
            photo = update.message.photo[-1]
            tg_file = await photo.get_file()
            save_dir = Path("data/uploads")
            save_dir.mkdir(parents=True, exist_ok=True)
            local_path = save_dir / f"tg_photo_{photo.file_id[:8]}.jpg"
            await tg_file.download_to_drive(custom_path=local_path)
            attachments.append(str(local_path))
            if not caption:
                caption = "Phân tích hình ảnh này giúp tôi."

        unified = UnifiedMessage(
            id=str(update.message.message_id),
            platform=PlatformType.TELEGRAM,
            channel_id=update.message.chat_id,
            user_id=update.effective_user.id,
            user_name=update.effective_user.username or update.effective_user.first_name,
            text=caption,
            attachments=attachments,
            raw_event=update,
        )

        response = await self.engine.process_message(unified)
        if response:
            await self.send_response(response)

    async def _on_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles inline keyboard button presses."""
        query = update.callback_query
        if not query or not query.data or not update.effective_user or not self.engine:
            return

        await query.answer()

        unified = UnifiedMessage(
            id=str(query.message.message_id if query.message else 0),
            platform=PlatformType.TELEGRAM,
            channel_id=query.message.chat_id if query.message else 0,
            user_id=update.effective_user.id,
            user_name=update.effective_user.username or update.effective_user.first_name,
            text=query.data,
            raw_event=update,
        )

        response = await self.engine.process_message(unified)
        if response:
            await self.send_response(response)

    def _build_inline_keyboard(self, buttons: List[ActionButton]) -> Optional[InlineKeyboardMarkup]:
        if not buttons:
            return None
        keyboard = []
        row = []
        for btn in buttons:
            row.append(InlineKeyboardButton(text=btn.label, callback_data=btn.callback_data))
            if len(row) >= 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def _chunk_text(text: str, max_length: int = 4000) -> List[str]:
        """Splits long text to avoid Telegram 4096 char limit."""
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
        """Renders and sends UnifiedResponse to Telegram."""
        if not self.app:
            return

        chat_id = int(response.target_channel_id)
        reply_markup = self._build_inline_keyboard(response.buttons)
        text_chunks = self._chunk_text(response.text)

        # Send text chunks
        for i, chunk in enumerate(text_chunks):
            # Attach buttons only to the final chunk
            markup = reply_markup if i == len(text_chunks) - 1 else None
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode="Markdown",
                    reply_markup=markup,
                )
            except Exception:
                # Fallback to plain text if markdown formatting failed
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    reply_markup=markup,
                )

        # Send attachments if any
        for file_path_str in response.attachments:
            p = Path(file_path_str)
            if not p.exists():
                continue

            try:
                suffix = p.suffix.lower()
                with open(p, "rb") as f:
                    if suffix in (".png", ".jpg", ".jpeg", ".webp"):
                        await self.app.bot.send_photo(chat_id=chat_id, photo=f)
                    elif suffix in (".mp3", ".ogg", ".wav", ".m4a"):
                        await self.app.bot.send_audio(chat_id=chat_id, audio=f, filename=p.name)
                    else:
                        await self.app.bot.send_document(chat_id=chat_id, document=f, filename=p.name)
            except Exception as e:
                logger.error(f"Failed to send attachment {p} to Telegram: {e}")
