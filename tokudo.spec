# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Hidden imports for dynamic and lazy modules
hidden_imports = [
    "aiofiles",
    "aiohttp",
    "apscheduler",
    "apscheduler.schedulers.asyncio",
    "apscheduler.triggers.interval",
    "apscheduler.triggers.cron",
    "apscheduler.triggers.date",
    "discord",
    "telegram",
    "telegram.ext",
    "psutil",
    "edge_tts",
    "youtube_transcript_api",
    "openai",
    "google.generativeai",
    "google.ai.generativelanguage",
    "pydantic",
    "pydantic_core",
    "sqlite3",
    "dotenv",
    "multidict",
    "yarl",
    "asyncio",
    "webbrowser",
    "core",
    "core.schema",
    "core.security",
    "core.engine",
    "core.brain_router",
    "core.version",
    "brain",
    "brain.memory_manager",
    "brain.wiki_distiller",
    "skills",
    "skills.base",
    "skills.os_controller",
    "skills.code_architect",
    "skills.multimodal",
    "skills.skill_builder",
    "adapters",
    "adapters.telegram_adapter",
    "adapters.discord_adapter",
    "web",
    "web.dashboard_server",
    "automation",
    "automation.kanban_worker",
    "automation.scheduler",
]

hidden_imports += collect_submodules("pydantic")
hidden_imports += collect_submodules("pydantic_core")
hidden_imports += collect_submodules("apscheduler")

datas = [
    ("skills/*.py", "skills"),
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Tokudo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
