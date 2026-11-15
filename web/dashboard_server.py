"""
tokudo.web.dashboard_server
Visual Web Dashboard for Tokudo Personal AI OS (equivalent to Javis OS).
Runs an asynchronous Web UI on http://localhost:8080 with:
- Multi-Brain Visual Fleet Management: Add, Edit, Delete, Test Ping, Save & Hot-Reload AI accounts
- Real-time Token Usage Telemetry & Cooldown timers
- Live System Hardware Metrics (CPU, RAM, Disk) & Screenshot preview
- Background Kanban Task Board & Second Brain Markdown Vault
"""

from __future__ import annotations
import os
import time
import json
import psutil
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from aiohttp import web

from core.schema import PlatformType
from core.brain_router import BrainAccount

logger = logging.getLogger("tokudo.web.dashboard")


HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="vi" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tokudo Workstation — AI OS Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <style>
    body { background-color: #090d16; color: #f1f5f9; font-family: ui-sans-serif, system-ui, sans-serif; }
    .glass { background: rgba(17, 24, 39, 0.75); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .glass-card { background: rgba(30, 41, 59, 0.6); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.05); }
    .glass-card:hover { border-color: rgba(99, 102, 241, 0.4); transform: translateY(-2px); transition: all 0.2s ease; }
    .badge-active { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-standby { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-cooldown { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-disabled { background: rgba(107, 114, 128, 0.2); color: #9ca3af; border: 1px solid rgba(107, 114, 128, 0.3); }
  </style>
</head>
<body class="min-h-screen flex flex-col antialiased">

  <!-- Top Navigation Header -->
  <header class="glass sticky top-0 z-40 px-6 py-3.5 flex items-center justify-between border-b border-slate-800">
    <div class="flex items-center space-x-3">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
        <i data-lucide="cpu" class="w-6 h-6 text-white"></i>
      </div>
      <div>
        <div class="flex items-center space-x-2">
          <span class="font-bold text-lg text-white tracking-wide">TOKUDO AI OS</span>
          <span id="machineIdBadge" class="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-indigo-400 font-mono border border-slate-700">PC-LOCAL</span>
        </div>
        <p class="text-xs text-slate-400">Personal AI Agent & Second Brain Hub</p>
      </div>
    </div>

    <!-- Live Telemetry Quick Pills -->
    <div class="hidden md:flex items-center space-x-4 text-xs font-mono">
      <div class="glass px-3 py-1.5 rounded-lg flex items-center space-x-2">
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        <span class="text-slate-400">CPU:</span>
        <span id="topCpu" class="text-emerald-400 font-semibold">0%</span>
      </div>
      <div class="glass px-3 py-1.5 rounded-lg flex items-center space-x-2">
        <span class="text-slate-400">RAM:</span>
        <span id="topRam" class="text-cyan-400 font-semibold">0%</span>
      </div>
      <div class="glass px-3 py-1.5 rounded-lg flex items-center space-x-2">
        <span class="text-slate-400">Tokens hôm nay:</span>
        <span id="topTokens" class="text-indigo-400 font-semibold">0</span>
      </div>
      <div class="glass px-3 py-1.5 rounded-lg flex items-center space-x-2">
        <span class="text-slate-400">Não chính:</span>
        <span id="topActiveBrain" class="text-white font-semibold">Loading...</span>
      </div>
    </div>

    <!-- Quick Refresh Button -->
    <div class="flex items-center space-x-2">
      <button onclick="fetchAllData()" class="px-3 py-1.5 rounded-lg glass text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-800 flex items-center space-x-1.5 transition">
        <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
        <span>Làm mới</span>
      </button>
    </div>
  </header>

  <!-- Main Container -->
  <div class="flex-1 flex max-w-7xl w-full mx-auto p-4 md:p-6 space-x-6">
    
    <!-- Sidebar Navigation -->
    <aside class="w-60 flex-shrink-0 space-y-2 hidden lg:block">
      <nav class="space-y-1 font-medium text-sm">
        <button onclick="switchTab('brains')" id="tabBtn-brains" class="w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
          <i data-lucide="brain-circuit" class="w-4 h-4"></i>
          <span>Multi-Brain Fleet</span>
        </button>
        <button onclick="switchTab('system')" id="tabBtn-system" class="w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition">
          <i data-lucide="activity" class="w-4 h-4"></i>
          <span>Hệ thống & Phần cứng</span>
        </button>
        <button onclick="switchTab('kanban')" id="tabBtn-kanban" class="w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition">
          <i data-lucide="trello" class="w-4 h-4"></i>
          <span>Kanban Tác vụ ngầm</span>
        </button>
        <button onclick="switchTab('memory')" id="tabBtn-memory" class="w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition">
          <i data-lucide="book-marked" class="w-4 h-4"></i>
          <span>Second Brain Vault</span>
        </button>
      </nav>

      <!-- Bot Connectivity Status Card -->
      <div class="glass p-3.5 rounded-xl text-xs space-y-2.5 pt-4">
        <p class="font-semibold text-slate-300 uppercase tracking-wider text-[10px]">Kênh Kết Nối</p>
        <div class="flex items-center justify-between">
          <span class="flex items-center space-x-2 text-slate-300">
            <i data-lucide="send" class="w-3.5 h-3.5 text-cyan-400"></i>
            <span>Telegram Bot</span>
          </span>
          <span id="statusTelegram" class="w-2 h-2 rounded-full bg-slate-600"></span>
        </div>
        <div class="flex items-center justify-between">
          <span class="flex items-center space-x-2 text-slate-300">
            <i data-lucide="message-square" class="w-3.5 h-3.5 text-indigo-400"></i>
            <span>Discord Bot</span>
          </span>
          <span id="statusDiscord" class="w-2 h-2 rounded-full bg-slate-600"></span>
        </div>
      </div>
    </aside>

    <!-- Tab Contents Container -->
    <main class="flex-1 space-y-6">

      <!-- ================= TAB 1: MULTI-BRAIN FLEET ================= -->
      <section id="tab-brains" class="space-y-6">
        <!-- Control Banner -->
        <div class="glass p-5 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 class="text-xl font-bold text-white flex items-center space-x-2">
              <span>Hạm Đội Tài Khoản AI (Multi-Brain Router)</span>
              <span id="accountCountBadge" class="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">0 tài khoản</span>
            </h1>
            <p class="text-xs text-slate-400 mt-1">Quản lý nhiều tài khoản ChatGPT, Gemini Pro/Free, Claude. Chuyển đổi tức thì hoặc tự động cứu hộ khi chạm hạn mức.</p>
          </div>

          <div class="flex items-center space-x-3">
            <!-- Auto-Failover Toggle -->
            <label class="flex items-center space-x-2 text-xs text-slate-300 cursor-pointer glass px-3 py-2 rounded-xl">
              <input type="checkbox" id="failoverToggle" onchange="toggleFailover()" class="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0">
              <span class="font-medium">Tự động cứu hộ (Auto-Failover)</span>
            </label>

            <!-- Add Brain Button -->
            <button onclick="openAccountModal()" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs flex items-center space-x-2 shadow-lg shadow-indigo-600/30 transition">
              <i data-lucide="plus" class="w-4 h-4"></i>
              <span>Thêm Tài Khoản</span>
            </button>
          </div>
        </div>

        <!-- Accounts Grid -->
        <div id="accountsGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <!-- Dynamically populated -->
        </div>
      </section>

      <!-- ================= TAB 2: SYSTEM HARDWARE ================= -->
      <section id="tab-system" class="space-y-6 hidden">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="glass p-5 rounded-2xl space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-400">VI XỬ LÝ (CPU)</span>
              <i data-lucide="cpu" class="w-4 h-4 text-emerald-400"></i>
            </div>
            <div class="text-3xl font-bold text-white font-mono" id="sysCpuVal">0%</div>
            <div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div id="sysCpuBar" class="bg-emerald-500 h-2 rounded-full" style="width: 0%"></div>
            </div>
          </div>

          <div class="glass p-5 rounded-2xl space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-400">BỘ NHỚ TRONG (RAM)</span>
              <i data-lucide="layers" class="w-4 h-4 text-cyan-400"></i>
            </div>
            <div class="text-3xl font-bold text-white font-mono" id="sysRamVal">0%</div>
            <div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div id="sysRamBar" class="bg-cyan-500 h-2 rounded-full" style="width: 0%"></div>
            </div>
            <p id="sysRamDetail" class="text-xs text-slate-500 font-mono">0 GB / 0 GB</p>
          </div>

          <div class="glass p-5 rounded-2xl space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-400">Ổ ĐĨA HỆ THỐNG (C:)</span>
              <i data-lucide="hard-drive" class="w-4 h-4 text-indigo-400"></i>
            </div>
            <div class="text-3xl font-bold text-white font-mono" id="sysDiskVal">0%</div>
            <div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div id="sysDiskBar" class="bg-indigo-500 h-2 rounded-full" style="width: 0%"></div>
            </div>
            <p id="sysDiskDetail" class="text-xs text-slate-500 font-mono">0 GB / 0 GB</p>
          </div>
        </div>

        <!-- Screenshot Preview Card -->
        <div class="glass p-5 rounded-2xl space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-bold text-white text-base">Chụp & Xem Màn Hình Cục Bộ</h3>
              <p class="text-xs text-slate-400">Chụp nhanh ảnh màn hình desktop Windows và xem ngay trên trình duyệt.</p>
            </div>
            <button onclick="triggerScreenshot()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center space-x-2 transition border border-slate-700">
              <i data-lucide="camera" class="w-4 h-4"></i>
              <span>Chụp Màn Hình Ngay</span>
            </button>
          </div>
          <div id="screenshotContainer" class="border border-slate-800 rounded-xl bg-slate-950/60 p-4 min-h-[220px] flex items-center justify-center text-slate-500 text-xs">
            Chưa có ảnh chụp mới nhất. Bấm nút trên để chụp.
          </div>
        </div>
      </section>

      <!-- ================= TAB 3: KANBAN QUEUE ================= -->
      <section id="tab-kanban" class="space-y-6 hidden">
        <div class="glass p-5 rounded-2xl flex items-center justify-between">
          <div>
            <h2 class="font-bold text-lg text-white">Hàng Đợi Kanban Xử Lý Tác Vụ Ngầm</h2>
            <p class="text-xs text-slate-400">Các tác vụ nặng (quét mã nguồn, chưng cất tài liệu, xuất render) chạy trong luồng nền.</p>
          </div>
          <button onclick="fetchKanban()" class="px-3 py-1.5 rounded-lg glass text-xs text-slate-300 hover:text-white">
            Làm mới bảng
          </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4" id="kanbanColumns">
          <!-- TODO Column -->
          <div class="space-y-3">
            <div class="flex items-center justify-between text-xs font-semibold px-2 text-slate-400">
              <span>CHỜ XỬ LÝ (TODO)</span>
              <span id="cntTodo" class="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">0</span>
            </div>
            <div id="colTodo" class="space-y-2 min-h-[300px] p-2 bg-slate-900/30 rounded-xl border border-slate-800/60"></div>
          </div>

          <!-- DOING Column -->
          <div class="space-y-3">
            <div class="flex items-center justify-between text-xs font-semibold px-2 text-amber-400">
              <span>ĐANG CHẠY (DOING)</span>
              <span id="cntDoing" class="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">0</span>
            </div>
            <div id="colDoing" class="space-y-2 min-h-[300px] p-2 bg-slate-900/30 rounded-xl border border-slate-800/60"></div>
          </div>

          <!-- DONE Column -->
          <div class="space-y-3">
            <div class="flex items-center justify-between text-xs font-semibold px-2 text-emerald-400">
              <span>HOÀN TẤT (DONE)</span>
              <span id="cntDone" class="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">0</span>
            </div>
            <div id="colDone" class="space-y-2 min-h-[300px] p-2 bg-slate-900/30 rounded-xl border border-slate-800/60"></div>
          </div>
        </div>
      </section>

      <!-- ================= TAB 4: SECOND BRAIN ================= -->
      <section id="tab-memory" class="space-y-6 hidden">
        <div class="glass p-5 rounded-2xl flex items-center justify-between">
          <div>
            <h2 class="font-bold text-lg text-white">Second Brain Vault (Trí Nhớ Dài Hạn)</h2>
            <p class="text-xs text-slate-400">Xem và trực tiếp tinh chỉnh hồ sơ cá nhân, thói quen và bài học đúc kết của Tokudo.</p>
          </div>
          <button onclick="saveCurrentMemoryFile()" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs flex items-center space-x-2 transition">
            <i data-lucide="save" class="w-4 h-4"></i>
            <span>Lưu Nội Dung</span>
          </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div class="glass p-3 rounded-xl space-y-1" id="memoryFileList">
            <!-- Memory files buttons -->
          </div>
          <div class="md:col-span-3 glass p-4 rounded-xl space-y-2">
            <div class="flex items-center justify-between text-xs text-slate-400 font-mono pb-2 border-b border-slate-800">
              <span id="currentMemoryFileName">user_profile.md</span>
              <span class="text-[10px] text-slate-500">Định dạng Markdown</span>
            </div>
            <textarea id="memoryEditor" rows="18" class="w-full bg-slate-950/70 border border-slate-800 rounded-lg p-3 font-mono text-xs text-slate-200 focus:outline-none focus:border-indigo-500"></textarea>
          </div>
        </div>
      </section>

    </main>
  </div>

  <!-- Modal: Add / Edit Account -->
  <div id="accountModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
    <div class="glass max-w-lg w-full rounded-2xl p-6 space-y-5 border border-slate-700 shadow-2xl">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 id="modalTitle" class="font-bold text-base text-white">Chỉnh Sửa Tài Khoản AI</h3>
        <button onclick="closeAccountModal()" class="text-slate-400 hover:text-white"><i data-lucide="x" class="w-5 h-5"></i></button>
      </div>

      <div class="space-y-4 text-xs">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-slate-400 font-medium mb-1">Mã Định Danh (ID)</label>
            <input type="text" id="modalAccId" placeholder="vd: gemini_pro_1" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-white font-mono focus:border-indigo-500 focus:outline-none">
          </div>
          <div>
            <label class="block text-slate-400 font-medium mb-1">Tên Hiển Thị</label>
            <input type="text" id="modalAccName" placeholder="vd: Gemini 1.5 Pro (Acc 1)" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-white focus:border-indigo-500 focus:outline-none">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-slate-400 font-medium mb-1">Nhà Cung Cấp (Provider)</label>
            <select id="modalAccProvider" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-white focus:border-indigo-500 focus:outline-none">
              <option value="gemini">Google Gemini</option>
              <option value="openai">OpenAI (ChatGPT)</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="deepseek">DeepSeek</option>
              <option value="ollama">Local Ollama (0đ)</option>
            </select>
          </div>
          <div>
            <label class="block text-slate-400 font-medium mb-1">Tên Model</label>
            <input type="text" id="modalAccModel" placeholder="vd: gemini-1.5-pro, gpt-4o" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-white font-mono focus:border-indigo-500 focus:outline-none">
          </div>
        </div>

        <div>
          <label class="block text-slate-400 font-medium mb-1">API Key</label>
          <div class="relative">
            <input type="password" id="modalAccKey" placeholder="sk-... hoặc AIzaSy... (hoặc ${ENV_VAR})" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-white font-mono pr-10 focus:border-indigo-500 focus:outline-none">
            <button type="button" onclick="toggleKeyVisibility()" class="absolute right-2.5 top-2.5 text-slate-500 hover:text-slate-300">
              <i data-lucide="eye" class="w-4 h-4"></i>
            </button>
          </div>
        </div>

        <div>
          <label class="block text-slate-400 font-medium mb-1">Base URL (Tùy chọn, cho Ollama / Proxy / DeepSeek)</label>
          <input type="text" id="modalAccBaseUrl" placeholder="http://localhost:11434/v1" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-white font-mono focus:border-indigo-500 focus:outline-none">
        </div>

        <div class="grid grid-cols-3 gap-3">
          <div>
            <label class="block text-slate-400 font-medium mb-1">Phân Hạng (Tier)</label>
            <select id="modalAccTier" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white">
              <option value="pro">PRO</option>
              <option value="free">FREE</option>
            </select>
          </div>
          <div>
            <label class="block text-slate-400 font-medium mb-1">Độ Ưu Tiên (1-10)</label>
            <input type="number" id="modalAccPriority" min="1" max="10" value="5" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white">
          </div>
          <div class="flex items-center pt-5">
            <label class="flex items-center space-x-2 text-slate-300 cursor-pointer">
              <input type="checkbox" id="modalAccEnabled" checked class="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0">
              <span>Kích hoạt</span>
            </label>
          </div>
        </div>
      </div>

      <div class="flex items-center justify-end space-x-3 border-t border-slate-800 pt-3">
        <button onclick="closeAccountModal()" class="px-4 py-2 rounded-xl glass text-xs font-medium text-slate-300 hover:text-white">Hủy</button>
        <button onclick="saveAccount()" class="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium shadow-lg shadow-indigo-600/30">Lưu Tài Khoản</button>
      </div>
    </div>
  </div>

  <script>
    let currentData = { accounts: [], active_account_id: "", auto_failover: true, stats: {} };
    let memoryFiles = [];
    let selectedMemoryFile = "";

    async function fetchAllData() {
      try {
        const [ovRes, brRes] = await Promise.all([
          fetch('/api/overview').then(r => r.json()),
          fetch('/api/brains').then(r => r.json()),
        ]);

        // Overview & Top bar
        document.getElementById('machineIdBadge').textContent = ovRes.machine_id || "PC-LOCAL";
        document.getElementById('topCpu').textContent = (ovRes.metrics.cpu_percent || 0) + '%';
        document.getElementById('topRam').textContent = (ovRes.metrics.ram_percent || 0) + '%';
        document.getElementById('topTokens').textContent = (ovRes.total_tokens_today || 0).toLocaleString();
        document.getElementById('topActiveBrain').textContent = ovRes.active_brain_name || "N/A";

        // Hardware Tab
        document.getElementById('sysCpuVal').textContent = (ovRes.metrics.cpu_percent || 0) + '%';
        document.getElementById('sysCpuBar').style.width = (ovRes.metrics.cpu_percent || 0) + '%';
        document.getElementById('sysRamVal').textContent = (ovRes.metrics.ram_percent || 0) + '%';
        document.getElementById('sysRamBar').style.width = (ovRes.metrics.ram_percent || 0) + '%';
        document.getElementById('sysRamDetail').textContent = `${ovRes.metrics.ram_used_gb} GB / ${ovRes.metrics.ram_total_gb} GB`;
        document.getElementById('sysDiskVal').textContent = (ovRes.metrics.disk_percent || 0) + '%';
        document.getElementById('sysDiskBar').style.width = (ovRes.metrics.disk_percent || 0) + '%';
        document.getElementById('sysDiskDetail').textContent = `${ovRes.metrics.disk_used_gb} GB / ${ovRes.metrics.disk_total_gb} GB`;

        // Bot Connectivity
        const tgPill = document.getElementById('statusTelegram');
        tgPill.className = 'w-2 h-2 rounded-full ' + (ovRes.telegram_active ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600');
        const dcPill = document.getElementById('statusDiscord');
        dcPill.className = 'w-2 h-2 rounded-full ' + (ovRes.discord_active ? 'bg-indigo-400 animate-pulse' : 'bg-slate-600');

        // Brains tab
        currentData = brRes;
        document.getElementById('accountCountBadge').textContent = `${brRes.accounts.length} tài khoản`;
        document.getElementById('failoverToggle').checked = brRes.auto_failover;
        renderAccounts(brRes);

      } catch (err) {
        console.error("Fetch error:", err);
      }
      lucide.createIcons();
    }

    function renderAccounts(data) {
      const grid = document.getElementById('accountsGrid');
      grid.innerHTML = '';

      data.accounts.forEach(acc => {
        const isActive = (acc.id === data.active_account_id);
        const stat = data.usage_today[acc.id] || { requests: 0, total_tokens: 0, errors: 0 };
        
        let statusBadge = '';
        if (!acc.enabled) {
          statusBadge = '<span class="text-[10px] px-2 py-0.5 rounded-full badge-disabled font-medium">Đã tắt</span>';
        } else if (acc.is_cooling_down) {
          statusBadge = `<span class="text-[10px] px-2 py-0.5 rounded-full badge-cooldown font-medium">Nghỉ (${acc.remaining_cooldown_seconds}s)</span>`;
        } else if (isActive) {
          statusBadge = '<span class="text-[10px] px-2 py-0.5 rounded-full badge-active font-medium font-mono">🌟 Đang dùng</span>';
        } else {
          statusBadge = '<span class="text-[10px] px-2 py-0.5 rounded-full badge-standby font-medium">Sẵn sàng</span>';
        }

        const providerColors = {
          openai: "text-emerald-400",
          gemini: "text-cyan-400",
          anthropic: "text-amber-400",
          deepseek: "text-blue-400",
          ollama: "text-purple-400"
        };
        const pColor = providerColors[acc.provider] || "text-slate-300";

        const card = document.createElement('div');
        card.className = `glass-card p-4 rounded-xl flex flex-col justify-between space-y-4 ${isActive ? 'ring-2 ring-indigo-500/60 bg-indigo-950/20' : ''}`;
        card.innerHTML = `
          <div class="space-y-2.5">
            <div class="flex items-start justify-between">
              <div>
                <span class="text-[10px] font-bold uppercase tracking-wider ${pColor}">${acc.provider}</span>
                <h4 class="font-bold text-sm text-white">${acc.name}</h4>
                <p class="text-[11px] font-mono text-slate-400 truncate max-w-[200px]">${acc.model}</p>
              </div>
              ${statusBadge}
            </div>

            <!-- Stats Bar -->
            <div class="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 text-[11px] font-mono grid grid-cols-2 gap-2 text-slate-300">
              <div>
                <span class="text-slate-500">Gọi hôm nay:</span>
                <span class="font-bold text-white ml-1">${stat.requests}</span>
              </div>
              <div>
                <span class="text-slate-500">Tokens:</span>
                <span class="font-bold text-indigo-400 ml-1">${(stat.total_tokens || 0).toLocaleString()}</span>
              </div>
              <div>
                <span class="text-slate-500">Tier / Pri:</span>
                <span class="text-slate-300 uppercase">${acc.tier} (P:${acc.priority})</span>
              </div>
              <div>
                <span class="text-slate-500">Lỗi:</span>
                <span class="${stat.errors > 0 ? 'text-amber-400' : 'text-slate-400'} ml-1">${stat.errors}</span>
              </div>
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
            <div class="flex items-center space-x-1">
              ${!isActive && acc.enabled ? `
                <button onclick="switchBrain('${acc.id}')" class="px-2.5 py-1 rounded-lg bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white font-medium text-[11px] transition">
                  Kích hoạt
                </button>
              ` : ''}
              <button onclick="testBrain('${acc.id}')" id="testBtn-${acc.id}" class="px-2 py-1 rounded-lg glass text-[11px] text-slate-400 hover:text-white">
                Ping
              </button>
            </div>

            <div class="flex items-center space-x-1 text-slate-400">
              <button onclick="editAccount('${acc.id}')" class="p-1 hover:text-indigo-400 transition" title="Sửa"><i data-lucide="edit-3" class="w-3.5 h-3.5"></i></button>
              <button onclick="deleteAccount('${acc.id}')" class="p-1 hover:text-rose-400 transition" title="Xóa"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
            </div>
          </div>
        `;
        grid.appendChild(card);
      });
      lucide.createIcons();
    }

    async function switchBrain(accId) {
      const res = await fetch('/api/brains/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accId })
      }).then(r => r.json());
      if (res.success) {
        fetchAllData();
      } else {
        alert(res.message);
      }
    }

    async function testBrain(accId) {
      const btn = document.getElementById(`testBtn-${accId}`);
      btn.textContent = '...';
      const res = await fetch('/api/brains/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accId })
      }).then(r => r.json());
      if (res.success) {
        btn.textContent = `${res.latency_ms}ms ✅`;
        btn.className = "px-2 py-1 rounded-lg bg-emerald-500/20 text-emerald-300 text-[11px]";
      } else {
        btn.textContent = `Lỗi ❌`;
        btn.className = "px-2 py-1 rounded-lg bg-rose-500/20 text-rose-300 text-[11px]";
        alert(`Kiểm tra API Key thất bại:\n${res.error}`);
      }
    }

    async function toggleFailover() {
      const enabled = document.getElementById('failoverToggle').checked;
      await fetch('/api/brains/toggle_failover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_failover: enabled })
      });
    }

    // Modal Operations
    function openAccountModal(acc = null) {
      document.getElementById('modalTitle').textContent = acc ? 'Chỉnh Sửa Tài Khoản AI' : 'Thêm Tài Khoản AI Mới';
      document.getElementById('modalAccId').value = acc ? acc.id : 'acc_' + Math.floor(Math.random() * 1000);
      document.getElementById('modalAccId').disabled = !!acc;
      document.getElementById('modalAccName').value = acc ? acc.name : '';
      document.getElementById('modalAccProvider').value = acc ? acc.provider : 'gemini';
      document.getElementById('modalAccModel').value = acc ? acc.model : 'gemini-1.5-pro';
      document.getElementById('modalAccKey').value = acc ? acc.api_key : '';
      document.getElementById('modalAccBaseUrl').value = acc ? (acc.base_url || '') : '';
      document.getElementById('modalAccTier').value = acc ? acc.tier : 'pro';
      document.getElementById('modalAccPriority').value = acc ? acc.priority : 5;
      document.getElementById('modalAccEnabled').checked = acc ? acc.enabled : true;

      document.getElementById('accountModal').classList.remove('hidden');
      lucide.createIcons();
    }

    function closeAccountModal() {
      document.getElementById('accountModal').classList.add('hidden');
    }

    function editAccount(accId) {
      const acc = currentData.accounts.find(a => a.id === accId);
      if (acc) openAccountModal(acc);
    }

    async function saveAccount() {
      const payload = {
        id: document.getElementById('modalAccId').value.trim(),
        name: document.getElementById('modalAccName').value.trim(),
        provider: document.getElementById('modalAccProvider').value,
        model: document.getElementById('modalAccModel').value.trim(),
        api_key: document.getElementById('modalAccKey').value.trim(),
        base_url: document.getElementById('modalAccBaseUrl').value.trim() || null,
        tier: document.getElementById('modalAccTier').value,
        priority: parseInt(document.getElementById('modalAccPriority').value) || 5,
        enabled: document.getElementById('modalAccEnabled').checked,
      };

      if (!payload.id || !payload.name || !payload.model) {
        alert("Vui lòng điền đầy đủ ID, Tên và Tên Model!");
        return;
      }

      const res = await fetch('/api/brains/save_account', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).then(r => r.json());

      if (res.success) {
        closeAccountModal();
        fetchAllData();
      } else {
        alert(res.message);
      }
    }

    async function deleteAccount(accId) {
      if (!confirm(`Bạn có chắc muốn xóa tài khoản '${accId}' khỏi hạm đội?`)) return;
      await fetch('/api/brains/delete_account', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accId })
      });
      fetchAllData();
    }

    function toggleKeyVisibility() {
      const f = document.getElementById('modalAccKey');
      f.type = f.type === 'password' ? 'text' : 'password';
    }

    // Screenshot Trigger
    async function triggerScreenshot() {
      const c = document.getElementById('screenshotContainer');
      c.innerHTML = '<span class="text-indigo-400 animate-pulse">Đang chụp màn hình Windows...</span>';
      const res = await fetch('/api/screenshot', { method: 'POST' }).then(r => r.json());
      if (res.success && res.image_url) {
        c.innerHTML = `<img src="${res.image_url}?t=${Date.now()}" class="max-h-[480px] w-auto rounded-lg shadow-lg border border-slate-700">`;
      } else {
        c.textContent = "Không thể chụp màn hình: " + (res.error || "Lỗi");
      }
    }

    // Kanban Fetching
    async function fetchKanban() {
      const res = await fetch('/api/kanban').then(r => r.json());
      const cTodo = document.getElementById('colTodo');
      const cDoing = document.getElementById('colDoing');
      const cDone = document.getElementById('colDone');
      cTodo.innerHTML = ''; cDoing.innerHTML = ''; cDone.innerHTML = '';

      let cntT = 0, cntDg = 0, cntDn = 0;
      res.tasks.forEach(t => {
        const item = document.createElement('div');
        item.className = "p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs space-y-1.5";
        item.innerHTML = `
          <div class="flex items-center justify-between">
            <span class="font-mono text-[10px] text-slate-500">#${t.id}</span>
            <span class="text-[10px] text-slate-400 font-mono">${t.created_at.substring(11, 16)}</span>
          </div>
          <p class="font-medium text-white">${t.title}</p>
          ${t.result_text ? `<p class="text-[11px] text-slate-400 truncate">${t.result_text}</p>` : ''}
        `;
        if (t.status === 'TODO') { cTodo.appendChild(item); cntT++; }
        else if (t.status === 'DOING') { cDoing.appendChild(item); cntDg++; }
        else { cDone.appendChild(item); cntDn++; }
      });

      document.getElementById('cntTodo').textContent = cntT;
      document.getElementById('cntDoing').textContent = cntDg;
      document.getElementById('cntDone').textContent = cntDn;
    }

    // Second Brain Memory
    async function fetchMemoryFiles() {
      const res = await fetch('/api/memory').then(r => r.json());
      memoryFiles = res.files;
      const listEl = document.getElementById('memoryFileList');
      listEl.innerHTML = '';

      memoryFiles.forEach((file, idx) => {
        const btn = document.createElement('button');
        btn.className = `w-full text-left px-3 py-2 rounded-lg text-xs font-mono truncate transition ${idx === 0 ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30' : 'text-slate-400 hover:bg-slate-800'}`;
        btn.textContent = file.name;
        btn.onclick = () => loadMemoryContent(file.name);
        listEl.appendChild(btn);
      });

      if (memoryFiles.length > 0) {
        loadMemoryContent(memoryFiles[0].name);
      }
    }

    function loadMemoryContent(filename) {
      selectedMemoryFile = filename;
      document.getElementById('currentMemoryFileName').textContent = filename;
      const target = memoryFiles.find(f => f.name === filename);
      document.getElementById('memoryEditor').value = target ? target.content : '';
    }

    async function saveCurrentMemoryFile() {
      if (!selectedMemoryFile) return;
      const content = document.getElementById('memoryEditor').value;
      const res = await fetch('/api/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: selectedMemoryFile, content: content })
      }).then(r => r.json());
      if (res.success) {
        alert(`Đã lưu tệp ${selectedMemoryFile} thành công!`);
        fetchMemoryFiles();
      }
    }

    // Tab Switching
    function switchTab(tabId) {
      ['brains', 'system', 'kanban', 'memory'].forEach(t => {
        document.getElementById(`tab-${t}`).classList.add('hidden');
        const b = document.getElementById(`tabBtn-${t}`);
        b.className = "w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition";
      });

      document.getElementById(`tab-${tabId}`).classList.remove('hidden');
      const activeBtn = document.getElementById(`tabBtn-${tabId}`);
      activeBtn.className = "w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30";

      if (tabId === 'kanban') fetchKanban();
      if (tabId === 'memory') fetchMemoryFiles();
    }

    // Startup
    fetchAllData();
    setInterval(fetchAllData, 5000); // Poll metrics every 5s
  </script>
