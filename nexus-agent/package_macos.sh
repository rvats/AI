#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Installing runtime + packaging dependencies..."
python3 -m pip install -r requirements-packaging.txt

echo "Building Nexus Desktop (macOS onefile)..."
python3 packaging/build.py

echo "Done. Binary is in dist/"
