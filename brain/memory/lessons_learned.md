# Lessons Learned & Knowledge Vault

- **Windows Path Handling:** Luôn dùng `pathlib.Path` hoặc chuẩn hóa đường dẫn để tránh lỗi ký tự escape trong chuỗi Windows (`\`).
- **AsyncIO & GUI / Subprocess:** Khi chạy các tác vụ đồng bộ nặng (PIL image grab, ffmpeg, CPU bound), luôn đẩy vào `asyncio.to_thread` hoặc subprocess non-blocking để không làm đơ bot Telegram/Discord.
- **SQLite Concurrency:** Kích hoạt chế độ WAL (`PRAGMA journal_mode=WAL`) cho SQLite để hỗ trợ ghi đọc đồng thời mà không bị lock database.
