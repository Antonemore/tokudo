"""
tokudo.core.brain_router
Multi-Brain Management & Routing Engine:
Supports multiple accounts per provider (3x ChatGPT, 3x Gemini Pro, 2x Gemini Free, 1x Claude, Ollama),
Dynamic Hot-Switching, Smart Auto-Failover on 429/Quota exhaustion, and Token Usage Telemetry.
"""

from __future__ import annotations
import os
import time
import json
import sqlite3
import logging
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

logger = logging.getLogger("tokudo.core.brain_router")


class BrainAccount(BaseModel):
    """Configuration for an individual AI brain account."""
    id: str
    name: str
    provider: str  # 'openai', 'gemini', 'anthropic', 'deepseek', 'ollama'
    model: str
    api_key: str = ""
    base_url: Optional[str] = None
    tier: str = "pro"  # 'free' or 'pro'
    priority: int = 10
    enabled: bool = True
    rpm_limit: Optional[int] = None
    tpd_limit: Optional[int] = None
    cooldown_until: Optional[float] = None  # epoch timestamp

    @property
    def is_cooling_down(self) -> bool:
        if self.cooldown_until and time.time() < self.cooldown_until:
            return True
        return False

    @property
    def remaining_cooldown_seconds(self) -> int:
        if self.cooldown_until:
            rem = int(self.cooldown_until - time.time())
            return max(0, rem)
        return 0


class BrainUsageTracker:
    """Tracks token consumption, request counts, and error rates in SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        base_db = Path(db_path or "data/brain_usage.db")
        self.db_path = base_db if base_db.is_absolute() else Path.cwd() / base_db
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_sqlite()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_usage (
                    account_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    requests_count INTEGER DEFAULT 0,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    last_used_at TEXT,
                    PRIMARY KEY (account_id, date)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def record_usage(
        self,
        account_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        status: str = "SUCCESS",
    ) -> None:
        total = prompt_tokens + completion_tokens
        today = datetime.now().strftime("%Y-%m-%d")
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO daily_usage (
                    account_id, date, requests_count, prompt_tokens,
                    completion_tokens, total_tokens, error_count, last_used_at
                ) VALUES (?, ?, 1, ?, ?, ?, 0, ?)
                ON CONFLICT(account_id, date) DO UPDATE SET
                    requests_count = requests_count + 1,
                    prompt_tokens = prompt_tokens + excluded.prompt_tokens,
                    completion_tokens = completion_tokens + excluded.completion_tokens,
                    total_tokens = total_tokens + excluded.total_tokens,
                    last_used_at = excluded.last_used_at
                """,
                (account_id, today, prompt_tokens, completion_tokens, total, now_iso),
            )
            conn.execute(
                """
                INSERT INTO usage_logs (account_id, model, prompt_tokens, completion_tokens, total_tokens, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (account_id, model, prompt_tokens, completion_tokens, total, status, now_iso),
            )
            conn.commit()

    def record_error(self, account_id: str, model: str, error_msg: str) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO daily_usage (
                    account_id, date, requests_count, prompt_tokens,
                    completion_tokens, total_tokens, error_count, last_used_at
                ) VALUES (?, ?, 1, 0, 0, 0, 1, ?)
                ON CONFLICT(account_id, date) DO UPDATE SET
                    requests_count = requests_count + 1,
                    error_count = error_count + 1,
                    last_used_at = excluded.last_used_at
                """,
                (account_id, today, now_iso),
            )
            conn.execute(
                """
                INSERT INTO usage_logs (account_id, model, prompt_tokens, completion_tokens, total_tokens, status, timestamp)
                VALUES (?, ?, 0, 0, 0, ?, ?)
                """,
                (account_id, model, f"ERROR: {error_msg[:100]}", now_iso),
            )
            conn.commit()

    def get_stats_for_today(self) -> Dict[str, Dict[str, Any]]:
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_usage WHERE date = ?", (today,)
            ).fetchall()
            return {
                r["account_id"]: {
                    "requests": r["requests_count"],
                    "prompt_tokens": r["prompt_tokens"],
                    "completion_tokens": r["completion_tokens"],
                    "total_tokens": r["total_tokens"],
                    "errors": r["error_count"],
                    "last_used": r["last_used_at"],
                }
                for r in rows
            }


