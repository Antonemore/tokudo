"""
tokudo.build_exe
Automated Standalone Windows Executable (.exe) Packager for Tokudo AI OS.
Compiles main.py into dist/Tokudo.exe using PyInstaller and packages
Tokudo-v<version>-Windows-x64.zip for zero-dependency desktop deployment.
"""

from __future__ import annotations
import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

from core.version import __version__, __codename__


def build_executable():
    print("=" * 65)
    print(f"🔨 BUILDING WINDOWS STANDALONE EXECUTABLE: TOKUDO v{__version__}")
    print(f"Codename: {__codename__}")
    print("=" * 65)

    root_dir = Path(__file__).parent.resolve()
    spec_path = root_dir / "tokudo.spec"
    dist_dir = root_dir / "dist"

    if not spec_path.exists():
        print(f"❌ Error: {spec_path} not found.")
        sys.exit(1)

    # 1. Run PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_path),
    ]

    print(f"-> Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=root_dir)

    if result.returncode != 0:
        print("❌ PyInstaller compilation failed!")
        sys.exit(result.returncode)

    exe_path = dist_dir / "Tokudo.exe"
    if not exe_path.exists():
        print(f"❌ Error: Expected executable not found at {exe_path}")
        sys.exit(1)

    exe_size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"✅ Compilation Succeeded: {exe_path.name} ({exe_size_mb:.2f} MB)")

    # 2. Package Portable Distribution Bundle
    portable_zip_name = f"Tokudo-v{__version__}-Windows-x64.zip"
    portable_zip_path = dist_dir / portable_zip_name
    print(f"-> Creating portable zip package: {portable_zip_name}...")

    with zipfile.ZipFile(portable_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(exe_path, arcname="Tokudo.exe")

        env_example = root_dir / ".env.example"
        if env_example.exists():
            zipf.write(env_example, arcname=".env.example")

        readme = root_dir / "README.md"
        if readme.exists():
            zipf.write(readme, arcname="README.md")

        brains_json = root_dir / "data" / "brains.json"
        if brains_json.exists():
            zipf.write(brains_json, arcname="data/brains.json")

        run_bat = root_dir / "run_tokudo.bat"
        if run_bat.exists():
            zipf.write(run_bat, arcname="run_tokudo.bat")

    zip_size_mb = portable_zip_path.stat().st_size / (1024 * 1024)
    print(f"🎉 Successfully created Windows distribution package:")
    print(f"   📦 {portable_zip_path.name} ({zip_size_mb:.2f} MB)")
    print(f"   🚀 Executable: {exe_path} ({exe_size_mb:.2f} MB)")


if __name__ == "__main__":
    build_executable()
