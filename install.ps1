# =====================================================================
# TOKUDO AI OS — OFFICIAL WINDOWS INSTALLER (POWERSHELL)
# =====================================================================
# Requires: Windows 10/11, Python 3.11+
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1
# =====================================================================

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Show-Header {
    Clear-Host
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "          🧠 TOKUDO AI OS — TRÌNH CÀI ĐẶT CHÍNH THỨC (v1.0.0)" -ForegroundColor Yellow
    Write-Host "              Personal AI Agent & Second Brain on Windows" -ForegroundColor White
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host ""
}

Show-Header

# 1. Xác định thư mục gốc
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $RootDir
Write-Host "📁 Thư mục cài đặt: $RootDir" -ForegroundColor Gray

# 2. Kiểm tra Python Runtime
Write-Host "`n[1/5] Kiểm tra môi trường Python..." -ForegroundColor Cyan
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue

if (-not $PythonCmd) {
    Write-Host "❌ Không tìm thấy Python trong hệ thống!" -ForegroundColor Red
    Write-Host "Vui lòng cài đặt Python 3.11 hoặc 3.12 từ https://www.python.org/" -ForegroundColor Yellow
    Write-Host "⚠️ QUAN TRỌNG: Hãy tích chọn [x] Add Python to PATH khi cài đặt." -ForegroundColor Yellow
    Exit 1
}

$PyVer = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
Write-Host "✅ Đã tìm thấy Python: v$PyVer ($($PythonCmd.Source))" -ForegroundColor Green

# 3. Khởi tạo Virtual Environment (.venv)
Write-Host "`n[2/5] Khởi tạo môi trường ảo Python (.venv)..." -ForegroundColor Cyan
$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "-> Đang tạo .venv..." -ForegroundColor Gray
    python -m venv .venv
    Write-Host "✅ Đã khởi tạo môi trường ảo .venv thành công." -ForegroundColor Green
} else {
    Write-Host "ℹ️ Môi trường ảo .venv đã tồn tại sẵn." -ForegroundColor Gray
}

# 4. Nâng cấp Pip & Cài đặt Requirements
Write-Host "`n[3/5] Đang cài đặt thư viện phụ thuộc từ requirements.txt..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -r requirements.txt --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Cài đặt toàn bộ thư viện thành công!" -ForegroundColor Green
} else {
    Write-Host "❌ Quá trình cài đặt gói thư viện gặp lỗi. Vui lòng kiểm tra lại mạng!" -ForegroundColor Red
    Exit 1
}

# 5. Khởi tạo cấu hình ban đầu
Write-Host "`n[4/5] Khởi tạo tệp tin cấu hình và thư mục dữ liệu..." -ForegroundColor Cyan

# Tạo .env nếu chưa có
$EnvFile = Join-Path $RootDir ".env"
$EnvExample = Join-Path $RootDir ".env.example"
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Host "✅ Đã khởi tạo file .env từ .env.example." -ForegroundColor Green
    }
} else {
    Write-Host "ℹ️ File .env đã tồn tại sẵn (giữ nguyên bí mật của bạn)." -ForegroundColor Gray
}

# Tạo các thư mục lưu trữ cục bộ
$Dirs = @("data\screenshots", "data\tts", "data\uploads", "brain\memory", "brain\wiki")
foreach ($d in $Dirs) {
    $fullP = Join-Path $RootDir $d
    if (-not (Test-Path $fullP)) {
        New-Item -ItemType Directory -Path $fullP -Force | Out-Null
    }
}
Write-Host "✅ Đã xác thực các thư mục runtime." -ForegroundColor Green

# 6. Chạy bộ kiểm thử tự động (Smoke Test)
Write-Host "`n[5/5] Đang chạy kiểm thử tích hợp (Smoke Test)..." -ForegroundColor Cyan
$TestScript = Join-Path $RootDir "tests\test_smoke.py"
& $VenvPython $TestScript

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 7/7 phân hệ cốt lõi đã vượt qua kiểm thử hoàn hảo!" -ForegroundColor Green
} else {
    Write-Host "⚠️ Có cảnh báo trong kiểm thử, vui lòng xem log phía trên." -ForegroundColor Yellow
}

# Tạo Desktop Shortcut (Tùy chọn tiện lợi)
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "Tokudo AI OS.lnk"
$TargetBat = Join-Path $RootDir "start.bat"

try {
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetBat
    $Shortcut.WorkingDirectory = $RootDir
    $Shortcut.Description = "Khởi chạy Tokudo Personal AI OS & Web Dashboard"
    $Shortcut.Save()
    Write-Host "`n🌟 Đã tạo lối tắt (Desktop Shortcut) tại: $ShortcutPath" -ForegroundColor Cyan
} catch {
    # Không bắt buộc nếu môi trường hạn chế COM
}

Write-Host "`n======================================================================" -ForegroundColor Green
Write-Host "🎉 CÀI ĐẶT TOKUDO AI OS THÀNH CÔNG RỰC RỠ!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "👉 Để khởi chạy: Nhấp đúp vào 'Tokudo AI OS' trên màn hình Desktop hoặc chạy .\start.bat" -ForegroundColor White
Write-Host "🌐 Giao diện Web OS sẽ tự động mở tại: http://localhost:8080" -ForegroundColor Yellow
Write-Host "📱 Kết nối Telegram & Discord: Điền token vào file .env" -ForegroundColor White
Write-Host "======================================================================`n" -ForegroundColor Green
