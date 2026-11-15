"""
tokudo.skills.multimodal
Multimodal processing: Image inspection, YouTube video summary, and Voice Synthesis (TTS).
"""

from __future__ import annotations
import os
import re
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from PIL import Image
from youtube_transcript_api import YouTubeTranscriptApi
import edge_tts

from skills.base import BaseSkill

logger = logging.getLogger("tokudo.skills.multimodal")


class ImageAnalysisSkill(BaseSkill):
    name = "analyze_image"
    description = "Kiểm tra thông tin chi tiết của file hình ảnh (kích thước, định dạng, bảng màu)."
    parameters = {
        "type": "object",
        "properties": {
            "image_path": {"type": "string", "description": "Đường dẫn tệp hình ảnh cục bộ"},
        },
        "required": ["image_path"],
    }
    requires_approval = False

    async def execute(self, image_path: str, **kwargs) -> Dict[str, Any]:
        path = Path(image_path)
        if not path.exists():
            return {"error": f"Không tìm thấy hình ảnh tại: {image_path}"}

        def _inspect():
            with Image.open(path) as img:
                return {
                    "format": img.format,
                    "mode": img.mode,
                    "width": img.width,
                    "height": img.height,
                    "size_kb": round(path.stat().st_size / 1024, 2),
                }

        info = await asyncio.to_thread(_inspect)
        report = (
            f"🖼 **PHÂN TÍCH HÌNH ẢNH:** `{path.name}`\n"
            f"• **Kích thước:** `{info['width']} x {info['height']} px`\n"
            f"• **Định dạng:** `{info['format']}` ({info['mode']})\n"
            f"• **Dung lượng:** `{info['size_kb']} KB`"
        )
        return {"info": info, "formatted_report": report}


class YouTubeSummarySkill(BaseSkill):
    name = "youtube_summary"
    description = "Trích xuất phụ đề và nội dung video YouTube từ đường dẫn để tóm tắt các ý chính."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Đường dẫn video YouTube (youtube.com hoặc youtu.be)"},
        },
        "required": ["url"],
    }
    requires_approval = False

    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"youtu\.be\/([0-9A-Za-z_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def execute(self, url: str, **kwargs) -> Dict[str, Any]:
        video_id = self._extract_video_id(url)
        if not video_id:
            return {"error": f"Không thể nhận diện Video ID từ đường dẫn: {url}"}

        def _fetch_subtitles():
            try:
                # Try fetching Vietnamese, then English, then any available transcript
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                transcript = None
                try:
                    transcript = transcript_list.find_transcript(['vi', 'en'])
                except Exception:
                    transcript = transcript_list.find_generated_transcript(['vi', 'en'])
                
                entries = transcript.fetch()
                full_text = " ".join([item['text'] for item in entries])
                return full_text
            except Exception as e:
                return f"Lỗi trích xuất phụ đề: {str(e)}"

        raw_transcript = await asyncio.to_thread(_fetch_subtitles)
        if raw_transcript.startswith("Lỗi"):
            return {"error": raw_transcript}

        # Truncate if too huge
        sample_transcript = raw_transcript[:5000]
        word_count = len(raw_transcript.split())

        return {
            "video_id": video_id,
            "word_count": word_count,
            "sample_transcript": sample_transcript,
            "message": f"📺 Đã trích xuất phụ đề ({word_count} từ). Đang tiến hành tóm tắt nội dung chính...",
        }


class TextToSpeechSkill(BaseSkill):
    name = "text_to_speech"
    description = "Chuyển đổi văn bản thành giọng nói tiếng Việt tự nhiên và lưu thành file audio .mp3 để gửi."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Đoạn văn bản cần đọc"},
            "voice": {
                "type": "string",
                "enum": ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural", "en-US-ChristopherNeural"],
                "default": "vi-VN-NamMinhNeural",
                "description": "Giọng đọc (Nam/Nữ tiếng Việt hoặc tiếng Anh)",
            },
        },
        "required": ["text"],
    }
    requires_approval = False

    async def execute(self, text: str, voice: str = "vi-VN-NamMinhNeural", **kwargs) -> Dict[str, Any]:
        output_dir = Path("data/tts")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = output_dir / f"voice_{timestamp}.mp3"

        clean_text = text.strip()[:1000]  # Cap length for safety
        communicate = edge_tts.Communicate(clean_text, voice)
        await communicate.save(str(file_path))

        logger.info(f"Synthesized TTS audio to {file_path}")
        return {
            "status": "success",
            "file_path": str(file_path.resolve()),
            "voice": voice,
            "message": f"🎙 Đã tạo file giọng nói thành công.",
        }
