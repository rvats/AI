"""Build Nexus Desktop binaries with PyInstaller.

Usage:
    python packaging/build.py
    python packaging/build.py --onedir
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "desktop_app.py"
INDEX_HTML = ROOT / "index.html"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"


def detect_target_name() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def build(onefile: bool) -> int:
    target = detect_target_name()
    sep = ";" if target == "windows" else ":"
    mode_flag = "--onefile" if onefile else "--onedir"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        mode_flag,
        "--windowed",
        "--name",
        f"NexusDesktop-{target}",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--add-data",
        f"{INDEX_HTML}{sep}.",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        str(ENTRY),
    ]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("Build failed.")
        return result.returncode

    if onefile:
        if target == "windows":
            artifact = DIST_DIR / f"NexusDesktop-{target}.exe"
        else:
            artifact = DIST_DIR / f"NexusDesktop-{target}"
        print(f"Build complete: {artifact}")
    else:
        artifact_dir = DIST_DIR / f"NexusDesktop-{target}"
        print(f"Build complete: {artifact_dir}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Nexus Desktop binaries with PyInstaller.")
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Build folder-based output instead of single-file output.",
    )
    args = parser.parse_args()

    return build(onefile=not args.onedir)


if __name__ == "__main__":
    raise SystemExit(main())