</body>
</html>
"""


class DashboardServer:
    """
    Embedded Async Web Dashboard server for Tokudo running on localhost.
    Provides complete GUI for AI Account Management, System Monitoring,
    Kanban Board, and Second Brain Memory.
    """

    def __init__(self, engine_ref, host: str = "127.0.0.1", port: int = 8080):
        self.engine = engine_ref
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/api/overview", self.handle_overview)
        self.app.router.add_get("/api/brains", self.handle_get_brains)
        self.app.router.add_post("/api/brains/switch", self.handle_switch_brain)
        self.app.router.add_post("/api/brains/save_account", self.handle_save_account)
        self.app.router.add_post("/api/brains/delete_account", self.handle_delete_account)
        self.app.router.add_post("/api/brains/toggle_failover", self.handle_toggle_failover)
        self.app.router.add_post("/api/brains/test", self.handle_test_brain)
        self.app.router.add_post("/api/screenshot", self.handle_screenshot)
        self.app.router.add_get("/api/screenshot/latest", self.handle_latest_screenshot_file)
        self.app.router.add_get("/api/kanban", self.handle_get_kanban)
        self.app.router.add_get("/api/memory", self.handle_get_memory)
        self.app.router.add_post("/api/memory", self.handle_save_memory)

    async def start(self) -> None:
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        logger.info(f"🚀 Tokudo Visual Dashboard online at: http://{self.host}:{self.port}")

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()
            logger.info("Tokudo Visual Dashboard server stopped.")

    # Route Handlers
    async def handle_index(self, request: web.Request) -> web.Response:
        return web.Response(text=HTML_DASHBOARD, content_type="text/html")

    async def handle_overview(self, request: web.Request) -> web.Response:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        root_path = os.path.abspath(os.sep)
        try:
            disk = psutil.disk_usage(root_path)
        except Exception:
            disk = psutil.disk_usage(".")

        stats = self.engine.brain_router.tracker.get_stats_for_today()
        total_tokens = sum(s.get("total_tokens", 0) for s in stats.values())
        active_brain = self.engine.brain_router.get_active_brain()

        tg_adapter = self.engine.adapters.get(PlatformType.TELEGRAM)
        dc_adapter = self.engine.adapters.get(PlatformType.DISCORD)

        data = {
            "machine_id": self.engine.machine_id,
            "metrics": {
                "cpu_percent": cpu,
                "ram_percent": ram.percent,
                "ram_used_gb": round(ram.used / (1024**3), 1),
                "ram_total_gb": round(ram.total / (1024**3), 1),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024**3), 1),
                "disk_total_gb": round(disk.total / (1024**3), 1),
            },
            "active_brain_id": active_brain.id if active_brain else None,
            "active_brain_name": active_brain.name if active_brain else "None",
            "total_tokens_today": total_tokens,
            "telegram_active": bool(tg_adapter and tg_adapter.app),
            "discord_active": bool(dc_adapter and not dc_adapter.bot.is_closed()),
        }
        return web.json_response(data)

    async def handle_get_brains(self, request: web.Request) -> web.Response:
        router = self.engine.brain_router
        accounts_list = []
        for acc in router.accounts.values():
            acc_dict = acc.model_dump()
            acc_dict["is_cooling_down"] = acc.is_cooling_down
            acc_dict["remaining_cooldown_seconds"] = acc.remaining_cooldown_seconds
            # Mask sensitive API Key for display
            key = acc.api_key
            if key and len(key) > 8 and not key.startswith("${"):
                acc_dict["api_key_masked"] = key[:4] + "..." + key[-4:]
            else:
                acc_dict["api_key_masked"] = key
            accounts_list.append(acc_dict)

        data = {
            "active_account_id": router.active_account_id,
            "auto_failover": router.auto_failover,
            "accounts": accounts_list,
            "usage_today": router.tracker.get_stats_for_today(),
        }
        return web.json_response(data)

    async def handle_switch_brain(self, request: web.Request) -> web.Response:
        body = await request.json()
        acc_id = body.get("account_id")
        success, msg = self.engine.brain_router.set_active_brain(acc_id)
        return web.json_response({"success": success, "message": msg})

    async def handle_save_account(self, request: web.Request) -> web.Response:
        body = await request.json()
        acc_id = body.get("id")
        if not acc_id:
            return web.json_response({"success": False, "message": "Missing account id"}, status=400)

        # Update in-memory account
        router = self.engine.brain_router
        existing = router.accounts.get(acc_id)
        if existing and not body.get("api_key"):
            body["api_key"] = existing.api_key  # Preserve key if not re-typed

        new_acc = BrainAccount(**body)
        router.accounts[acc_id] = new_acc
        router.save_config()
        logger.info(f"Dashboard saved account '{acc_id}' ({new_acc.name})")
        return web.json_response({"success": True, "message": f"Đã lưu tài khoản {new_acc.name}"})

    async def handle_delete_account(self, request: web.Request) -> web.Response:
        body = await request.json()
        acc_id = body.get("account_id")
        router = self.engine.brain_router
        if acc_id in router.accounts:
            del router.accounts[acc_id]
            router.save_config()
            return web.json_response({"success": True, "message": "Deleted account"})
        return web.json_response({"success": False, "message": "Not found"}, status=404)

    async def handle_toggle_failover(self, request: web.Request) -> web.Response:
        body = await request.json()
        enabled = body.get("auto_failover", True)
        self.engine.brain_router.auto_failover = bool(enabled)
        self.engine.brain_router.save_config()
        return web.json_response({"success": True, "auto_failover": self.engine.brain_router.auto_failover})

    async def handle_test_brain(self, request: web.Request) -> web.Response:
        body = await request.json()
        acc_id = body.get("account_id")
        router = self.engine.brain_router
        acc = router.accounts.get(acc_id)
        if not acc:
            return web.json_response({"success": False, "error": "Account not found"}, status=404)

        t_start = time.time()
        try:
            # Minimal prompt test
            await router._call_provider(
                acc,
                system_prompt="Reply with 'OK'.",
                user_message="Ping",
                history=None,
                tools=None,
                temperature=0.0,
            )
            latency = int((time.time() - t_start) * 1000)
            return web.json_response({"success": True, "latency_ms": latency})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)})

    async def handle_screenshot(self, request: web.Request) -> web.Response:
        skill = self.engine.skill_registry.get_skill("capture_screenshot")
        if not skill:
            return web.json_response({"success": False, "error": "Skill capture_screenshot not found"})
        res = await skill.execute()
        return web.json_response({"success": True, "image_url": "/api/screenshot/latest"})

    async def handle_latest_screenshot_file(self, request: web.Request) -> web.Response:
        scr_dir = Path("data/screenshots")
        files = sorted(scr_dir.glob("screenshot_*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return web.Response(text="No screenshot available", status=404)
        return web.FileResponse(files[0])

    async def handle_get_kanban(self, request: web.Request) -> web.Response:
        with self.engine.kanban._get_connection() as conn:
            rows = conn.execute("SELECT * FROM kanban_tasks ORDER BY created_at DESC LIMIT 30").fetchall()
            tasks = [dict(r) for r in rows]
        return web.json_response({"tasks": tasks})

    async def handle_get_memory(self, request: web.Request) -> web.Response:
        mem_dir = self.engine.memory.memory_dir
        files = []
        for p in sorted(mem_dir.glob("*.md")):
            files.append({"name": p.name, "content": p.read_text(encoding="utf-8")})
        return web.json_response({"files": files})

    async def handle_save_memory(self, request: web.Request) -> web.Response:
        body = await request.json()
        filename = body.get("filename")
        content = body.get("content", "")
        if not filename or not filename.endswith(".md"):
            return web.json_response({"success": False, "message": "Invalid file"}, status=400)
        p = self.engine.memory.memory_dir / filename
        p.write_text(content, encoding="utf-8")
        return web.json_response({"success": True, "message": f"Saved {filename}"})
