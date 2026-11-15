"""
tokudo.brain.memory_manager
Manages persistent long-term memory in Markdown and executes Auto-Reflection.
"""

from __future__ import annotations
import os
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict

logger = logging.getLogger("tokudo.brain.memory")


class MemoryManager:
    """
    Manages long-term markdown memories and continuous self-reflection.
    Memory files:
      - user_profile.md
      - preferences.md
      - lessons_learned.md
    """

    def __init__(self, memory_dir: Optional[str] = None):
        base_dir = Path(os.getenv("MEMORY_DIR", memory_dir or "brain/memory"))
        self.memory_dir = base_dir if base_dir.is_absolute() else Path.cwd() / base_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_default_files()

    def _ensure_default_files(self) -> None:
        """Creates empty starter files if they don't exist."""
        defaults = {
            "user_profile.md": "# User Profile\n\n- Role: User\n",
            "preferences.md": "# User Preferences\n\n- Preferred style: Concise, technical, and actionable\n",
            "lessons_learned.md": "# Lessons Learned\n\n- Initialized Tokudo Second Brain\n",
        }
        for name, initial_content in defaults.items():
            path = self.memory_dir / name
            if not path.exists():
                path.write_text(initial_content, encoding="utf-8")

    def get_consolidated_context(self) -> str:
        """
        Reads all memory files and synthesizes them into a system context block
        for the LLM reasoning core.
        """
        sections = []
        for file_path in sorted(self.memory_dir.glob("*.md")):
            try:
                content = file_path.read_text(encoding="utf-8").strip()
                if content:
                    sections.append(f"### [Memory Source: {file_path.name}]\n{content}")
            except Exception as e:
                logger.error(f"Error reading memory file {file_path}: {e}")

        if not sections:
            return "No persistent memory found."
        return "\n\n".join(sections)

    def append_memory(self, filename: str, content: str) -> bool:
        """Safely appends a new bullet point or entry to a memory file."""
        if not filename.endswith(".md"):
            filename += ".md"
        file_path = self.memory_dir / filename
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n- [{now_str}] {content.strip()}"

        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(entry)
            logger.info(f"Appended memory to {filename}: {content[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to append memory to {filename}: {e}")
            return False

    def remember(self, note: str, category: str = "preferences") -> str:
        """
        Explicit remember command handler (/remember).
        Categories: 'preferences', 'profile', 'lessons'
        """
        target_map = {
            "preferences": "preferences.md",
            "pref": "preferences.md",
            "profile": "user_profile.md",
            "user": "user_profile.md",
            "lessons": "lessons_learned.md",
            "lesson": "lessons_learned.md",
        }
        target_file = target_map.get(category.lower(), "preferences.md")
        success = self.append_memory(target_file, note)
        if success:
            return f"🧠 Đã ghi nhớ vào bộ não dài hạn ({target_file}):\n`{note}`"
        return "❌ Gặp lỗi khi lưu bộ nhớ."

    async def auto_reflect(
        self,
        user_text: str,
        bot_response: str,
        llm_engine=None,
    ) -> None:
        """
        Auto-Reflection Engine:
        Evaluates dialogue turn to extract user preferences, operational instructions,
        or project conventions. Runs asynchronously in the background.
        """
        # Quick heuristic filter: don't analyze trivial short greetings
        if len(user_text.strip()) < 15 or user_text.strip().startswith("/"):
            return

        reflection_prompt = (
            "You are the Memory Reflection subsystem of Tokudo Personal AI.\n"
            "Analyze the following conversation turn between User and Tokudo.\n"
            "Identify if the user explicitly stated a persistent preference, custom rule, "
            "habit, constraint, or a lesson learned that Tokudo must remember permanently.\n\n"
            f"User: {user_text}\n"
            f"Tokudo: {bot_response}\n\n"
            "If there is a valuable insight to save, output in this exact format:\n"
            "CATEGORY: <preferences | lessons_learned | user_profile>\n"
            "INSIGHT: <Concise, direct 1-2 sentence description in Vietnamese or English>\n"
            "If there is nothing new or important to remember, reply with: NONE"
        )

        try:
            if llm_engine:
                result = await llm_engine.generate_raw(reflection_prompt, temperature=0.2)
                if result and "INSIGHT:" in result and "NONE" not in result:
                    cat_match = re.search(r"CATEGORY:\s*(\w+)", result, re.IGNORECASE)
                    insight_match = re.search(r"INSIGHT:\s*(.+)", result, re.DOTALL | re.IGNORECASE)

                    if insight_match:
                        insight_text = insight_match.group(1).strip()
                        raw_cat = cat_match.group(1).strip().lower() if cat_match else "preferences"
                        target_file = "lessons_learned.md" if "lesson" in raw_cat else "preferences.md"
                        self.append_memory(target_file, f"(Auto-Reflected) {insight_text}")
        except Exception as e:
            logger.warning(f"Auto-reflection skipped or encountered error: {e}")
