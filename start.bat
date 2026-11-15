@echo off
chcp 65001 > nul
title Tokudo AI OS — Personal AI Agent & Second Brain
color 0B

echo ======================================================================
echo           🧠 TOKUDO AI OS — PERSONAL AGENT ^& SECOND BRAIN
echo                       Phiên bản: v1.0.0 (Genesis Core)
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Kiểm tra môi trường ảo .venv
if not exist ".venv\Scripts\python.exe" (
    echo ⚠️  Chưa phát hiện môi trường ảo .venv. Đang tự động chạy setup...
    call setup.bat
    if errorlevel 1 (
        echo ❌ Cài đặt môi trường thất bại. Vui lòng kiểm tra lại Python!
        pause
        exit /b 1
    )
)

:: 2. Kiểm tra file cấu hình .env
if not exist ".env" (
    echo ℹ️  Chưa có file .env. Đang tự động sao chép từ .env.example...
    copy ".env.example" ".env" > nul
    echo ⚠️  Vui lòng mở file .env và điền Token/API Key nếu muốn kết nối Telegram/Discord!
)

:: 3. Mở Web Dashboard trên trình duyệt mặc định sau 2 giây
start "" powershell -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:8080'"

echo 🚀 Đang khởi chạy hệ sinh thái Tokudo...
echo 🌐 Giao diện Web Dashboard: http://localhost:8080
echo 💡 Nhấn Ctrl + C để dừng bot khi cần.
echo.
echo ----------------------------------------------------------------------

:: 4. Khởi chạy Core
".venv\Scripts\python.exe" main.py

pause
