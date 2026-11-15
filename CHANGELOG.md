# 📋 Nhật Ký Phiên Bản (Changelog) — Tokudo AI OS

All notable changes to the **Tokudo** Personal AI Agent & Second Brain will be documented in this file.

---

## [v1.0.0] — 2026-11-15 ("Genesis Core")

### 🚀 Tính năng đột phá chính (Major Features)
- **Single-Core Multi-Frontend:**
  - Đồng bộ hóa 2 chiều song song giữa **Telegram** (`python-telegram-bot`) và **Discord** (`discord.py`) từ một lõi xử lý trung tâm duy nhất.
  - Chuẩn hóa thông điệp qua schema `UnifiedMessage` và điều phối kết quả bằng `UnifiedResponse`.
  - Hỗ trợ định danh trạm máy tính `[MACHINE_ID]` để vận hành nhiều máy trạm độc lập trong cùng một group chat.
  - Tự động chia nhỏ tin nhắn (Auto-chunking) khi vượt quá giới hạn ký tự (4000 ký tự trên Telegram, 2000 ký tự trên Discord).

- **Multi-Brain Fleet & Smart Auto-Failover:**
  - Quản trị cụm đa tài khoản AI trong cùng hệ thống: hỗ trợ đồng thời **3x ChatGPT, 3x Gemini Pro, 2x Gemini Free, 1x Claude, và 1x Local Ollama (0đ)**.
  - Cơ chế **Smart Cooldown & Failover**: Tự động chuyển đổi mượt mà sang tài khoản AI kế tiếp khi tài khoản hiện tại chạm ngưỡng rate-limit `429 Too Many Requests` hoặc hết Quota mà không làm gián đoạn phiên chat.
  - Đo lường lưu lượng Token thời gian thực (Prompt, Completion, Total Tokens, Request Count, Error Count) lưu trữ vào SQLite `data/brain_usage.db`.

- **Web OS Dashboard Trực Quan (`http://localhost:8080`):**
  - Giao diện Web Dark Glassmorphism tối ưu tương đương và linh hoạt hơn Javis OS.
  - Quản lý tài khoản AI trực quan: **Thêm mới, Sửa, Lưu, Xóa, Bật/Tắt, Ping kiểm tra API key, và Kích hoạt não chính (Hot-Switch)** bằng 1 click.
  - Giám sát phần cứng thời gian thực (CPU %, RAM %, Ổ đĩa C %) và chụp ảnh màn hình desktop Windows gửi về trình duyệt.
  - Quản trị bảng tác vụ ngầm Kanban và trình biên tập văn bản Second Brain Markdown trực tiếp.

- **Bảo Mật Nghiêm Ngặt & Human-In-The-Loop (HITL):**
  - Bộ lọc Whitelist tuyệt đối theo `TELEGRAM_ALLOWED_USER_ID` và `DISCORD_ALLOWED_USER_ID` (drop im lặng mọi request lạ).
  - Hàng rào phê duyệt 2 bước (HITL): Gửi nút bấm `[✅ Chấp thuận]` / `[❌ Từ chối]` về điện thoại trước khi thực thi bất kỳ lệnh nhạy cảm nào (Terminal PowerShell, đóng app, sinh code mới).

- **Second Brain & Tự Học Hỏi (Auto-Reflection):**
  - Trí nhớ dài hạn Markdown trong `brain/memory/` (`user_profile.md`, `preferences.md`, `lessons_learned.md`).
  - Cơ chế tự phản tỉnh (Auto-Reflection) chưng cất thói quen mới sau mỗi phiên trò chuyện.
  - Chưng cất tri thức dạng wiki và tra cứu toàn văn SQLite FTS5 (`brain/index.db`) với thuật toán BM25 và trích dẫn đường dẫn file.

- **Kỹ Năng Tự Mở Rộng (Self-Expanding Meta-Skill):**
  - Meta-skill `skill_builder` cho phép Tokudo tự lập trình thêm kỹ năng Python mới, kiểm tra cú pháp AST (`ast.parse`) và **Hot-Reload trực tiếp vào RAM** không cần khởi động lại ứng dụng.
  - Kỹ năng tích hợp sẵn: `os_controller` (quản lý app Windows, chụp màn hình, kiểm tra phần cứng), `code_architect` (cây dự án, audit bảo mật, hỗ trợ SketchUp Ruby / Rust / C++ / Python), `multimodal` (phân tích ảnh, tóm tắt video YouTube, tạo giọng đọc tiếng Việt TTS).

- **Tác Vụ Nền & Hẹn Giờ:**
  - Background Kanban Queue (`TODO -> DOING -> DONE`) với SQLite persistence và tự động gửi báo cáo kèm file kết quả về đúng kênh chat yêu cầu.
  - Task Scheduler sử dụng `APScheduler` quản lý lịch nhắc việc và tác vụ định kỳ.

---

### 📦 Đóng gói & Bộ khởi chạy (Packaging & Launchers)
- Thêm `start.bat`: Khởi chạy 1-click tự động kiểm tra môi trường, bật bot và mở ngay Web Dashboard trên trình duyệt.
- Thêm `stop.bat`: Đóng an toàn toàn bộ tiến trình Tokudo và giải phóng port 8080.
- Thêm `setup.bat`: Trình cài đặt môi trường và thư viện tự động cho Windows.
- Thêm `package.py`: Kịch bản tự động đóng gói dự án thành bản phát hành `Tokudo-v1.0.0-Windows.zip`.
