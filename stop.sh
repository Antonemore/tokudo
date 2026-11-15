#!/usr/bin/env bash
# =====================================================================
# TOKUDO AI OS — STOP SCRIPT (macOS / Linux)
# =====================================================================

echo "🛑 Đang dừng Tokudo AI OS..."

# Dừng tiến trình chiếm port 8080 nếu có
if command -v lsof >/dev/null 2>&1; then
    PID=$(lsof -ti:8080 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo "-> Dừng tiến trình port 8080 (PID: $PID)..."
        kill -15 "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null || true
    fi
fi

# Dừng các tiến trình main.py của Tokudo
pkill -f "python.*main.py" 2>/dev/null || true

echo "✅ Đã dừng toàn bộ dịch vụ Tokudo an toàn!"
