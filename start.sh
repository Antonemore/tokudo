#!/usr/bin/env bash
# =====================================================================
# TOKUDO AI OS — ONE-CLICK LAUNCHER (macOS / Linux)
# =====================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".venv/bin/python" ]; then
    echo "⚠️ Chưa cài đặt môi trường. Đang chạy install.sh..."
    bash install.sh
fi

if [ ! -f ".env" ]; then
    cp .env.example .env
fi

# Tự động mở trình duyệt sau 2 giây
(
    sleep 2
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "http://localhost:8080" >/dev/null 2>&1 || true
    elif which xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:8080" >/dev/null 2>&1 || true
    fi
) &

echo "======================================================================"
echo "          🧠 KHỞI CHẠY TOKUDO AI OS (v1.0.0)"
echo "======================================================================"
echo "🌐 Web Dashboard: http://localhost:8080"
echo "💡 Nhấn Ctrl + C để dừng bot khi cần."
echo "----------------------------------------------------------------------"

exec .venv/bin/python main.py
