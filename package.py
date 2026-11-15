"""
tokudo.package
Automated Production Packaging Script:
Bundles the Tokudo AI OS into clean, distributable release archives:
- Tokudo-v1.0.0-Universal.zip (for Windows & general use)
- Tokudo-v1.0.0-Universal.tar.gz (for Linux & macOS)
excluding private tokens, database files, and virtual environment caches.
"""

import os
import sys
import shutil
import zipfile
import tarfile
import hashlib
from pathlib import Path

from core.version import __version__, __codename__


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_package():
    print("=" * 65)
    print(f"📦 ĐÓNG GÓI PHÁT HÀNH: TOKUDO AI OS v{__version__} ({__codename__})")
    print("=" * 65)

    root_dir = Path(__file__).parent.resolve()
    dist_dir = root_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    release_base = f"Tokudo-v{__version__}-Universal"
    zip_path = dist_dir / f"{release_base}.zip"
    tar_path = dist_dir / f"{release_base}.tar.gz"

    exclude_dirs = {
        ".venv",
        "venv",
        "__pycache__",
        ".git",
        ".idea",
        ".vscode",
        "dist",
    }
    exclude_files = {
        ".env",
        "index.db",
        "kanban.db",
        "brain_usage.db",
    }
    exclude_extensions = {".pyc", ".pyd", ".pyo", ".db", ".db-wal", ".db-shm"}

    print(f"-> Đang chuẩn bị tệp tin từ: {root_dir}")

    # Collect files
    files_to_pack = []
    for file_p in root_dir.rglob("*"):
        parts = file_p.relative_to(root_dir).parts
        if any(ex in parts for ex in exclude_dirs):
            continue

        if file_p.is_file():
            if file_p.name in exclude_files:
                continue
            if file_p.suffix in exclude_extensions:
                continue
            if any(p in parts for p in ("screenshots", "tts", "uploads")) and file_p.name != ".gitkeep":
                continue

            rel_path = file_p.relative_to(root_dir)
            files_to_pack.append((file_p, rel_path))

    # 1. Build ZIP
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_p, rel_path in files_to_pack:
            archive_arcname = Path(release_base) / rel_path
            zipf.write(file_p, arcname=str(archive_arcname))

    # 2. Build TAR.GZ
    with tarfile.open(tar_path, "w:gz") as tarf:
        for file_p, rel_path in files_to_pack:
            archive_arcname = Path(release_base) / rel_path
            tarf.add(file_p, arcname=str(archive_arcname))

    zip_size_mb = round(zip_path.stat().st_size / (1024 * 1024), 2)
    tar_size_mb = round(tar_path.stat().st_size / (1024 * 1024), 2)
    zip_hash = compute_sha256(zip_path)
    tar_hash = compute_sha256(tar_path)

    # Manifest
    manifest_path = dist_dir / f"{release_base}-manifest.txt"
    manifest_content = (
        f"TOKUDO AI OS — RELEASE MANIFEST\n"
        f"Version: v{__version__}\n"
        f"Codename: {__codename__}\n"
        f"Files Count: {len(files_to_pack)} clean files\n\n"
        f"1. ZIP Archive (Windows / All):\n"
        f"   File: {zip_path.name}\n"
        f"   Size: {zip_size_mb} MB\n"
        f"   SHA-256: {zip_hash}\n\n"
        f"2. TAR.GZ Archive (macOS / Linux):\n"
        f"   File: {tar_path.name}\n"
        f"   Size: {tar_size_mb} MB\n"
        f"   SHA-256: {tar_hash}\n"
    )
    manifest_path.write_text(manifest_content, encoding="utf-8")

    print("\n" + "=" * 65)
    print("🎉 ĐÓNG GÓI PHÁT HÀNH ĐA NỀN TẢNG THÀNH CÔNG!")
    print(f"• Gói ZIP:    {zip_path.name} ({zip_size_mb} MB) - SHA256: {zip_hash[:16]}...")
    print(f"• Gói TAR.GZ: {tar_path.name} ({tar_size_mb} MB) - SHA256: {tar_hash[:16]}...")
    print(f"• Bảng kê:    {manifest_path.name}")
    print("=" * 65)


if __name__ == "__main__":
    build_package()
