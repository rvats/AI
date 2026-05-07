"""
Nexus Desktop App (cross-platform)

Features:
- Starts/stops Nexus FastAPI backend locally
- Streams prompt responses from /api/chat
- Upload, preview, and edit images (rotate, flip, grayscale, brightness, contrast)
- Sends image-aware prompts to the agent for additional capabilities

Run:
    python desktop_app.py
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import ModuleType

import requests
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from PIL import Image, ImageEnhance, ImageOps, ImageTk


APP_DIR = Path(__file__).resolve().parent
DEFAULT_API_URL = "http://127.0.0.1:8000"


class NexusDesktopApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Nexus Desktop")
        self.geometry("1220x820")
        self.minsize(1024, 700)

        self.backend_process: subprocess.Popen[str] | None = None
        self.backend_running = False
        self.backend_thread: threading.Thread | None = None
        self.backend_server = None
        self.main_module: ModuleType | None = None

        self.event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.chat_stream_in_progress = False

        self.current_image_path: Path | None = None
        self.original_image: Image.Image | None = None
        self.preview_image: Image.Image | None = None
        self.preview_photo: ImageTk.PhotoImage | None = None

        self.rotate_steps = 0
        self.flip_h = False
        self.flip_v = False

        self._build_ui()
        self._set_default_capability_prompts()
        self.after(120, self._drain_ui_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(12, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Nexus Desktop", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")

        self.status_var = tk.StringVar(value="Backend: not connected")
        ttk.Label(header, textvariable=self.status_var, foreground="#1f6f43").grid(row=0, column=1, sticky="e")

        root_tabs = ttk.Notebook(self)
        root_tabs.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.chat_tab = ttk.Frame(root_tabs, padding=10)
        self.image_tab = ttk.Frame(root_tabs, padding=10)
        root_tabs.add(self.chat_tab, text="Agent Chat")
        root_tabs.add(self.image_tab, text="Image Studio")

        self._build_chat_tab()
        self._build_image_tab()

    def _build_chat_tab(self) -> None:
        self.chat_tab.columnconfigure(0, weight=3)
        self.chat_tab.columnconfigure(1, weight=1)
        self.chat_tab.rowconfigure(1, weight=1)

        conn = ttk.LabelFrame(self.chat_tab, text="Connection", padding=10)
        conn.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        conn.columnconfigure(1, weight=1)

        ttk.Label(conn, text="API URL").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.api_url_var = tk.StringVar(value=DEFAULT_API_URL)
        ttk.Entry(conn, textvariable=self.api_url_var).grid(row=0, column=1, sticky="ew", padx=(0, 8))

        self.start_btn = ttk.Button(conn, text="Start Local Backend", command=self.start_backend)
        self.start_btn.grid(row=0, column=2, padx=(0, 6))

        self.stop_btn = ttk.Button(conn, text="Stop Backend", command=self.stop_backend)
        self.stop_btn.grid(row=0, column=3, padx=(0, 6))

        ttk.Button(conn, text="Test Connection", command=self.test_connection).grid(row=0, column=4)

        chat_frame = ttk.LabelFrame(self.chat_tab, text="Conversation", padding=10)
        chat_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(0, weight=1)

        self.chat_text = ScrolledText(chat_frame, wrap=tk.WORD, font=("Segoe UI", 10), state=tk.DISABLED)
        self.chat_text.grid(row=0, column=0, sticky="nsew")

        input_row = ttk.Frame(chat_frame)
        input_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        input_row.columnconfigure(0, weight=1)

        self.prompt_var = tk.StringVar()
        prompt_entry = ttk.Entry(input_row, textvariable=self.prompt_var)
        prompt_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        prompt_entry.bind("<Return>", lambda _e: self.send_prompt())

        self.send_btn = ttk.Button(input_row, text="Send Prompt", command=self.send_prompt)
        self.send_btn.grid(row=0, column=1)

        side = ttk.LabelFrame(self.chat_tab, text="Agent Capabilities", padding=10)
        side.grid(row=1, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)
        side.rowconfigure(1, weight=1)

        ttk.Label(
            side,
            text="Click a preset to populate the prompt box, then edit and send.",
            foreground="#475569",
            wraplength=260,
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.capabilities_list = tk.Listbox(side, height=14)
        self.capabilities_list.grid(row=1, column=0, sticky="nsew")
        self.capabilities_list.bind("<<ListboxSelect>>", self._on_capability_selected)

        ttk.Button(side, text="Clear Chat", command=self.clear_chat).grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def _build_image_tab(self) -> None:
        self.image_tab.columnconfigure(0, weight=3)
        self.image_tab.columnconfigure(1, weight=2)
        self.image_tab.rowconfigure(1, weight=1)

        toolbar = ttk.LabelFrame(self.image_tab, text="Image File", padding=10)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Button(toolbar, text="Upload Image", command=self.upload_image).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(toolbar, text="Reset Edits", command=self.reset_edits).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(toolbar, text="Save As", command=self.save_image_as).grid(row=0, column=2, padx=(0, 8))

        self.image_path_var = tk.StringVar(value="No image loaded")
        ttk.Label(toolbar, textvariable=self.image_path_var, foreground="#334155").grid(row=0, column=3, sticky="w")

        preview_frame = ttk.LabelFrame(self.image_tab, text="Preview", padding=10)
        preview_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_label = ttk.Label(preview_frame, anchor="center")
        self.preview_label.grid(row=0, column=0, sticky="nsew")

        controls = ttk.LabelFrame(self.image_tab, text="Edit Controls", padding=10)
        controls.grid(row=1, column=1, sticky="nsew")
        controls.columnconfigure(1, weight=1)

        ttk.Button(controls, text="Rotate Left", command=self.rotate_left).grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 8))
        ttk.Button(controls, text="Rotate Right", command=self.rotate_right).grid(row=0, column=1, sticky="ew", pady=(0, 8))
        ttk.Button(controls, text="Flip Horizontal", command=self.toggle_flip_h).grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(0, 8))
        ttk.Button(controls, text="Flip Vertical", command=self.toggle_flip_v).grid(row=1, column=1, sticky="ew", pady=(0, 8))

        self.grayscale_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="Grayscale", variable=self.grayscale_var, command=self._apply_edits).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        ttk.Label(controls, text="Brightness").grid(row=3, column=0, sticky="w")
        self.brightness_var = tk.DoubleVar(value=1.0)
        ttk.Scale(controls, from_=0.2, to=2.2, orient=tk.HORIZONTAL, variable=self.brightness_var, command=lambda _v: self._apply_edits()).grid(
            row=3, column=1, sticky="ew", pady=(0, 8)
        )

        ttk.Label(controls, text="Contrast").grid(row=4, column=0, sticky="w")
        self.contrast_var = tk.DoubleVar(value=1.0)
        ttk.Scale(controls, from_=0.2, to=2.2, orient=tk.HORIZONTAL, variable=self.contrast_var, command=lambda _v: self._apply_edits()).grid(
            row=4, column=1, sticky="ew", pady=(0, 8)
        )

        image_prompt_box = ttk.LabelFrame(controls, text="Image-Aware Agent Prompt", padding=8)
        image_prompt_box.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        image_prompt_box.columnconfigure(0, weight=1)

        self.image_prompt_var = tk.StringVar()
        ttk.Entry(image_prompt_box, textvariable=self.image_prompt_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(image_prompt_box, text="Run Prompt", command=self.send_image_prompt).grid(row=0, column=1)

        ttk.Label(
            image_prompt_box,
            text="Sends a prompt with current image path and active edit state to the agent.",
            foreground="#64748b",
            wraplength=330,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------
    def _set_default_capability_prompts(self) -> None:
        self.capability_prompts = [
            "List this project structure and explain what each folder does.",
            "Create a Python script that summarizes CSV files in this repository.",
            "Search web for latest FastAPI best practices and summarize.",
            "Inspect environment and report missing dependencies for this app.",
            "Write unit tests for the most important module in this workspace.",
            "Generate a release checklist for this project.",
        ]
        for item in self.capability_prompts:
            self.capabilities_list.insert(tk.END, item)

    def _on_capability_selected(self, _event: object) -> None:
        selection = self.capabilities_list.curselection()
        if not selection:
            return
        self.prompt_var.set(self.capabilities_list.get(selection[0]))

    def clear_chat(self) -> None:
        self.chat_text.configure(state=tk.NORMAL)
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.configure(state=tk.DISABLED)

    def _append_chat(self, text: str) -> None:
        self.chat_text.configure(state=tk.NORMAL)
        self.chat_text.insert(tk.END, text)
        self.chat_text.see(tk.END)
        self.chat_text.configure(state=tk.DISABLED)

    def send_prompt(self) -> None:
        prompt = self.prompt_var.get().strip()
        if not prompt:
            return
        if self.chat_stream_in_progress:
            messagebox.showinfo("Busy", "Wait for the current response to finish.")
            return

        self.prompt_var.set("")
        self._append_chat(f"\nYou:\n{prompt}\n\nNexus:\n")

        self.chat_stream_in_progress = True
        self.send_btn.state(["disabled"])
        threading.Thread(target=self._stream_chat, args=(prompt,), daemon=True).start()

    def send_image_prompt(self) -> None:
        user_intent = self.image_prompt_var.get().strip()
        if not user_intent:
            user_intent = "Suggest the best edits and output workflow for this image."

        image_path_text = str(self.current_image_path) if self.current_image_path else "(no image loaded)"
        payload = {
            "image_path": image_path_text,
            "rotation_steps": self.rotate_steps,
            "flip_horizontal": self.flip_h,
            "flip_vertical": self.flip_v,
            "brightness": round(float(self.brightness_var.get()), 3),
            "contrast": round(float(self.contrast_var.get()), 3),
            "grayscale": bool(self.grayscale_var.get()),
        }

        prompt = (
            "You are helping with image editing in Nexus Desktop.\n"
            f"Current image context: {json.dumps(payload)}\n"
            f"User request: {user_intent}\n"
            "Provide concrete next steps and commands using your available capabilities."
        )

        self.prompt_var.set(prompt)
        self.send_prompt()

    def _stream_chat(self, prompt: str) -> None:
        api_url = self.api_url_var.get().strip().rstrip("/")
        url = f"{api_url}/api/chat"

        try:
            with requests.post(url, json={"message": prompt}, stream=True, timeout=240) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if not raw:
                        continue
                    try:
                        evt = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    etype = evt.get("type", "")
                    if etype == "text":
                        self.event_queue.put(("append", evt.get("content", "")))
                    elif etype == "tool_start":
                        self.event_queue.put(("append", f"\n[tool:start] {evt.get('name')}\n"))
                    elif etype == "tool_result":
                        tool_name = evt.get("name", "tool")
                        snippet = evt.get("result", "")
                        self.event_queue.put(("append", f"[tool:result] {tool_name}\n{snippet}\n"))
                    elif etype == "error":
                        self.event_queue.put(("append", f"\n[error] {evt.get('message', 'Unknown error')}\n"))
                    elif etype == "done":
                        break
        except requests.RequestException as exc:
            self.event_queue.put(("append", f"\n[connection error] {exc}\n"))
        finally:
            self.event_queue.put(("chat_done", ""))

    # ------------------------------------------------------------------
    # Image editing
    # ------------------------------------------------------------------
    def upload_image(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not file_path:
            return

        try:
            img = Image.open(file_path).convert("RGB")
        except Exception as exc:
            messagebox.showerror("Open image failed", str(exc))
            return

        self.current_image_path = Path(file_path)
        self.original_image = img
        self.image_path_var.set(str(self.current_image_path))
        self.reset_edits()

    def reset_edits(self) -> None:
        if self.original_image is None:
            return
        self.rotate_steps = 0
        self.flip_h = False
        self.flip_v = False
        self.grayscale_var.set(False)
        self.brightness_var.set(1.0)
        self.contrast_var.set(1.0)
        self._apply_edits()

    def rotate_left(self) -> None:
        if self.original_image is None:
            return
        self.rotate_steps = (self.rotate_steps - 1) % 4
        self._apply_edits()

    def rotate_right(self) -> None:
        if self.original_image is None:
            return
        self.rotate_steps = (self.rotate_steps + 1) % 4
        self._apply_edits()

    def toggle_flip_h(self) -> None:
        if self.original_image is None:
            return
        self.flip_h = not self.flip_h
        self._apply_edits()

    def toggle_flip_v(self) -> None:
        if self.original_image is None:
            return
        self.flip_v = not self.flip_v
        self._apply_edits()

    def _apply_edits(self) -> None:
        if self.original_image is None:
            return

        img = self.original_image.copy()

        if self.rotate_steps:
            img = img.rotate(-90 * self.rotate_steps, expand=True)
        if self.flip_h:
            img = ImageOps.mirror(img)
        if self.flip_v:
            img = ImageOps.flip(img)
        if self.grayscale_var.get():
            img = ImageOps.grayscale(img).convert("RGB")

        brightness = float(self.brightness_var.get())
        contrast = float(self.contrast_var.get())
        img = ImageEnhance.Brightness(img).enhance(brightness)
        img = ImageEnhance.Contrast(img).enhance(contrast)

        self.preview_image = img
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if self.preview_image is None:
            return

        max_w = max(self.preview_label.winfo_width() - 20, 320)
        max_h = max(self.preview_label.winfo_height() - 20, 320)

        img = self.preview_image.copy()
        img.thumbnail((max_w, max_h))

        self.preview_photo = ImageTk.PhotoImage(img)
        self.preview_label.configure(image=self.preview_photo)

    def save_image_as(self) -> None:
        if self.preview_image is None:
            messagebox.showinfo("No image", "Upload and edit an image first.")
            return

        ext_default = ".png"
        initial_name = "edited-image.png"
        if self.current_image_path:
            initial_name = f"{self.current_image_path.stem}-edited.png"

        file_path = filedialog.asksaveasfilename(
            title="Save edited image",
            defaultextension=ext_default,
            initialfile=initial_name,
            filetypes=[
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("WebP", "*.webp"),
                ("BMP", "*.bmp"),
            ],
        )
        if not file_path:
            return

        try:
            self.preview_image.save(file_path)
            messagebox.showinfo("Saved", f"Saved: {file_path}")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    # ------------------------------------------------------------------
    # Backend management
    # ------------------------------------------------------------------
    def test_connection(self) -> None:
        api_url = self.api_url_var.get().strip().rstrip("/")
        try:
            resp = requests.get(f"{api_url}/api/config", timeout=4)
            resp.raise_for_status()
            cfg = resp.json()
            backend = cfg.get("backend", "unknown")
            model = cfg.get("ollama_model") if backend == "ollama" else cfg.get("anthropic_model")
            self.status_var.set(f"Backend: connected ({backend} | {model})")
            self.backend_running = True
        except requests.RequestException as exc:
            self.status_var.set("Backend: not connected")
            self.backend_running = False
            messagebox.showwarning("Connection failed", str(exc))

    def start_backend(self) -> None:
        if self.backend_thread and self.backend_thread.is_alive():
            messagebox.showinfo("Backend", "Embedded backend is already running.")
            return

        if self.backend_process and self.backend_process.poll() is None:
            messagebox.showinfo("Backend", "Local backend is already running.")
            return

        if getattr(sys, "frozen", False):
            self._start_embedded_backend()
            return

        script_path = APP_DIR / "main.py"
        if not script_path.exists():
            messagebox.showerror("Missing backend", f"Could not find {script_path}")
            return

        try:
            self.backend_process = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(APP_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            threading.Thread(target=self._consume_backend_logs, daemon=True).start()
            threading.Thread(target=self._wait_for_backend_ready, daemon=True).start()
            self.status_var.set("Backend: starting...")
        except Exception as exc:
            messagebox.showerror("Start failed", str(exc))

    def _start_embedded_backend(self) -> None:
        try:
            import uvicorn
            import main as nexus_main
        except Exception as exc:
            messagebox.showerror("Embedded backend failed", str(exc))
            return

        self.main_module = nexus_main
        self.backend_server = uvicorn.Server(
            uvicorn.Config(
                app=nexus_main.app,
                host="127.0.0.1",
                port=8000,
                log_level="warning",
            )
        )

        def run_server() -> None:
            try:
                self.backend_server.run()
            except Exception:
                pass

        self.backend_thread = threading.Thread(target=run_server, daemon=True)
        self.backend_thread.start()
        threading.Thread(target=self._wait_for_backend_ready, daemon=True).start()
        self.status_var.set("Backend: starting (embedded)...")

    def _consume_backend_logs(self) -> None:
        if not self.backend_process or not self.backend_process.stdout:
            return
        try:
            for _line in self.backend_process.stdout:
                pass
        except Exception:
            pass

    def _wait_for_backend_ready(self) -> None:
        api_url = self.api_url_var.get().strip().rstrip("/")
        for _ in range(35):
            has_process = self.backend_process is not None
            has_thread = self.backend_thread is not None

            if not has_process and not has_thread:
                return
            if has_process and self.backend_process and self.backend_process.poll() is not None:
                self.event_queue.put(("status", "Backend: failed to start"))
                return
            if has_thread and self.backend_thread and not self.backend_thread.is_alive():
                self.event_queue.put(("status", "Backend: failed to start"))
                return
            try:
                resp = requests.get(f"{api_url}/api/config", timeout=1.5)
                if resp.ok:
                    cfg = resp.json()
                    backend = cfg.get("backend", "unknown")
                    model = cfg.get("ollama_model") if backend == "ollama" else cfg.get("anthropic_model")
                    self.event_queue.put(("status", f"Backend: connected ({backend} | {model})"))
                    return
            except requests.RequestException:
                pass
            time.sleep(0.5)
        self.event_queue.put(("status", "Backend: started but not reachable"))

    def stop_backend(self) -> None:
        if self.backend_server is not None:
            try:
                self.backend_server.should_exit = True
                self.backend_server.force_exit = True
            except Exception:
                pass

            if self.backend_thread and self.backend_thread.is_alive():
                self.backend_thread.join(timeout=3)

            self.backend_server = None
            self.backend_thread = None
            self.main_module = None
            self.backend_running = False
            self.status_var.set("Backend: stopped")
            return

        proc = self.backend_process
        if not proc or proc.poll() is not None:
            self.status_var.set("Backend: not connected")
            return

        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

        self.backend_process = None
        self.backend_running = False
        self.status_var.set("Backend: stopped")

    # ------------------------------------------------------------------
    # Event loop helpers
    # ------------------------------------------------------------------
    def _drain_ui_queue(self) -> None:
        try:
            while True:
                kind, payload = self.event_queue.get_nowait()
                if kind == "append":
                    self._append_chat(payload)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "chat_done":
                    self.chat_stream_in_progress = False
                    self.send_btn.state(["!disabled"])
                    self._append_chat("\n\n")
        except queue.Empty:
            pass

        self.after(120, self._drain_ui_queue)

    def _on_close(self) -> None:
        self.stop_backend()
        self.destroy()


if __name__ == "__main__":
    app = NexusDesktopApp()
    app.mainloop()
