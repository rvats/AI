# Nexus Agent Desktop

Nexus Agent includes a cross-platform desktop UI built with Tkinter.

## Features

- Desktop app for Windows, macOS, and Linux
- Built-in local backend lifecycle controls (start/stop/test)
- Streaming prompt chat against `/api/chat`
- Capability prompt presets for common agent workflows
- Image Studio tab with upload, preview, rotation, flipping, grayscale, brightness, contrast, and save-as export
- Image-aware prompt runner that sends the current edit context to the agent

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python desktop_app.py
```

## One-Click Packaging (PyInstaller)

Use the OS-specific script to build a distributable binary in one command.

### Windows

```bat
package_windows.bat
```

### macOS

```bash
chmod +x package_macos.sh
./package_macos.sh
```

### Linux

```bash
chmod +x package_linux.sh
./package_linux.sh
```

Artifacts are written to `dist/`.

## Manual Build

```bash
python -m pip install -r requirements-packaging.txt
python packaging/build.py
```

Use `python packaging/build.py --onedir` if you prefer folder-based output instead of single-file output.

## Notes

- In source mode, **Start Local Backend** launches `main.py` in a subprocess.
- In packaged mode, **Start Local Backend** runs the backend in embedded mode for portability.
- If you already run the backend separately, set API URL to that instance and click **Test Connection**.
- Image edits are non-destructive and only written when using **Save As**.
