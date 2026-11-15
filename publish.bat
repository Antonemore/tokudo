@echo off
chcp 65001 > nul
title Tokudo AI OS — GitHub Publisher
color 0B

echo ======================================================================
echo           🚀 XUẤT BẢN TOKUDO AI OS LÊN GITHUB
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Kiểm tra Git
where git > nul 2>&1
if errorlevel 1 (
    echo ❌ Không tìm thấy Git trên máy tính! Vui lòng cài đặt Git: https://git-scm.com/
    pause
    exit /b 1
)

:: 2. Kiểm tra Remote Origin
git remote get-url origin > nul 2>&1
if errorlevel 1 (
    echo ℹ️ Chưa thiết lập địa chỉ GitHub Repository (remote origin).
    echo.
    echo Vui lòng tạo 1 repository mới trên GitHub (vd: https://github.com/your-username/tokudo)
    echo sau đó dán đường link HTTPS hoặc SSH của repo vào đây:
    set /p REPO_URL="👉 Đường link GitHub Repo: "
    
    if "%REPO_URL%"=="" (
        echo ❌ Không có đường link repo. Hủy thao tác.
        pause
        exit /b 1
    )
    
    git remote add origin %REPO_URL%
    echo ✅ Đã liên kết với: %REPO_URL%
)

:: 3. Xác nhận Commit
echo.
echo [1/3] Đang thêm các tệp tin sạch vào Git (đã tự động bỏ qua .env và databases)...
git add .

echo.
set /p COMMIT_MSG="[2/3] Nhập thông điệp cập nhật (Bấm Enter để dùng mặc định 'release: Tokudo AI OS v1.0.0'): "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=release: Tokudo AI OS v1.0.0

git commit -m "%COMMIT_MSG%"

:: 4. Đẩy lên GitHub
echo.
echo [3/3] Đang đẩy mã nguồn và phiên bản tag lên GitHub...
git branch -M main
git push -u origin main --tags

if errorlevel 1 (
    echo.
    echo ⚠️ Đẩy lên GitHub gặp sự cố (có thể do quyền truy cập hoặc cần đăng nhập).
    echo Mẹo: Hãy đảm bảo bạn đã đăng nhập tài khoản GitHub trên Git Credential Manager.
) else (
    echo.
    echo ======================================================================
    echo 🎉 XUẤT BẢN THÀNH CÔNG LÊN GITHUB!
    echo ======================================================================
)

echo.
pause
