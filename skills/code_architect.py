"""
tokudo.skills.code_architect
Codebase structure inspection, multi-language coding assistance (Python, Rust, SketchUp Ruby, C++),
and automated static security vulnerability auditing.
"""

from __future__ import annotations
import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from skills.base import BaseSkill

logger = logging.getLogger("tokudo.skills.code")


class CodebaseExplorerSkill(BaseSkill):
    name = "explore_codebase"
    description = "Khám phá và phân tích cấu trúc thư mục dự án mã nguồn, xác định tech stack và cây thư mục."
    parameters = {
        "type": "object",
        "properties": {
            "root_path": {"type": "string", "description": "Đường dẫn thư mục dự án cần phân tích (mặc định là thư mục hiện tại)", "default": "."},
            "max_depth": {"type": "integer", "description": "Độ sâu tối đa của cây thư mục", "default": 3},
        },
        "required": [],
    }
    requires_approval = False

    async def execute(self, root_path: str = ".", max_depth: int = 3, **kwargs) -> Dict[str, Any]:
        target = Path(root_path).resolve()
        if not target.exists():
            return {"error": f"Đường dẫn không tồn tại: {root_path}"}

        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "target", "bin", "obj", ".idea", ".vscode"}
        lines = [f"📁 **Dự án:** `{target.name}` (`{target}`)\n```text"]
        stats = {"files": 0, "dirs": 0, "extensions": {}}

        def _walk(current: Path, depth: int, prefix: str = ""):
            if depth > max_depth:
                return
            try:
                entries = sorted(list(current.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
            except PermissionError:
                return

            for i, entry in enumerate(entries):
                if entry.name in ignore_dirs or entry.name.startswith("."):
                    continue
                is_last = (i == len(entries) - 1)
                connector = "└── " if is_last else "├── "
                sub_prefix = "    " if is_last else "│   "

                if entry.is_dir():
                    stats["dirs"] += 1
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    _walk(entry, depth + 1, prefix + sub_prefix)
                else:
                    stats["files"] += 1
                    ext = entry.suffix.lower() or "no_ext"
                    stats["extensions"][ext] = stats["extensions"].get(ext, 0) + 1
                    lines.append(f"{prefix}{connector}{entry.name}")

        _walk(target, 1)
        lines.append("```")

        # Detect stack
        stack = []
        if stats["extensions"].get(".py"): stack.append("Python")
        if stats["extensions"].get(".rs"): stack.append("Rust")
        if stats["extensions"].get(".rb"): stack.append("Ruby / SketchUp API")
        if stats["extensions"].get(".cpp") or stats["extensions"].get(".h"): stack.append("C/C++")
        if stats["extensions"].get(".ts") or stats["extensions"].get(".js"): stack.append("JavaScript/TypeScript")

        summary = (
            f"\n📊 **Thống kê:** {stats['dirs']} thư mục, {stats['files']} tệp tin.\n"
            f"🛠 **Tech Stack phát hiện:** {', '.join(stack) if stack else 'Không rõ'}"
        )
        return {
            "tree_view": "\n".join(lines[:120]),  # cap output length
            "summary": summary,
            "detected_stack": stack,
        }


class CodeSecurityAuditSkill(BaseSkill):
    name = "security_code_audit"
    description = "Quét mã nguồn hoặc file để phát hiện các lỗ hổng bảo mật: hardcoded keys, injection, unsafe eval."
    parameters = {
        "type": "object",
        "properties": {
            "target_path": {"type": "string", "description": "Đường dẫn file hoặc thư mục cần quét bảo mật"},
        },
        "required": ["target_path"],
    }
    requires_approval = False

    VULNERABILITY_PATTERNS = [
        (r"(?i)(api[_-]?key|secret|token|password|passwd)\s*=\s*['\"][A-Za-z0-9_\-]{8,}['\"]", "High: Khả năng lộ Hardcoded Secret / API Token"),
        (r"\beval\s*\(", "Critical: Sử dụng hàm eval() tiềm ẩn nguy cơ Remote Code Execution (RCE)"),
        (r"\bexec\s*\(", "Critical: Sử dụng hàm exec() có thể bị inject mã độc"),
        (r"\bos\.system\s*\(", "High: Sử dụng os.system() dễ bị Command Injection"),
        (r"\bsubprocess\.(Popen|run|call)\(.*shell\s*=\s*True", "High: Shell=True trong subprocess tiềm ẩn lỗ hổng chèn lệnh"),
        (r"SELECT\s+.+\s+FROM\s+.+\s+WHERE\s+.+%\s*\(", "High: Tiềm ẩn SQL Injection qua nối chuỗi thô"),
    ]

    async def execute(self, target_path: str, **kwargs) -> Dict[str, Any]:
        path = Path(target_path)
        if not path.exists():
            return {"error": f"Không tìm thấy đường dẫn: {target_path}"}

        files_to_scan = []
        if path.is_file():
            files_to_scan.append(path)
        else:
            for ext in ("*.py", "*.js", "*.ts", "*.rb", "*.rs", "*.cpp"):
                files_to_scan.extend(path.rglob(ext))

        findings = []
        for file_p in files_to_scan[:50]:  # limit batch
            try:
                content = file_p.read_text(encoding="utf-8", errors="ignore")
                for line_idx, line in enumerate(content.splitlines(), start=1):
                    for pattern, desc in self.VULNERABILITY_PATTERNS:
                        if re.search(pattern, line):
                            findings.append({
                                "file": str(file_p.name),
                                "line": line_idx,
                                "snippet": line.strip()[:100],
                                "severity": desc,
                            })
            except Exception as e:
                logger.warning(f"Error scanning {file_p}: {e}")

        if not findings:
            report = f"✅ **RÀ SOÁT BẢO MẬT:** Đã quét {len(files_to_scan)} tệp. Không phát hiện lỗ hổng cơ bản nào!"
        else:
            report = f"⚠️ **CẢNH BÁO BẢO MẬT:** Phát hiện {len(findings)} điểm rủi ro:\n"
            for f in findings[:10]:
                report += f"- `{f['file']}:{f['line']}` - **{f['severity']}**\n  > Code: `{f['snippet']}`\n"

        return {"total_scanned": len(files_to_scan), "findings": findings, "report": report}
