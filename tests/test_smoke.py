"""
Smoke test verifying Tokudo core systems, Multi-Brain routing, memory, and wiki distillation.
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

# Force UTF-8 on Windows console (prevents UnicodeEncodeError on CI runners)
if sys.platform == "win32":
    import io
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncio
from core.schema import PlatformType, UnifiedMessage, UnifiedResponse
from core.security import SecurityManager
from core.brain_router import MultiBrainRouter
from brain.memory_manager import MemoryManager
from brain.wiki_distiller import WikiDistiller
from skills.base import SkillRegistry
from automation.kanban_worker import KanbanWorker
from automation.scheduler import TaskScheduler
from core.engine import TokudoEngine


async def test_all():
    print("=== TEST 1: Security Whitelist & HITL ===")
    os.environ["TELEGRAM_ALLOWED_USER_ID"] = "111,222"
    os.environ["DISCORD_ALLOWED_USER_ID"] = "333,444"
    sec = SecurityManager()
    assert sec.is_authorized(PlatformType.TELEGRAM, 111) is True
    assert sec.is_authorized(PlatformType.TELEGRAM, 999) is False
    assert sec.is_authorized(PlatformType.DISCORD, "333") is True
    assert sec.is_authorized(PlatformType.DISCORD, "888") is False
    print("  -> Security Whitelist check passed.")

    req, resp = sec.create_approval_request(
        "test_action", "rm -rf test", {}, PlatformType.TELEGRAM, 111, 111
    )
    assert req.id == resp.approval_id
    sec.resolve_approval(req.id, True)
    approved = await sec.wait_for_approval(req.id)
    assert approved is True
    print("  -> HITL Approval flow passed.")

    print("\n=== TEST 2: Multi-Brain Router & Quota Telemetry ===")
    router = MultiBrainRouter(config_path="data/brains.json")
    assert len(router.accounts) >= 8
    # Switch test
    ok, switch_msg = router.set_active_brain("gemini_free_1")
    assert ok is True
    assert router.active_account_id == "gemini_free_1"
    # Usage recording
    router.tracker.record_usage("gemini_free_1", "gemini-1.5-flash", 200, 150)
    dash = router.get_dashboard()
    assert "Gemini 1.5 Flash (Free Acc 1)" in dash
    print("  -> Multi-Brain Pool and Dashboard telemetry verified.")

    print("\n=== TEST 3: Memory Manager ===")
    mem = MemoryManager(memory_dir="brain/memory")
    ctx = mem.get_consolidated_context()
    assert "User Profile" in ctx
    mem.append_memory("preferences.md", "Ưu tiên phản hồi bằng tiếng Việt ngắn gọn")
    print("  -> Memory Manager read/append passed.")

    print("\n=== TEST 4: Wiki Distiller & FTS5 ===")
    wiki = WikiDistiller(wiki_dir="brain/wiki", db_path="brain/index.db")
    doc = await wiki.distill(
        title="Sketchup Ruby API Architecture",
        raw_content="Ruby API allows manipulating SketchUp active_model entities directly via Sketchup.active_model.entities.add_face.",
        tags=["sketchup", "ruby", "3d"],
    )
    assert Path(doc["path"]).exists()
    search_res = wiki.search("Sketchup Ruby", limit=2)
    assert len(search_res) > 0
    assert "Sketchup" in search_res[0]["title"]
    print("  -> Wiki distillation & FTS5 search passed.")

    print("\n=== TEST 5: Skills Discovery & Execution ===")
    registry = SkillRegistry()
    registry.discover_and_load()
    assert "system_metrics" in registry.skills
    assert "capture_screenshot" in registry.skills
    assert "explore_codebase" in registry.skills
    assert "skill_builder" in registry.skills

    metrics = await registry.execute("system_metrics", {})
    assert "cpu_percent" in metrics
    print(f"  -> System Metrics executed: CPU={metrics['cpu_percent']}%, RAM={metrics['ram_percent']}%")

    code_info = await registry.execute("explore_codebase", {"root_path": ".", "max_depth": 1})
    assert "tree_view" in code_info
    print("  -> Codebase Explorer executed successfully.")

    print("\n=== TEST 6: Kanban Background Worker ===")
    kanban = KanbanWorker()
    task_id = await kanban.submit_task(
        title="Nhiệm vụ kiểm thử",
        description="Test background execution",
        origin_platform=PlatformType.TELEGRAM,
        origin_channel_id=111,
        origin_user_id=111,
    )
    assert len(task_id) == 8
    board = kanban.get_summary()
    assert "TODO" in board
    print("  -> Kanban Worker task creation & summary passed.")

    print("\n=== TEST 7: Tokudo Engine Coordination with Multi-Brain ===")
    scheduler = TaskScheduler()
    engine = TokudoEngine(
        security_manager=sec,
        memory_manager=mem,
        wiki_distiller=wiki,
        skill_registry=registry,
        kanban_worker=kanban,
        task_scheduler=scheduler,
    )

    # Test /brain command
    msg_brain = UnifiedMessage(
        id="10",
        platform=PlatformType.TELEGRAM,
        channel_id=111,
        user_id=111,
        text="/brain",
    )
    brain_resp = await engine.process_message(msg_brain)
    assert brain_resp is not None
    assert "MULTI-BRAIN" in brain_resp.text
    assert len(brain_resp.buttons) > 0
    print(f"  -> Engine /brain returned Dashboard with {len(brain_resp.buttons)} action buttons!")

    # Test /status command
    msg_status = UnifiedMessage(
        id="11",
        platform=PlatformType.TELEGRAM,
        channel_id=111,
        user_id=111,
        text="/status",
    )
    status_resp = await engine.process_message(msg_status)
    assert status_resp is not None
    assert f"[{engine.machine_id}]" in status_resp.text
    assert "THÔNG SỐ HỆ THỐNG" in status_resp.text
    print(f"  -> Engine /status returned with Machine ID prefix.")

    # Test unauthorized message drop
    msg_unauth = UnifiedMessage(
        id="12",
        platform=PlatformType.TELEGRAM,
        channel_id=999,
        user_id=999,
        text="Hello",
    )
    unauth_resp = await engine.process_message(msg_unauth)
    assert unauth_resp is None
    print("  -> Engine silently dropped unauthorized user as required.")

    print("\n🎉 ALL SMOKE TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(test_all())
