# 🧠 Tokudo — Personal AI Agent & Second Brain on Windows

**Tokudo** là hệ thống Trợ lý AI cá nhân và Bộ não số (Second Brain) tối thượng chạy trực tiếp trên máy tính Windows cục bộ, có khả năng đồng bộ song song hai chiều trên cả **Telegram** và **Discord** từ một lõi điều phối duy nhất (`Single-Core Multi-Frontend`).

---

## 🏛️ Kiến Trúc Hệ Thống (Architecture Overview)

```
                 ┌────────────────────────────────────────────────────────┐
                 │           MULTI-FRONTEND CLIENTS (DI ĐỘNG & BÀN)       │
                 │   [📱 Telegram (Long-polling)]    [💬 Discord Gateway] │
                 └───────────┬────────────────────────────────┬───────────┘
                             │                                │
             (Normalize)     ▼                                ▼     (Normalize)
                      UnifiedMessage                   UnifiedMessage
                             │                                │
                 ┌───────────┴────────────────────────────────┴───────────┐
                 │          TOKUDO CORE ENGINE (LÕI XỬ LÝ DUY NHẤT)       │
                 │                                                        │
                 │  • Node Tag: [MACHINE_ID]  (Định danh PC, chống xung đột)│
                 │  • Whitelist Filter: Silent drop unauthorized users   │
                 │  • Security HITL: Phê duyệt bất đồng bộ lệnh nhạy cảm  │
                 │  • LLM Reasoning: OpenAI / Gemini Function Calling     │
                 └──────┬─────────────┬──────────────┬─────────────┬──────┘
                        │             │              │             │
        ┌───────────────┘             │              │             └───────────────┐
        ▼                             ▼              ▼                             ▼
┌──────────────┐             ┌─────────────────┐ ┌────────────────┐       ┌─────────────────┐
│ SECOND BRAIN │             │ EXTENSIBLE SKILL│ │ KANBAN WORKER  │       │ TASK SCHEDULER  │
│              │             │                 │ │                │       │                 │
│ • memory/    │             │ • os_controller │ │ • Async Queue  │       │ • APScheduler   │
│   Auto-Reflect             │ • code_architect│ │ • SQLite TODO/ │       │ • Cron / Dates  │
│ • wiki/      │             │ • multimodal    │ │   DOING / DONE │       │ • Reminders &   │
│   SQLite FTS5│             │ • skill_builder │ │ • Auto Notify  │       │   Alerts        │
└──────────────┘             └─────────────────┘ └────────────────┘       └─────────────────┘
```

---

## ✨ Điểm Nhấn Công Nghệ

1. **Giao Diện Web Trực Quan (Web OS Dashboard - `http://localhost:8080`):**
   - Tương đương và tối ưu hơn Javis OS: Quản lý trực quan toàn bộ hạm đội tài khoản AI bằng giao diện web Dark Mode mượt mà.
   - Thao tác 1 chạm: **Thêm mới, Chỉnh sửa, Lưu, Xóa, Bật/Tắt, Ping kiểm tra API key, và Đổi não chính (Hot-Switch)** ngay trên giao diện mà không cần chỉnh sửa code hay restart bot.
   - Theo dõi phần cứng thời gian thực (CPU %, RAM %, Ổ đĩa C %), xem bảng Kanban tác vụ ngầm, và trực tiếp chỉnh sửa các tệp trí nhớ Second Brain Markdown (`user_profile.md`, `preferences.md`).

2. **Hạm Đội Đa Bộ Não & Tự Động Cứu Hộ (Multi-Brain Router & Smart Failover):**
   - Quản trị nhiều tài khoản AI trong cùng một hệ thống (vd: 3x ChatGPT, 3x Gemini Pro, 2x Gemini Free, 1x Claude, 1x Local Ollama).
   - Tự động thống kê lưu lượng sử dụng token (Prompt, Completion, Total Tokens) theo ngày vào SQLite `data/brain_usage.db`.
   - **Smart Cooldown & Failover:** Khi tài khoản đang chạy bị dính lỗi `429 Too Many Requests` hoặc hết Quota, hệ thống tự động đưa tài khoản đó vào chế độ ngủ đông (Cooldown) và kích hoạt liền mạch tài khoản AI kế tiếp mà không làm gián đoạn phiên chat!

