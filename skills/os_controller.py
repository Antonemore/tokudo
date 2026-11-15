"""
tokudo.skills.os_controller
Cross-Platform Operating System Management:
Supports Windows, macOS, and Linux for App Management, Hardware Metrics, Screenshot, and Shell Execution.
"""

from __future__ import annotations
import os
import sys
import psutil
import platform
import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from skills.base import BaseSkill

logger = logging.getLogger("tokudo.skills.os")


class SystemMetricsSkill(BaseSkill):
    name = "system_metrics"
    description = "Kiểm tra tình trạng phần cứng máy tính: CPU, RAM, Disk, hệ điều hành (Windows/macOS/Linux)."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    requires_approval = False

    async def execute(self, **kwargs) -> Dict[str, Any]:
        cpu_pct = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()

        # Dynamic root drive path across Windows (C:\), macOS (/), and Linux (/)
        root_path = os.path.abspath(os.sep)
        try:
            disk = psutil.disk_usage(root_path)
        except Exception:
            disk = psutil.disk_usage(".")

        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            boot_time = "N/A"

        os_name = platform.system()
        os_release = platform.release()

        report = (
            f"💻 **THÔNG SỐ HỆ THỐNG ({os_name.upper()})**\n"
            f"• **Hệ điều hành:** `{os_name} {os_release}` ({platform.machine()})\n"
            f"• **CPU Usage:** `{cpu_pct}%`\n"
            f"• **RAM:** `{ram.used // (1024**3)}GB / {ram.total // (1024**3)}GB ({ram.percent}%)`\n"
            f"• **Ổ đĩa gốc ({root_path}):** `{disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB ({disk.percent}%)`\n"
            f"• **Thời gian khởi động (Boot Time):** `{boot_time}`"
        )
        return {
            "formatted_text": report,
            "os_name": os_name,
            "cpu_percent": cpu_pct,
            "ram_percent": ram.percent,
            "disk_percent": disk.percent,
        }


class ScreenshotSkill(BaseSkill):
    name = "capture_screenshot"
    description = "Chụp ảnh màn hình máy tính hiện tại (Windows, macOS, Linux) và lưu thành file ảnh."
    parameters = {
        "type": "object",
        "properties": {
            "monitor": {"type": "integer", "description": "Số thứ tự màn hình (mặc định toàn bộ)", "default": 0}
        },
        "required": [],
    }
    requires_approval = False

    async def execute(self, **kwargs) -> Dict[str, Any]:
        output_dir = Path("data/screenshots")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = output_dir / f"screenshot_{timestamp}.png"

        def _grab():
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab(all_screens=True)
                if img:
                    img.save(str(file_path), "PNG")
                    return True
            except Exception as e:
                logger.warning(f"PIL ImageGrab failed or headless display: {e}")
                # Fallback on macOS using screencapture CLI
                if platform.system() == "Darwin":
                    subprocess.run(["screencapture", "-x", str(file_path)], check=False)
                    return file_path.exists()
            return False

        success = await asyncio.to_thread(_grab)
        if success and file_path.exists():
            logger.info(f"Captured screenshot: {file_path}")
            return {
                "status": "success",
                "file_path": str(file_path.resolve()),
                "message": f"📸 Đã chụp màn hình thành công tại `{file_path.name}`",
            }
        else:
            return {
                "status": "warning",
                "message": "⚠️ Không thể chụp ảnh màn hình (môi trường máy chủ không có giao diện hiển thị - Headless Display).",
            }


class CrossPlatformAppControllerSkill(BaseSkill):
    name = "windows_app_controller"  # Maintained alias for backward compatibility
    description = "Khởi chạy hoặc đóng các ứng dụng trên Windows, macOS hoặc Linux (Blender, Chrome, VSCode, v.v.)."
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Tên ứng dụng (vd: sketchup, blender, autocad, chrome, code, notepad)",
            },
            "action": {
                "type": "string",
                "enum": ["launch", "close"],
                "description": "Hành động: 'launch' để mở hoặc 'close' để đóng ứng dụng",
            },
        },
        "required": ["app_name", "action"],
    }
    requires_approval = False

    async def execute(self, app_name: str, action: str, **kwargs) -> Dict[str, Any]:
        os_sys = platform.system()
        app_clean = app_name.lower().strip()

        if action == "launch":
            try:
                if os_sys == "Windows":
                    cmd = f"start {app_clean}"
                elif os_sys == "Darwin":
                    cmd = f"open -a '{app_name}'"
                else:  # Linux
                    cmd = f"xdg-open {app_clean} >/dev/null 2>&1 || {app_clean} &"

                proc = await asyncio.create_subprocess_shell(
                    cmd, shell=True, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                return {"status": "success", "message": f"🚀 Đã phát lệnh mở ứng dụng `{app_name}` trên {os_sys}."}
            except Exception as e:
                return {"status": "error", "message": f"❌ Lỗi mở `{app_name}`: {str(e)}"}

        elif action == "close":
            killed = 0
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if app_clean in proc.info["name"].lower():
                        proc.terminate()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if killed > 0:
                return {"status": "success", "message": f"🛑 Đã đóng {killed} tiến trình của `{app_name}`."}
            else:
                return {"status": "not_found", "message": f"⚠️ Không tìm thấy tiến trình đang chạy của `{app_name}`."}


class TerminalCommandSkill(BaseSkill):
    name = "run_terminal_command"
    description = "Thực thi lệnh Terminal / Shell (PowerShell trên Windows, Bash trên Linux/macOS). Luôn yêu cầu phê duyệt bảo mật."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Lệnh dòng lệnh cần thực thi"}
        },
        "required": ["command"],
    }
    requires_approval = True  # Strict Human-In-The-Loop required!

    async def execute(self, command: str, **kwargs) -> Dict[str, Any]:
        os_sys = platform.system()
        logger.info(f"Executing approved command on {os_sys}: {command}")

        try:
            if os_sys == "Windows":
                process = await asyncio.create_subprocess_exec(
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                # Linux & macOS use bash / sh
                shell_bin = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
                process = await asyncio.create_subprocess_exec(
                    shell_bin,
                    "-c",
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
            out_str = stdout.decode("utf-8", errors="replace").strip()
            err_str = stderr.decode("utf-8", errors="replace").strip()

            return {
                "exit_code": process.returncode,
                "stdout": out_str[:3000] if out_str else "(empty)",
                "stderr": err_str[:1000] if err_str else "(none)",
                "formatted_output": f"```\n{out_str or err_str}\n```",
            }
        except asyncio.TimeoutError:
            return {"error": "Lệnh bị vượt quá thời gian thực thi (timeout 60s)."}
        except Exception as e:
            return {"error": f"Lỗi thực thi lệnh: {str(e)}"}
