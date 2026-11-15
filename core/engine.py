"""
tokudo.core.engine
Central Intelligence Core: Multi-Brain Routing, LLM Reasoning, Tool Calling,
Memory Injection, Knowledge Search, and Multi-Frontend Dispatching.
"""

from __future__ import annotations
import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

from core.schema import (
    PlatformType,
    UnifiedMessage,
    UnifiedResponse,
    ActionButton,
    ButtonStyle,
)
from core.security import SecurityManager
from core.brain_router import MultiBrainRouter, BrainAccount
from brain.memory_manager import MemoryManager
from brain.wiki_distiller import WikiDistiller
from skills.base import SkillRegistry, BaseSkill
from skills.skill_builder import SkillBuilderSkill
from automation.kanban_worker import KanbanWorker
from automation.scheduler import TaskScheduler

logger = logging.getLogger("tokudo.core.engine")


class TokudoEngine:
    """
    Central Coordinator for the Tokudo AI System.
    Harmonizes Multi-Brain Pool, Brain, Skills, Security, Automation, and Multi-Platform Frontends.
    """

    def __init__(
        self,
        security_manager: SecurityManager,
        memory_manager: MemoryManager,
        wiki_distiller: WikiDistiller,
        skill_registry: SkillRegistry,
        kanban_worker: KanbanWorker,
        task_scheduler: TaskScheduler,
    ):
        self.machine_id = os.getenv("MACHINE_ID", "PC-LOCAL")
        self.security = security_manager
        self.memory = memory_manager
        self.wiki = wiki_distiller
        self.skill_registry = skill_registry
        self.kanban = kanban_worker
        self.scheduler = task_scheduler

        # Connect mutual dependencies
        self.kanban.set_engine(self)
        self.scheduler.set_engine(self)

        # Connect meta-skill registry reference
        builder_skill = self.skill_registry.get_skill("skill_builder")
        if builder_skill and isinstance(builder_skill, SkillBuilderSkill):
            builder_skill.set_registry(self.skill_registry)

        # Registered platform adapters
        self.adapters: Dict[PlatformType, Any] = {}

        # Multi-Brain Router with Multi-Account Pooling & Telemetry
        self.brain_router = MultiBrainRouter()

    def register_adapter(self, platform: PlatformType, adapter_instance: Any) -> None:
        """Registers a frontend adapter (Telegram, Discord, etc.)."""
        self.adapters[platform] = adapter_instance
        logger.info(f"Registered platform adapter for '{platform.value}'")

    async def generate_raw(self, prompt: str, temperature: float = 0.3) -> str:
        """Helper for raw LLM completions used in Auto-Reflection and Distillation."""
        try:
            res_text, _, _, _ = await self.brain_router.execute_chat(
                system_prompt="You are a precise, analytical assistant.",
                user_message=prompt,
                temperature=temperature,
            )
            return res_text
        except Exception as e:
            logger.warning(f"generate_raw fallback failure: {e}")
            return ""

    async def dispatch_response(self, response: UnifiedResponse) -> None:
        """
        Routes standardized response to the appropriate platform adapter.
        Guarantees [MACHINE_ID] prefix on all outgoing texts.
        """
        prefix = f"[{self.machine_id}] "
        if not response.text.startswith(f"[{self.machine_id}]"):
            response.text = f"{prefix}{response.text}"

        adapter = self.adapters.get(response.target_platform)
        if adapter:
            await adapter.send_response(response)
        else:
            logger.error(f"Cannot dispatch response: No adapter registered for {response.target_platform}")

    async def process_message(self, message: UnifiedMessage) -> Optional[UnifiedResponse]:
        """
        Main pipeline entry point for all incoming messages from Telegram & Discord.
        """
        # Step 1: Whitelist Security Check
        if not self.security.is_authorized(message.platform, message.user_id):
            logger.warning(
                f"Unauthorized message from user {message.user_id} on {message.platform}. Silently dropping."
            )
            return None

        # Step 2: Handle Interactive Button Callbacks (HITL approvals & Multi-Brain switching)
        if message.text.startswith("hitl:"):
            return await self._handle_hitl_callback(message)
        elif message.text.startswith("brain:"):
            return await self._handle_brain_callback(message)

        # Step 3: Handle Slash Commands
        command_resp = await self._handle_commands(message)
        if command_resp:
            return command_resp

        # Step 4: Core Multi-Brain Reasoning & Tool Execution
        response_text, files, extra_buttons = await self._execute_agent_reasoning(message)

        # Step 5: Trigger asynchronous self-reflection in background
        asyncio.create_task(
            self.memory.auto_reflect(message.text, response_text, llm_engine=self)
        )

        # Step 6: Construct UnifiedResponse
        return UnifiedResponse(
            target_platform=message.platform,
            target_channel_id=message.channel_id,
            text=f"[{self.machine_id}] {response_text}",
            attachments=files,
            buttons=extra_buttons,
            reply_to_message_id=message.id,
        )

    async def _handle_hitl_callback(self, message: UnifiedMessage) -> UnifiedResponse:
        """Processes user clicks on [✅ Chấp thuận] or [❌ Từ chối] buttons."""
        parts = message.text.split(":")
        if len(parts) >= 3:
            action = parts[1]
            approval_id = parts[2]
            approved = (action == "approve")
            resolved = self.security.resolve_approval(approval_id, approved)

            status_icon = "✅ ĐÃ PHÊ DUYỆT" if approved else "❌ ĐÃ TỪ CHỐI"
            result_str = (
                f"{status_icon} yêu cầu lệnh `{approval_id}`.\n"
                f"Hệ thống đang tiếp tục quy trình." if resolved else f"⚠️ Yêu cầu `{approval_id}` đã hết hạn hoặc không tồn tại."
            )
            return UnifiedResponse(
                target_platform=message.platform,
                target_channel_id=message.channel_id,
                text=f"[{self.machine_id}] {result_str}",
            )
        return UnifiedResponse(
            target_platform=message.platform,
            target_channel_id=message.channel_id,
            text=f"[{self.machine_id}] Thao tác không hợp lệ.",
        )

    async def _handle_brain_callback(self, message: UnifiedMessage) -> UnifiedResponse:
        """Processes interactive button clicks for Multi-Brain Switching & Telemetry."""
        parts = message.text.split(":")
        action = parts[1] if len(parts) > 1 else ""

        if action == "switch" and len(parts) >= 3:
            target_acc = parts[2]
            success, msg = self.brain_router.set_active_brain(target_acc)
            return UnifiedResponse(
                target_platform=message.platform,
                target_channel_id=message.channel_id,
                text=f"[{self.machine_id}] {msg}",
            )
        elif action == "reload":
            self.brain_router.reload_config()
            return UnifiedResponse(
                target_platform=message.platform,
                target_channel_id=message.channel_id,
                text=f"[{self.machine_id}] 🔄 Đã nạp lại cấu hình Multi-Brain từ `data/brains.json` ({len(self.brain_router.accounts)} tài khoản).",
            )
        elif action == "stats":
            dashboard = self.brain_router.get_dashboard()
            return UnifiedResponse(
                target_platform=message.platform,
                target_channel_id=message.channel_id,
                text=f"[{self.machine_id}]\n{dashboard}",
            )

        return UnifiedResponse(
            target_platform=message.platform,
            target_channel_id=message.channel_id,
            text=f"[{self.machine_id}] Thao tác Multi-Brain không hợp lệ.",
        )

    async def _handle_commands(self, message: UnifiedMessage) -> Optional[UnifiedResponse]:
        """Built-in command dispatcher."""
        text = message.clean_text

        if text in ("/start", "/help"):
            active_brain = self.brain_router.get_active_brain()
            brain_name = active_brain.name if active_brain else "Chưa cấu hình"
            help_text = (
                f"🤖 **HỆ THỐNG TRỢ LÝ TOKUDO (PC: {self.machine_id})**\n\n"
                f"🧠 **Bộ não đang kích hoạt:** `{brain_name}`\n\n"
                f"• `/brain` hoặc `/model` - Bảng điều khiển Multi-Brain, đổi não & thống kê lưu lượng\n"
                f"• `/brain switch <id>` - Chuyển sang tài khoản AI cụ thể\n"
                f"• `/brain reload` - Nạp lại danh sách tài khoản từ `data/brains.json`\n"
                f"• `/status` - Kiểm tra phần cứng CPU/RAM, hàng đợi Kanban, Cron jobs\n"
                f"• `/remember <nội dung>` - Ghi nhớ kiến thức/thói quen vào bộ não dài hạn\n"
                f"• `/wiki <từ khóa>` - Tra cứu tri thức đã chưng cất (SQLite FTS5)\n"
                f"• `/queue <tiêu đề>` - Đẩy việc nặng vào hàng đợi xử lý ngầm\n"
                f"• `/skills` - Liệt kê danh sách kỹ năng khả dụng\n\n"
                f"Bạn có thể nhắn tin bằng ngôn ngữ tự nhiên để trò chuyện, yêu cầu điều khiển Windows, lập trình hoặc chụp màn hình!"
            )
            return UnifiedResponse(
                target_platform=message.platform,
                target_channel_id=message.channel_id,
                text=f"[{self.machine_id}] {help_text}",
            )

        elif text.startswith(("/brain", "/model")):
            parts = text.split()
            subcmd = parts[1] if len(parts) > 1 else ""

            if subcmd == "switch" and len(parts) > 2:
                target_id = parts[2].strip()
                success, msg = self.brain_router.set_active_brain(target_id)
                return UnifiedResponse(
                    target_platform=message.platform,
                    target_channel_id=message.channel_id,
                    text=f"[{self.machine_id}] {msg}",
                )

            elif subcmd in ("stats", "usage"):
                dashboard = self.brain_router.get_dashboard()
                return UnifiedResponse(
                    target_platform=message.platform,
                    target_channel_id=message.channel_id,
                    text=f"[{self.machine_id}]\n{dashboard}",
                )

            elif subcmd == "reload":
                self.brain_router.reload_config()
                return UnifiedResponse(
                    target_platform=message.platform,
                    target_channel_id=message.channel_id,
                    text=f"[{self.machine_id}] 🔄 Đã nạp lại cấu hình `data/brains.json` ({len(self.brain_router.accounts)} tài khoản sẵn sàng).",
                )

            # Default /brain view: show dashboard with interactive buttons for 1-click switching
            dashboard = self.brain_router.get_dashboard()
            buttons: List[ActionButton] = []
            active_id = self.brain_router.active_account_id

            # Create quick switch buttons for top enabled accounts
            for acc in list(self.brain_router.accounts.values())[:6]:
                if acc.enabled:
                    label = f"🌟 {acc.name[:16]}" if acc.id == active_id else f"👉 {acc.name[:16]}"
                    style = ButtonStyle.SUCCESS if acc.id == active_id else ButtonStyle.PRIMARY
                    buttons.append(
                        ActionButton(
                            id=f"btn_switch_{acc.id}",
                            label=label,
                            callback_data=f"brain:switch:{acc.id}",
                            style=style,
                        )
                    )

            buttons.append(
                ActionButton(
                    id="btn_brain_reload",
                    label="🔄 Nạp lại file brains.json",
                    callback_data="brain:reload",
                    style=ButtonStyle.SECONDARY,
                )
            )

            return UnifiedResponse(
                target_platform=message.platform,
                target_channel_id=message.channel_id,
                text=f"[{self.machine_id}]\n{dashboard}",
                buttons=buttons,
            )

        elif text == "/status":
            metrics = await self.skill_registry.execute("system_metrics", {})
            kanban_status = self.kanban.get_summary()
            scheduler_status = self.scheduler.get_active_jobs_summary()
            active_brain = self.brain_router.get_active_brain()
            brain_line = f"🧠 **Bộ não:** `{active_brain.name if active_brain else 'N/A'}` (`{active_brain.model if active_brain else ''}`)\n\n"
            combined = f"{brain_line}{metrics['formatted_text']}\n\n{kanban_status}\n\n{scheduler_status}"
            return UnifiedResponse(
                target_platform=message.platform,
                target_channel_id=message.channel_id,
                text=f"[{self.machine_id}]\n{combined}",
            )

        elif text.startswith("/remember"):
            note = text.replace("/remember", "", 1).strip()
            if not note:
                return UnifiedResponse(
                    target_platform=message.platform,
                    target_channel_id=message.channel_id,
                    text=f"[{self.machine_id}] Vui lòng nhập nội dung cần ghi nhớ. Cú pháp: `/remember <nội dung>`",
                )
            result = self.memory.remember(note)
            return UnifiedResponse(
                target_platform=message.platform,
                target_channel_id=message.channel_id,
                text=f"[{self.machine_id}] {result}",
            )

        elif text.startswith("/wiki"):
            query = text.replace("/wiki", "", 1).strip()
            if not query:
                return UnifiedResponse(
                    target_platform=message.platform,
                    target_channel_id=message.channel_id,
                    text=f"[{self.machine_id}] Vui lòng nhập từ khóa tra cứu. Cú pháp: `/wiki <từ khóa>`",
                )
            results = self.wiki.search(query, limit=3)
            if not results:
                return UnifiedResponse(
                    target_platform=message.platform,
                    target_channel_id=message.channel_id,
                    text=f"[{self.machine_id}] 🔍 Không tìm thấy trang wiki nào khớp với: `{query}`",
                )
            lines = [f"📚 **KẾT QUẢ TRA CỨU TRI THỨC CHO: `{query}`**\n"]
            for r in results:
                lines.append(f"• **{r['title']}** (Tags: `{r['tags']}`)")
                lines.append(f"  > ...{r['snippet']}...")
                lines.append(f"  > Trích dẫn: `{r['file_path']}`\n")
            return UnifiedResponse(
                target_platform=message.platform,
                target_channel_id=message.channel_id,
                text=f"[{self.machine_id}] " + "\n".join(lines),
            )

        elif text.startswith("/queue"):
            title = text.replace("/queue", "", 1).strip() or "Tác vụ chạy ngầm"
            task_id = await self.kanban.submit_task(
                title=title,
                description=f"Yêu cầu từ {message.platform.value}",
                origin_platform=message.platform,
                origin_channel_id=message.channel_id,
                origin_user_id=message.user_id,
            )
            return UnifiedResponse(
                target_platform=message.platform,
                target_channel_id=message.channel_id,
                text=f"[{self.machine_id}] 📥 Đã đưa vào hàng đợi Kanban ngầm: `#{task_id}` — **{title}**\nBot sẽ tự động báo cáo khi hoàn tất!",
            )

        elif text == "/skills":
            skills_list = [f"• `{name}`: {skill.description}" for name, skill in self.skill_registry.skills.items()]
            skills_str = "\n".join(skills_list)
            return UnifiedResponse(
                target_platform=message.platform,
                target_channel_id=message.channel_id,
                text=f"[{self.machine_id}] 🛠 **DANH SÁCH KỸ NĂNG KHẢ DỤNG ({len(self.skill_registry.skills)}):**\n{skills_str}",
            )

        return None

    async def _execute_agent_reasoning(
        self, message: UnifiedMessage
    ) -> tuple[str, List[str], List[ActionButton]]:
        """
        Coordinates context assembly, Multi-Brain LLM execution with Smart Failover,
        tool calling, and HITL approvals.
        """
        # Step A: Retrieve Context from Second Brain (Memory + Wiki)
        memory_ctx = self.memory.get_consolidated_context()
        wiki_results = self.wiki.search(message.text, limit=2)
        wiki_ctx = ""
        if wiki_results:
            wiki_ctx = "\n### [Relevant Knowledge Citations]:\n" + "\n".join(
                [f"- {r['title']}: {r['snippet']} (File: {r['file_path']})" for r in wiki_results]
            )

        system_prompt = (
            f"You are Tokudo — an elite, highly capable Personal AI Assistant and Second Brain "
            f"operating locally on a Windows workstation (Machine ID: {self.machine_id}).\n\n"
            f"Operating Guidelines:\n"
            f"- Communication style: Concise, technical, actionable, respectful.\n"
            f"- Tech Stack expertise: Python, Rust, Ruby for SketchUp API, C++, Windows PowerShell.\n"
            f"- You have direct access to tools/skills on Windows.\n\n"
            f"### [Persistent Memory Context]:\n{memory_ctx}\n"
            f"{wiki_ctx}\n"
        )

        tools = self.skill_registry.get_tool_schemas()
        generated_files = []
        action_buttons = []

        try:
            # Multi-turn reasoning with Multi-Brain Router
            reply_text, tool_calls, used_brain, failover_notice = await self.brain_router.execute_chat(
                system_prompt=system_prompt,
                user_message=message.text,
                tools=tools,
            )

            # If tool calls are requested
            if tool_calls:
                for tc in tool_calls:
                    func_name = tc.get("name")
                    args = tc.get("arguments", {})

                    skill = self.skill_registry.get_skill(func_name)
                    if not skill:
                        continue

                    # Check if tool requires approval (HITL)
                    requires_hitl = skill.requires_approval
                    if func_name == "windows_app_controller" and args.get("action") == "close":
                        requires_hitl = True

                    if requires_hitl and self.security.require_approval:
                        cmd_desc = f"{func_name}({', '.join(f'{k}={v}' for k, v in args.items())})"
                        req, approval_response = self.security.create_approval_request(
                            skill_name=func_name,
                            command_desc=cmd_desc,
                            arguments=args,
                            origin_platform=message.platform,
                            origin_channel_id=message.channel_id,
                            origin_user_id=message.user_id,
                        )
                        await self.dispatch_response(approval_response)

                        approved = await self.security.wait_for_approval(req.id)
                        if not approved:
                            return (
                                f"🛑 Thao tác `{func_name}` đã bị TỪ CHỐI hoặc HẾT HẠN phê duyệt.",
                                generated_files,
                                action_buttons,
                            )

                    # Execute Skill
                    exec_result = await skill.execute(**args)
                    if isinstance(exec_result, dict):
                        if "file_path" in exec_result:
                            generated_files.append(exec_result["file_path"])

                    # Re-synthesize output
                    synthesis_prompt = (
                        f"User asked: {message.text}\n"
                        f"Executed tool: {func_name} with result:\n{json.dumps(exec_result, ensure_ascii=False)[:3000]}\n"
                        f"Provide a clear, helpful final response."
                    )
                    reply_text, _, _, _ = await self.brain_router.execute_chat(
                        system_prompt=system_prompt,
                        user_message=synthesis_prompt,
                    )

            # Prepend failover notice if system had to switch accounts automatically
            final_text = reply_text
            if failover_notice:
                final_text = f"_{failover_notice}_\n\n{reply_text}"

            return final_text, generated_files, action_buttons

        except Exception as e:
            logger.error(f"Error in Multi-Brain execution: {e}", exc_info=True)
            return (
                f"❌ Sự cố Multi-Brain Router: {str(e)}\n"
                f"💡 Mẹo: Dùng `/brain` để kiểm tra trạng thái các tài khoản hoặc `/brain switch <id>` để đổi bộ não khác.",
                generated_files,
                action_buttons,
            )