3. **Single-Core Multi-Frontend:**
   - Chuẩn hóa mọi tin nhắn (Text, Photo, Voice, File) thành schema `UnifiedMessage`.
   - Adapters tự động tối ưu định dạng cho từng nền tảng: Markdown & Inline Keyboard (Telegram), Embeds & Buttons (Discord).
   - Tự động chia nhỏ tin nhắn khi vượt quá độ dài tối đa (4000 ký tự cho Telegram, 2000 ký tự cho Discord).
   - Hỗ trợ triển khai trên nhiều máy trạm cùng lúc với tiền tố `[MACHINE_ID]` (vd: `[PC-STUDIO]`, `[WORKSTATION-01]`).

2. **Bảo Mật Nghiêm Ngặt & Human-in-the-Loop (HITL):**
   - **Whitelist:** Chỉ chấp nhận request từ `TELEGRAM_ALLOWED_USER_ID` và `DISCORD_ALLOWED_USER_ID`. Toàn bộ request từ người lạ bị drop im lặng.
   - **Xác thực 2 bước (HITL):** Mọi lệnh can thiệp OS, chạy lệnh Terminal PowerShell, đóng ứng dụng hoặc tạo mã nguồn mới đều gửi kèm nút bấm `[✅ Chấp thuận]` và `[❌ Từ chối]` về điện thoại và chờ xác nhận bất đồng bộ.

3. **Second Brain & Tự Học Hỏi (Self-Evolving Memory):**
   - Lưu trữ dài hạn tại `brain/memory/` (`user_profile.md`, `preferences.md`, `lessons_learned.md`).
   - **Auto-Reflection:** Cơ chế tự động đánh giá sau hội thoại để chưng cất thói quen, quy chuẩn code hoặc bài học mới.
   - **Wiki Distillation & SQLite FTS5:** Đọc tài liệu thô, tổng hợp thành tài liệu chuẩn tại `brain/wiki/` và đánh chỉ mục FTS5 (`brain/index.db`) để tìm kiếm BM25 kèm trích dẫn chính xác nguồn file.

4. **Self-Expanding Meta-Skill (`skill_builder`):**
   - Cho phép Tokudo tự viết code một skill Python mới vào `skills/`.
   - Kiểm tra cú pháp AST (`ast.parse`) và tự nạp nóng (**Hot-Reload**) vào RAM ngay trong lúc đang trò chuyện mà **không cần khởi động lại bot**.

5. **Tác Vụ Nền & Tự Động Hóa:**
   - **Background Kanban Queue:** Hàng đợi ngầm chạy các tác vụ nặng, lưu trạng thái `TODO / DOING / DONE` vào SQLite, tự động gửi file kết quả về đúng kênh chat yêu cầu.
   - **Cron & Reminders:** Đặt lịch nhắc việc và tác vụ định kỳ qua APScheduler.

---

## 📂 Cấu Trúc Thư Mục

