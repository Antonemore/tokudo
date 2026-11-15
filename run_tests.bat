@echo off
chcp 65001 > nul
title Tokudo AI OS — Smoke Test Suite
color 0E

echo ======================================================================
echo                  🧪 CHẠY BỘ KIỂM THỬ TÍCH HỢP TOKUDO
echo ======================================================================
echo.

cd /d "%~dp0"
".venv\Scripts\python.exe" tests\test_smoke.py

echo.
pause
