"""
tokudo.package
Automated Production Packaging Script:
Bundles the Tokudo AI OS into a clean, distributable release archive (Tokudo-v1.0.0-Windows.zip)
excluding private tokens, database files, and virtual environment caches.
"""

import os
import sys
import shutil
import zipfile
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

    release_name = f"Tokudo-v{__version__}-Windows"
    archive_path = dist_dir / f"{release_name}.zip"

    # Files and folders to exclude from distribution
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
        ".env",  # Never bundle real secrets!
        "index.db",
        "kanban.db",
        "brain_usage.db",
    }
    exclude_extensions = {".pyc", ".pyd", ".pyo", ".db", ".db-wal", ".db-shm"}

    print(f"-> Đang chuẩn bị tệp tin từ: {root_dir}")
    print(f"-> Đích đóng gói: {archive_path.name}")

    file_count = 0
    total_uncompressed_bytes = 0

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_p in root_dir.rglob("*"):
            # Check directory exclusions
            parts = file_p.relative_to(root_dir).parts
            if any(ex in parts for ex in exclude_dirs):
                continue

            if file_p.is_file():
                if file_p.name in exclude_files:
                    continue
                if file_p.suffix in exclude_extensions:
                    continue
                # Skip dynamically generated screenshot/audio/upload artifacts
                if any(p in parts for p in ("screenshots", "tts", "uploads")) and file_p.name != ".gitkeep":
                    continue

                rel_path = file_p.relative_to(root_dir)
                archive_arcname = Path(release_name) / rel_path

                zipf.write(file_p, arcname=str(archive_arcname))
                file_count += 1
                total_uncompressed_bytes += file_p.stat().st_size

    archive_size_mb = round(archive_path.stat().st_size / (1024 * 1024), 2)
    sha256_hash = compute_sha256(archive_path)

    # Write Release Metadata Manifest
    manifest_path = dist_dir / f"{release_name}-manifest.txt"
    manifest_content = (
        f"TOKUDO AI OS — RELEASE MANIFEST\n"
        f"Version: v{__version__}\n"
        f"Codename: {__codename__}\n"
        f"Release File: {archive_path.name}\n"
        f"File Size: {archive_size_mb} MB ({file_count} files)\n"
        f"SHA-256 Checksum: {sha256_hash}\n"
        f"Release Date: {sys.version.split()[0]} build\n"
    )
    manifest_path.write_text(manifest_content, encoding="utf-8")

    print("\n" + "=" * 65)
    print("🎉 ĐÓNG GÓI PHÁT HÀNH HOÀN TẤT THÀNH CÔNG!")
    print(f"• Bản phát hành: {archive_path}")
    print(f"• Dung lượng ZIP: {archive_size_mb} MB ({file_count} tệp tin sạch)")
    print(f"• Mã băm SHA-256: {sha256_hash}")
    print(f"• Bảng kê manifest: {manifest_path.name}")
    print("=" * 65)


if __name__ == "__main__":
    build_package()