```text
tokudo/
├── .env.example              # Mẫu cấu hình Token, ID Whitelist, LLM API Keys
├── requirements.txt          # Thư viện phụ thuộc
├── main.py                   # Entrypoint khởi chạy toàn bộ hệ thống
├── README.md                 # Tài liệu hướng dẫn kiến trúc & sử dụng chuyên sâu
├── web/
│   └── dashboard_server.py   # Máy chủ Web Dashboard UI trực quan (localhost:8080)
├── core/
│   ├── engine.py             # Bộ não điều phối trung tâm (LLM Reasoning + Tool Calling + [MACHINE_ID])
│   ├── brain_router.py       # Quản trị hạm đội tài khoản AI, Smart Failover & Token Telemetry
│   ├── schema.py             # UnifiedMessage, UnifiedResponse, ActionButton
│   └── security.py           # Whitelist & Human-in-the-loop Approval Manager
├── adapters/
│   ├── telegram_adapter.py   # Giao tiếp Telegram (Long-polling, Buttons, Media)
│   └── discord_adapter.py    # Giao tiếp Discord (Gateway, Embeds, Buttons)
├── brain/
│   ├── memory_manager.py     # Quản lý bộ nhớ dài hạn & cơ chế Auto-Reflection
│   ├── wiki_distiller.py     # Chưng cất tri thức & tìm kiếm SQLite FTS5
│   ├── index.db              # SQLite FTS5 Database (Full-text Search)
│   ├── memory/               # Trí nhớ dài hạn (.md)
│   └── wiki/                 # Kho tri thức tích lũy (.md)
├── skills/
│   ├── base.py               # BaseSkill & Dynamic Hot-Reloading Registry
│   ├── skill_builder.py      # Meta-skill tự viết và nạp thêm skill mới
│   ├── os_controller.py      # Điều khiển Windows, chụp màn hình, kiểm tra phần cứng
│   ├── code_architect.py     # Hỗ trợ lập trình (Python, Rust, SketchUp Ruby, C++) & quét bảo mật
│   └── multimodal.py         # Phân tích ảnh, tóm tắt video YouTube, tạo giọng nói (TTS)
└── automation/
    ├── kanban_worker.py      # Hàng đợi tác vụ nặng ngầm (SQLite Kanban)
    └── scheduler.py          # Quản lý Cron job & lịch nhắc việc
```

---

## 🚀 Hướng Dẫn Cài Đặt Độc Lập (Cross-Platform Setup)

Hệ thống hỗ trợ chạy độc lập trên cả **Windows, macOS và Linux** với kịch bản cài đặt tự động 1-click.

### 🪟 1. Trên Windows (10 / 11)
- **Cách 1 (PowerShell Installer):**
  ```powershell
  powershell -ExecutionPolicy Bypass -File install.ps1
  ```
- **Cách 2 (1-Click Launcher):**
  Nhấp đúp chuột vào file **`start.bat`** (tự động cài đặt nếu chưa có `.venv` và tự bật Web Dashboard `http://localhost:8080`).

### 🍏 2. Trên macOS
Mở Terminal trong thư mục dự án và chạy:
```bash
# Cài đặt tự động môi trường và thư viện
bash install.sh

# Khởi chạy hệ thống và mở Dashboard
./start.sh
```

### 🐧 3. Trên Linux (Ubuntu / Debian / Arch / Fedora)
```bash
# Cài đặt tự động
bash install.sh

# Khởi chạy hệ thống
./start.sh

# Dừng hệ thống khi cần
./stop.sh
```

---

### ⚙️ Cấu Hình Môi Trường (.env)
Sao chép `.env.example` thành `.env` và điền các thông số:
- `MACHINE_ID`: Tên định danh máy trạm (vd: `PC-WINDOWS-01`, `MACBOOK-PRO`, `UBUNTU-SERVER`)
- `TELEGRAM_ALLOWED_USER_ID`: ID Telegram của bạn (Lấy từ @userinfobot)
- `DISCORD_ALLOWED_USER_ID`: ID Discord của bạn (Bật Developer Mode -> Copy User ID)
- `TELEGRAM_BOT_TOKEN`: Token lấy từ @BotFather
- `DISCORD_BOT_TOKEN`: Token Discord Bot từ Developer Portal
- `GEMINI_API_KEY` hoặc `OPENAI_API_KEY`: Khóa API LLM (hoặc cấu hình trực quan qua Web Dashboard)

### 4. Các Lệnh Điều Khiển Thường Dùng
- `/start` hoặc `/help`: Hiển thị hướng dẫn và danh sách tính năng.
- `/status`: Kiểm tra thông số CPU, RAM, ổ đĩa C, hàng đợi Kanban và Cron jobs.
- `/remember <nội dung>`: Ghi nhớ trực tiếp kiến thức/thói quen vào Second Brain.
- `/wiki <từ khóa>`: Tìm kiếm toàn văn FTS5 trong kho tri thức đã chưng cất.
- `/queue <tiêu đề>`: Đẩy tác vụ nặng vào hàng đợi ngầm.
- `/skills`: Xem danh sách tất cả các công cụ/kỹ năng đang sẵn sàng.
