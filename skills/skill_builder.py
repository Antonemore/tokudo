"""
tokudo.skills.skill_builder
Meta-Skill: Enables Tokudo to autonomously write, validate (AST check),
and hot-reload new Python skills into runtime memory without restarting the bot.
"""

from __future__ import annotations
import ast
import logging
from pathlib import Path
from typing import Any, Dict

from skills.base import BaseSkill, SkillRegistry

logger = logging.getLogger("tokudo.skills.builder")


class SkillBuilderSkill(BaseSkill):
    name = "skill_builder"
    description = (
        "Meta-Skill tự mở rộng: Cho phép Tokudo tự lập trình thêm kỹ năng (Skill) Python mới, "
        "tự động lưu vào thư mục skills/, kiểm tra cú pháp và nạp nóng (Hot-reload) vào RAM ngay lập tức."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_name": {
                "type": "string",
                "description": "Tên file Python của skill (vd: currency_converter.py, weather_tool.py)",
            },
            "code_content": {
                "type": "string",
                "description": "Toàn bộ mã nguồn Python hoàn chỉnh của skill (phải kế thừa từ BaseSkill)",
            },
            "description": {
                "type": "string",
                "description": "Mô tả ngắn gọn về tính năng của skill mới này",
            },
        },
        "required": ["file_name", "code_content"],
    }
    # Creating executable code on the machine is sensitive, requires approval
    requires_approval = True

    def __init__(self, registry: SkillRegistry = None):
        self.registry = registry

    def set_registry(self, registry: SkillRegistry) -> None:
        self.registry = registry

    async def execute(self, file_name: str, code_content: str, description: str = "", **kwargs) -> Dict[str, Any]:
        if not file_name.endswith(".py"):
            file_name += ".py"

        # Prevent overwriting core files
        protected_files = {"base.py", "__init__.py", "skill_builder.py"}
        if file_name.lower() in protected_files:
            return {"error": f"Không được phép ghi đè lên các tệp hạt nhân: {file_name}"}

        # Step 1: Validate Python Syntax using AST
        try:
            parsed_ast = ast.parse(code_content, filename=file_name)
        except SyntaxError as e:
            return {
                "error": f"Lỗi cú pháp Python (SyntaxError) tại dòng {e.lineno}: {e.msg}",
                "status": "syntax_error",
            }

        # Step 2: Validate that at least one class is defined
        class_defs = [node.name for node in ast.walk(parsed_ast) if isinstance(node, ast.ClassDef)]
        if not class_defs:
            return {
                "error": "Mã nguồn không chứa bất kỳ Class nào. Skill bắt buộc phải kế thừa BaseSkill.",
                "status": "missing_class",
            }

        # Step 3: Write file to skills/ directory
        skills_dir = Path(__file__).parent
        file_path = skills_dir / file_name

        try:
            file_path.write_text(code_content, encoding="utf-8")
            logger.info(f"Wrote new skill code to {file_path}")
        except Exception as e:
            return {"error": f"Lỗi ghi tệp mã nguồn: {str(e)}"}

        # Step 4: Perform Hot-Reload into live runtime memory
        if self.registry:
            try:
                updated_skills = self.registry.hot_reload(file_name)
                return {
                    "status": "success",
                    "file_name": file_name,
                    "defined_classes": class_defs,
                    "active_skills_count": len(updated_skills),
                    "message": (
                        f"✨ **TỰ TIẾN HÓA THÀNH CÔNG!**\n"
                        f"• Đã tạo và biên dịch: `skills/{file_name}`\n"
                        f"• Lớp thực thi: `{', '.join(class_defs)}`\n"
                        f"• Đã nạp nóng (Hot-Reload) trực tiếp vào RAM không cần khởi động lại bot.\n"
                        f"• Tổng số kỹ năng sẵn sàng: `{len(updated_skills)}`"
                    ),
                }
            except Exception as e:
                logger.error(f"Hot-reload failed after file write: {e}", exc_info=True)
                return {
                    "status": "reload_warning",
                    "file_name": file_name,
                    "warning": f"File đã được ghi nhưng nạp nóng gặp sự cố: {str(e)}",
                }

        return {
            "status": "saved_without_registry",
            "message": f"Đã lưu file {file_name}. Cần khởi động lại bot để nạp do thiếu tham chiếu registry.",
        }
