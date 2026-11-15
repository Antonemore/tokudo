"""
tokudo.skills.os_controller
Windows OS Management, App Launcher/Closer, Screenshot, Hardware Metrics & Shell.
"""

from __future__ import annotations
import os
import sys
import psutil
import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from PIL import ImageGrab

from skills.base import BaseSkill

logger = logging.getLogger("tokudo.skills.os")


class SystemMetricsSkill(BaseSkill):
    name = "system_metrics"
    description = "Kiểm tra tình trạng phần cứng máy tính: CPU, RAM, Disk, nhiệt độ/uptime."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    requires_approval = False

    async def execute(self, **kwargs) -> Dict[str, Any]:
        cpu_pct = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")

        report = (
            f"💻 **THÔNG SỐ HỆ THỐNG WINDOWS**\n"
            f"• **CPU Usage:** `{cpu_pct}%`\n"
            f"• **RAM:** `{ram.used // (1024**3)}GB / {ram.total // (1024**3)}GB ({ram.percent}%)`\n"
            f"• **Ổ đĩa C:** `{disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB ({disk.percent}%)`\n"
            f"• **Thời gian khởi động (Boot Time):** `{boot_time}`"
        )
        return {
            "formatted_text": report,
            "cpu_percent": cpu_pct,
            "ram_percent": ram.percent,
            "disk_percent": disk.percent,
        }


class ScreenshotSkill(BaseSkill):
    name = "capture_screenshot"
    description = "Chụp ảnh màn hình máy tính Windows hiện tại và lưu thành file ảnh để gửi qua chat."
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

        # Execute screen grab in thread pool to prevent blocking asyncio loop
        def _grab():
            img = ImageGrab.grab(all_screens=True)
            img.save(str(file_path), "PNG")

        await asyncio.to_thread(_grab)
        logger.info(f"Captured screenshot: {file_path}")
        return {
            "status": "success",
            "file_path": str(file_path.resolve()),
            "message": f"📸 Đã chụp màn hình thành công tại `{file_path.name}`",
        }


class WindowsAppControllerSkill(BaseSkill):
    name = "windows_app_controller"
    description = "Khởi chạy hoặc đóng các ứng dụng Windows (SketchUp, Blender, AutoCAD, Chrome, VSCode, v.v.)."
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
    # Closing an app is sensitive, hence requires approval
    requires_approval = False  # Evaluated dynamically in engine if action == 'close'

    APP_MAP = {
        "sketchup": "sketchup.exe",
        "blender": "blender.exe",
        "autocad": "acad.exe",
        "chrome": "chrome.exe",
        "code": "code.exe",
        "vscode": "code.exe",
        "notepad": "notepad.exe",
        "calc": "calc.exe",
    }

    async def execute(self, app_name: str, action: str, **kwargs) -> Dict[str, Any]:
        app_key = app_name.lower().strip()
        exe_target = self.APP_MAP.get(app_key, app_name)

        if action == "launch":
            try:
                # Use start command to spawn detached process
                cmd = f"start {exe_target}"
                process = await asyncio.create_subprocess_shell(
                    cmd, shell=True, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                return {"status": "success", "message": f"🚀 Đã khởi chạy ứng dụng: `{app_name}`"}
            except Exception as e:
                return {"status": "error", "message": f"❌ Không thể mở ứng dụng `{app_name}`: {str(e)}"}

        elif action == "close":
            killed = 0
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if exe_target.lower() in proc.info["name"].lower():
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
    description = "Thực thi lệnh shell / PowerShell trên máy tính Windows. (Luôn yêu cầu xác nhận bảo mật)"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Lệnh PowerShell cần thực thi"}
        },
        "required": ["command"],
    }
    requires_approval = True  # Strict Human-In-The-Loop required!

    async def execute(self, command: str, **kwargs) -> Dict[str, Any]:
        logger.info(f"Executing approved terminal command: {command}")
        try:
            process = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-Command",
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
                "formatted_output": f"```powershell\n{out_str or err_str}\n```",
            }
        except asyncio.TimeoutError:
            return {"error": "Lệnh bị vượt quá thời gian thực thi (timeout 60s)."}
        except Exception as e:
            return {"error": f"Lỗi thực thi lệnh: {str(e)}"}
