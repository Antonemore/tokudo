"""
tokudo.main
Unified Entrypoint for Tokudo Personal AI Agent & Second Brain on Windows.
Runs Telegram, Discord, Task Scheduler, Background Kanban Queue, Core Engine,
and Embedded Web Dashboard (localhost:8080) in a single asyncio loop.
"""

from __future__ import annotations
import os
import sys
import signal
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment configuration (.env)
load_dotenv()

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tokudo.main")

# Core Subsystems
from core.schema import PlatformType
from core.security import SecurityManager
from core.engine import TokudoEngine
from brain.memory_manager import MemoryManager
from brain.wiki_distiller import WikiDistiller
from skills.base import SkillRegistry
from automation.kanban_worker import KanbanWorker
from automation.scheduler import TaskScheduler
from adapters.telegram_adapter import TelegramAdapter
from adapters.discord_adapter import DiscordAdapter
from web.dashboard_server import DashboardServer


async def main() -> None:
    logger.info("==================================================")
    logger.info("   TOKUDO — PERSONAL AI AGENT & SECOND BRAIN     ")
    logger.info("==================================================")

    machine_id = os.getenv("MACHINE_ID", "PC-WINDOWS-01")
    logger.info(f"Node Identifier: [{machine_id}]")

    # Ensure required runtime folders exist
    for folder in [
        "data/screenshots",
        "data/tts",
        "data/uploads",
        "brain/memory",
        "brain/wiki",
    ]:
        Path(folder).mkdir(parents=True, exist_ok=True)

    # 1. Initialize Security & Core Components
    security_mgr = SecurityManager()
    memory_mgr = MemoryManager()
    wiki_distiller = WikiDistiller()

    # 2. Initialize and Discover Skills
    skill_registry = SkillRegistry()
    skill_registry.discover_and_load()

    # 3. Initialize Automation Components
    kanban_worker = KanbanWorker()
    task_scheduler = TaskScheduler()

    # 4. Initialize Core Intelligence Engine
    engine = TokudoEngine(
        security_manager=security_mgr,
        memory_manager=memory_mgr,
        wiki_distiller=wiki_distiller,
        skill_registry=skill_registry,
        kanban_worker=kanban_worker,
        task_scheduler=task_scheduler,
    )

    # 5. Initialize Platform Adapters
    telegram_adapter = TelegramAdapter(engine_ref=engine)
    discord_adapter = DiscordAdapter(engine_ref=engine)

    engine.register_adapter(PlatformType.TELEGRAM, telegram_adapter)
    engine.register_adapter(PlatformType.DISCORD, discord_adapter)

    # 6. Initialize Web Dashboard Server (localhost:8080)
    dash_host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    dash_port = int(os.getenv("DASHBOARD_PORT", "8080"))
    dashboard_server = DashboardServer(engine_ref=engine, host=dash_host, port=dash_port)

    # 7. Start Services Concurrently
    tasks = []

    # Start Task Scheduler
    task_scheduler.start()

    # Start Background Kanban Worker
    tasks.append(asyncio.create_task(kanban_worker.start(), name="KanbanWorker"))

    # Start Web Dashboard Server
    await dashboard_server.start()

    # Start Telegram Adapter (if token provided)
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if tg_token and not tg_token.startswith("your_"):
        await telegram_adapter.initialize()
        tasks.append(asyncio.create_task(telegram_adapter.start(), name="TelegramAdapter"))
    else:
        logger.info("ℹ️ Telegram Bot Token not set. Running without Telegram frontend.")

    # Start Discord Adapter (if token provided)
    dc_token = os.getenv("DISCORD_BOT_TOKEN", "")
    if dc_token and not dc_token.startswith("your_"):
        tasks.append(asyncio.create_task(discord_adapter.start(), name="DiscordAdapter"))
    else:
        logger.info("ℹ️ Discord Bot Token not set. Running without Discord frontend.")

    logger.info(f"Tokudo Engine online with {len(skill_registry.skills)} active skills.")
    logger.info(f"🌐 Visual Dashboard available at: http://{dash_host}:{dash_port}")

    # Graceful Shutdown Listener
    stop_event = asyncio.Event()

    def _handle_exit():
        logger.info("Received termination signal. Shutting down Tokudo gracefully...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for s in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(s, _handle_exit)

    try:
        # Wait until stopped
        while not stop_event.is_set():
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Interrupt caught. Cleaning up...")
    finally:
        # Graceful cleanup
        await dashboard_server.stop()
        await kanban_worker.stop()
        task_scheduler.shutdown()
        await telegram_adapter.stop()
        await discord_adapter.stop()

        for t in tasks:
            if not t.done():
                t.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All Tokudo services terminated cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