class MultiBrainRouter:
    """
    Coordinates account pooling, real-time manual brain switching,
    auto-failover recovery, and comprehensive quota telemetry.
    """

    def __init__(self, config_path: str = "data/brains.json"):
        self.config_path = Path(config_path)
        self.tracker = BrainUsageTracker()
        self.accounts: Dict[str, BrainAccount] = {}
        self.active_account_id: str = "gemini_pro_1"
        self.auto_failover: bool = True
        self.reload_config()

    def reload_config(self) -> None:
        """Loads brain accounts from data/brains.json or creates a starter template."""
        if not self.config_path.exists():
            self._create_starter_template()

        try:
            raw_data = json.loads(self.config_path.read_text(encoding="utf-8"))
            self.auto_failover = raw_data.get("auto_failover", True)
            self.active_account_id = raw_data.get("active_account_id", "")

            loaded_accounts = {}
            for acc_data in raw_data.get("accounts", []):
                acc = BrainAccount(**acc_data)
                # Pull API key from environment if placeholder is used
                if acc.api_key.startswith("${") and acc.api_key.endswith("}"):
                    env_var = acc.api_key[2:-1]
                    acc.api_key = os.getenv(env_var, "")
                loaded_accounts[acc.id] = acc

            self.accounts = loaded_accounts

            # Ensure valid active account
            if self.active_account_id not in self.accounts and self.accounts:
                self.active_account_id = list(self.accounts.keys())[0]

            logger.info(
                f"MultiBrainRouter loaded {len(self.accounts)} accounts. Active brain: '{self.active_account_id}'"
            )
        except Exception as e:
            logger.error(f"Failed to load brains configuration: {e}", exc_info=True)

    def _create_starter_template(self) -> None:
        """Generates starter template customized for the user's multi-account fleet."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        starter = {
            "active_account_id": "gemini_pro_1",
            "auto_failover": True,
            "description": "Tokudo Multi-Brain Pool: 3x ChatGPT, 3x Gemini Pro, 2x Gemini Free, 1x Claude, 1x Ollama",
            "accounts": [
                {
                    "id": "gemini_free_1",
                    "name": "Gemini 1.5 Flash (Free Acc 1)",
                    "provider": "gemini",
                    "model": "gemini-1.5-flash",
                    "api_key": "${GEMINI_API_KEY}",
                    "tier": "free",
                    "priority": 10,
                    "enabled": True,
                    "rpm_limit": 15,
                    "tpd_limit": 1000000,
                },
                {
                    "id": "gemini_free_2",
                    "name": "Gemini 1.5 Flash (Free Acc 2)",
                    "provider": "gemini",
                    "model": "gemini-1.5-flash",
                    "api_key": "",
                    "tier": "free",
                    "priority": 9,
                    "enabled": False,
                    "rpm_limit": 15,
                    "tpd_limit": 1000000,
                },
                {
                    "id": "gemini_pro_1",
                    "name": "Gemini 1.5 Pro (Acc 1)",
                    "provider": "gemini",
                    "model": "gemini-1.5-pro",
                    "api_key": "${GEMINI_API_KEY}",
                    "tier": "pro",
                    "priority": 8,
                    "enabled": True,
                },
                {
                    "id": "gemini_pro_2",
                    "name": "Gemini 1.5 Pro (Acc 2)",
                    "provider": "gemini",
                    "model": "gemini-1.5-pro",
                    "api_key": "",
                    "tier": "pro",
                    "priority": 7,
                    "enabled": False,
                },
                {
                    "id": "gemini_pro_3",
                    "name": "Gemini 1.5 Pro (Acc 3)",
                    "provider": "gemini",
                    "model": "gemini-1.5-pro",
                    "api_key": "",
                    "tier": "pro",
                    "priority": 6,
                    "enabled": False,
                },
                {
                    "id": "chatgpt_pro_1",
                    "name": "ChatGPT GPT-4o (Acc 1)",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key": "${OPENAI_API_KEY}",
                    "tier": "pro",
                    "priority": 5,
                    "enabled": True,
                },
                {
                    "id": "chatgpt_pro_2",
                    "name": "ChatGPT GPT-4o (Acc 2)",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key": "",
                    "tier": "pro",
                    "priority": 4,
                    "enabled": False,
                },
                {
                    "id": "chatgpt_pro_3",
                    "name": "ChatGPT GPT-4o-mini (Acc 3)",
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "",
                    "tier": "pro",
                    "priority": 3,
                    "enabled": False,
                },
                {
                    "id": "claude_sonnet",
                    "name": "Claude 3.5 Sonnet",
                    "provider": "anthropic",
                    "model": "claude-3-5-sonnet-20241022",
                    "api_key": "${ANTHROPIC_API_KEY}",
                    "tier": "pro",
                    "priority": 2,
                    "enabled": False,
                },
                {
                    "id": "local_ollama",
                    "name": "Local Ollama Llama3 (0đ)",
                    "provider": "ollama",
                    "model": "llama3",
                    "base_url": "http://localhost:11434/v1",
                    "tier": "free",
                    "priority": 1,
                    "enabled": False,
                },
            ],
        }
        self.config_path.write_text(json.dumps(starter, indent=2, ensure_ascii=False), encoding="utf-8")

    def save_config(self) -> None:
        """Persists changes back to data/brains.json."""
        data = {
            "active_account_id": self.active_account_id,
            "auto_failover": self.auto_failover,
            "accounts": [acc.model_dump() for acc in self.accounts.values()],
        }
        self.config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_active_brain(self) -> Optional[BrainAccount]:
        return self.accounts.get(self.active_account_id)

    def set_active_brain(self, account_id: str) -> Tuple[bool, str]:
        """Manually switches the active brain."""
        if account_id not in self.accounts:
            return False, f"Không tìm thấy tài khoản bộ não `{account_id}`."
        acc = self.accounts[account_id]
        if not acc.enabled:
            return False, f"Tài khoản `{acc.name}` hiện đang bị tắt (enabled=false)."
        self.active_account_id = account_id
        self.save_config()
        return True, f"🧠 Đã chuyển đổi bộ não hoạt động chính sang: **{acc.name}** (`{acc.model}`)"

    def trigger_cooldown(self, account_id: str, minutes: int = 5) -> None:
        """Puts an account into temporary cooldown (e.g. after receiving 429 Rate Limit)."""
        acc = self.accounts.get(account_id)
        if acc:
            acc.cooldown_until = time.time() + (minutes * 60)
            logger.warning(f"Brain account '{account_id}' entered cooldown for {minutes}m.")

    def get_failover_candidates(self) -> List[BrainAccount]:
        """Returns ordered list of enabled and available accounts ready for failover."""
        candidates = [
            acc for acc in self.accounts.values()
            if acc.enabled and not acc.is_cooling_down and (acc.api_key or acc.provider == "ollama")
        ]
        # Sort by priority descending
        candidates.sort(key=lambda a: a.priority, reverse=True)
        return candidates

    def get_dashboard(self) -> str:
        """Generates visual usage dashboard & account status report for Telegram/Discord."""
        stats = self.tracker.get_stats_for_today()
        today_str = datetime.now().strftime("%d/%m/%Y")

        lines = [
            f"🧠 **BẢNG ĐIỀU KHIỂN & ĐỊNH TUYẾN MULTI-BRAIN**",
            f"📅 Ngày thống kê: `{today_str}` | Auto-Failover: `{'BẬT' if self.auto_failover else 'TẮT'}`\n",
        ]

        active_id = self.active_account_id
        total_tokens_today = 0
        total_requests_today = 0

        for acc in self.accounts.values():
            is_active = (acc.id == active_id)
            active_badge = "🌟 [ĐANG CHẠY]" if is_active else ""

            if not acc.enabled:
                status_icon = "⚪ (Tắt)"
            elif acc.is_cooling_down:
                status_icon = f"❄️ (Nghỉ {acc.remaining_cooldown_seconds}s)"
            else:
                status_icon = "🟢 (Sẵn sàng)"

            acc_stat = stats.get(acc.id, {"requests": 0, "total_tokens": 0, "errors": 0})
            req_cnt = acc_stat["requests"]
            tokens = acc_stat["total_tokens"]
            err_cnt = acc_stat["errors"]
            total_tokens_today += tokens
            total_requests_today += req_cnt

            lines.append(
                f"• {status_icon} **{acc.name}** {active_badge}\n"
                f"  ID: `{acc.id}` | Model: `{acc.model}` | Tier: `{acc.tier.upper()}`\n"
                f"  📊 Hôm nay: `{req_cnt}` lượt gọi | `{tokens:,}` tokens | `{err_cnt}` lỗi"
            )

        lines.append(f"\n📈 **TỔNG LƯU LƯỢNG HỆ THỐNG:** `{total_requests_today}` lượt | `{total_tokens_today:,}` tokens")
        return "\n".join(lines)

    async def execute_chat(
        self,
        system_prompt: str,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
    ) -> Tuple[str, List[Dict[str, Any]], BrainAccount, Optional[str]]:
        """
        Executes chat completion with Multi-Brain Router.
        If current brain hits 429/quota error and auto_failover is enabled,
        it automatically switches to the next available account and retries seamlessly!
        """
        # Determine candidate queue
        active = self.get_active_brain()
        queue: List[BrainAccount] = []
        if active and active.enabled and not active.is_cooling_down and (active.api_key or active.provider == "ollama"):
            queue.append(active)

        if self.auto_failover:
            for cand in self.get_failover_candidates():
                if cand.id != (active.id if active else ""):
                    queue.append(cand)

        if not queue:
            raise RuntimeError("Không có tài khoản AI nào khả dụng trong Multi-Brain Pool. Vui lòng kiểm tra API Keys!")

        failover_notices = []

        for idx, brain in enumerate(queue):
            try:
                logger.info(f"Dispatching query to brain [{brain.id}] ({brain.name} - {brain.model})...")
                res_text, tool_calls, prompt_tokens, comp_tokens = await self._call_provider(
                    brain, system_prompt, user_message, history, tools, temperature
                )

                # Record success telemetry
                self.tracker.record_usage(brain.id, brain.model, prompt_tokens, comp_tokens, "SUCCESS")

                notice = None
                if failover_notices:
                    notice = "\n".join(failover_notices)

                return res_text, tool_calls, brain, notice

            except Exception as e:
                err_str = str(e).lower()
                is_quota_or_rate_limit = any(
                    term in err_str for term in ["429", "quota", "resource_exhausted", "rate limit", "overloaded"]
                )
                logger.error(f"Brain [{brain.id}] failed: {e}")

                # Record error telemetry
                self.tracker.record_error(brain.id, brain.model, str(e))

                if is_quota_or_rate_limit:
                    # Put into cooldown (5 mins for free tier RPM, 30 mins for others)
                    cd_mins = 5 if brain.tier == "free" else 30
                    self.trigger_cooldown(brain.id, minutes=cd_mins)
                    failover_notices.append(
                        f"⚠️ `{brain.name}` chạm hạn mức (429/Quota). Tự động chuyển giao sang não dự phòng..."
                    )
                else:
                    failover_notices.append(f"⚠️ `{brain.name}` gặp sự cố: {str(e)[:60]}...")

                # If this was the last candidate, re-raise error
                if idx == len(queue) - 1:
                    raise RuntimeError(f"Tất cả {len(queue)} tài khoản AI đều thất bại. Lỗi cuối: {str(e)}")

        raise RuntimeError("Hoàn tất duyệt pool nhưng không nhận được kết quả.")

    async def _call_provider(
        self,
        brain: BrainAccount,
        system_prompt: str,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
    ) -> Tuple[str, List[Dict[str, Any]], int, int]:
        """Routes execution to OpenAI, Gemini, Anthropic, or Ollama."""
        provider = brain.provider.lower()

        if provider in ("openai", "deepseek", "ollama"):
            return await self._call_openai_compatible(brain, system_prompt, user_message, history, tools, temperature)
        elif provider == "gemini":
            return await self._call_gemini(brain, system_prompt, user_message, history, tools, temperature)
        elif provider == "anthropic":
            return await self._call_anthropic(brain, system_prompt, user_message, history, tools, temperature)
        else:
            raise ValueError(f"Nhà cung cấp không hỗ trợ: {provider}")

    async def _call_openai_compatible(
        self,
        brain: BrainAccount,
        system_prompt: str,
        user_message: str,
        history: Optional[List[Dict[str, str]]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
    ) -> Tuple[str, List[Dict[str, Any]], int, int]:
        from openai import AsyncOpenAI
        base_url = brain.base_url or "https://api.openai.com/v1"
        client = AsyncOpenAI(api_key=brain.api_key or "dummy_key", base_url=base_url)

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        resp = await client.chat.completions.create(
            model=brain.model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=temperature,
        )

        choice = resp.choices[0]
        content = choice.message.content or ""
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments or "{}"),
                })

        usage = resp.usage
        prompt_tokens = usage.prompt_tokens if usage else len(system_prompt + user_message) // 4
        comp_tokens = usage.completion_tokens if usage else len(content) // 4
        return content, tool_calls, prompt_tokens, comp_tokens

    async def _call_gemini(
        self,
        brain: BrainAccount,
        system_prompt: str,
        user_message: str,
        history: Optional[List[Dict[str, str]]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
    ) -> Tuple[str, List[Dict[str, Any]], int, int]:
        import google.generativeai as genai
        genai.configure(api_key=brain.api_key)
        model = genai.GenerativeModel(
            model_name=brain.model,
            system_instruction=system_prompt,
        )

        full_prompt = user_message
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(temperature=temperature),
            ),
        )

        content = res.text if res else ""
        # Approximate tokens if exact count not returned
        prompt_tokens = len(system_prompt + user_message) // 4
        comp_tokens = len(content) // 4
        return content, [], prompt_tokens, comp_tokens

    async def _call_anthropic(
        self,
        brain: BrainAccount,
        system_prompt: str,
        user_message: str,
        history: Optional[List[Dict[str, str]]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
    ) -> Tuple[str, List[Dict[str, Any]], int, int]:
        """Native async call to Anthropic Claude Messages API."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": brain.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": brain.model,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": temperature,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
                if resp.status != 200:
                    err_txt = await resp.text()
                    raise RuntimeError(f"Anthropic HTTP {resp.status}: {err_txt}")
                data = await resp.json()

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", len(system_prompt + user_message) // 4)
        comp_tokens = usage.get("output_tokens", len(content) // 4)
        return content, [], prompt_tokens, comp_tokens
