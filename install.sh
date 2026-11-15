#!/usr/bin/env bash
# =====================================================================
# TOKUDO AI OS — OFFICIAL MACOS & LINUX INSTALLER
# =====================================================================
# Usage: bash install.sh  (or curl -sSL ... | bash)
# =====================================================================

set -e

echo "======================================================================"
echo "          🧠 TOKUDO AI OS — TRÌNH CÀI ĐẶT ĐỘC LẬP (macOS / Linux)"
echo "              Personal AI Agent & Second Brain Hub (v1.0.0)"
echo "======================================================================"
echo ""

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
echo "📁 Thư mục cài đặt: $ROOT_DIR"

# 1. Kiểm tra Python Runtime (3.11+)
echo ""
echo "[1/4] Kiểm tra môi trường Python..."
PYTHON_BIN=""
for cmd in python3.12 python3.11 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PY_VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
            PYTHON_BIN="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Không tìm thấy Python 3.11+!"
    echo "• Trên Ubuntu/Debian: sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
    echo "• Trên macOS: brew install python@3.12"
    exit 1
fi

echo "✅ Sử dụng Python: $($PYTHON_BIN --version) ($PYTHON_BIN)"

# 2. Khởi tạo môi trường ảo .venv
echo ""
echo "[2/4] Khởi tạo môi trường ảo độc lập (.venv)..."
if [ ! -f ".venv/bin/python" ]; then
    "$PYTHON_BIN" -m venv .venv
    echo "✅ Đã tạo môi trường ảo .venv thành công."
else
    echo "ℹ️ Môi trường ảo .venv đã tồn tại sẵn."
fi

# 3. Cài đặt toàn bộ thư viện
echo ""
echo "[3/4] Đang cài đặt thư viện phụ thuộc từ requirements.txt..."
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -r requirements.txt --quiet
echo "✅ Đã cài đặt đầy đủ các gói thư viện!"

# 4. Cấu hình ban đầu
echo ""
echo "[4/4] Kiểm tra cấu hình và phân quyền thực thi..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ Đã tạo file .env từ .env.example."
fi

mkdir -p data/screenshots data/tts data/uploads brain/memory brain/wiki

# Cấp quyền thực thi cho các script
chmod +x start.sh stop.sh install.sh 2>/dev/null || true

# Chạy smoke test
echo ""
echo "🧪 Đang chạy kiểm thử xác minh..."
.venv/bin/python tests/test_smoke.py

echo ""
echo "======================================================================"
echo "🎉 CÀI ĐẶT TOKUDO AI OS THÀNH CÔNG!"
echo "======================================================================"
echo "👉 Khởi chạy ngay: ./start.sh"
echo "🌐 Giao diện Web OS: http://localhost:8080"
echo "🛑 Dừng hệ thống:   ./stop.sh"
echo "======================================================================"
echo ""
