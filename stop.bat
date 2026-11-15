@echo off
chcp 65001 > nul
title Tokudo AI OS — Stop Service
color 0C

echo ======================================================================
echo                  🛑 DỪNG TIẾN TRÌNH TOKUDO AI OS
echo ======================================================================
echo.

echo Đang tìm và giải phóng cổng mạng 8080...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8080 ^| findstr LISTENING') do (
    echo Đang đóng tiến trình PID %%a đang chiếm port 8080...
    taskkill /F /PID %%a > nul 2>&1
)

echo Đang dừng các tác vụ Python liên quan đến Tokudo...
wmic process where "commandline like '%%tokudo%%main.py%%'" call terminate > nul 2>&1

echo.
echo ✅ Đã dừng toàn bộ dịch vụ của Tokudo AI OS an toàn!
echo.
timeout /t 3 > nul
