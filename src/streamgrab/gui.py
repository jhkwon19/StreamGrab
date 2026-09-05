"""Native desktop interface for StreamGrab."""

from __future__ import annotations

import os
from pathlib import Path
import queue
import re
import locale
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from streamgrab.gui_support import cli_command, failure_detail, is_valid_web_url


_PROGRESS_PATTERN = re.compile(r"다운로드 \[[^]]+]\s+([\d.]+)%")
_FFMPEG_REQUIRED = "HLS 저장에는 FFmpeg가 필요합니다"


class StreamGrabApp(tk.Tk):
    """Small Windows-style shell around the existing CLI."""

    def __init__(self) -> None:
        super().__init__()
        self.title("StreamGrab")
        self.geometry("680x315")
        self.minsize(560, 285)
        self.configure(bg="#f5f5f5")

        self.url = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.status = tk.StringVar(value="준비")
        self.progress_text = tk.StringVar(value="대기 중")
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._process: subprocess.Popen[str] | None = None
        self._worker: threading.Thread | None = None
        self._closing = False
        self._cancel_requested = False

        self._configure_style()
        self._build_layout()
        self.bind_all("<Control-Return>", lambda _event: self._start_download())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._process_events)
        self.url_entry.focus_set()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TButton", font=("Segoe UI", 9), padding=(9, 4))
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 9), padding=(15, 6))

    def _build_layout(self) -> None:
        content = tk.Frame(self, bg="#f5f5f5", padx=18, pady=15)
        content.pack(fill="both", expand=True)

        tk.Label(content, text="영상 주소", bg="#f5f5f5", font=("Segoe UI", 9)).pack(anchor="w")
        url_row = tk.Frame(content, bg="#f5f5f5")
        url_row.pack(fill="x", pady=(4, 11))
        self.url_entry = ttk.Entry(url_row, textvariable=self.url, font=("Segoe UI", 9))
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=3)
        ttk.Button(url_row, text="붙여넣기", command=self._paste_url).pack(side="left", padx=(7, 0))

        tk.Label(content, text="저장 경로", bg="#f5f5f5", font=("Segoe UI", 9)).pack(anchor="w")
        path_row = tk.Frame(content, bg="#f5f5f5")
        path_row.pack(fill="x", pady=(4, 12))
        self.path_entry = ttk.Entry(path_row, textvariable=self.destination, font=("Segoe UI", 9))
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=3)
        ttk.Button(path_row, text="찾아보기", command=self._choose_destination).pack(side="left", padx=(7, 0))

        progress_row = tk.Frame(content, bg="#f5f5f5")
        progress_row.pack(fill="x", pady=(1, 12))
        tk.Label(progress_row, textvariable=self.progress_text, bg="#f5f5f5", anchor="w", font=("Segoe UI", 8), fg="#555555").pack(fill="x")
        self.progress = ttk.Progressbar(progress_row, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(4, 0))

        action_row = tk.Frame(content, bg="#f5f5f5")
        action_row.pack(fill="x", side="bottom")
        ttk.Button(action_row, text="폴더 열기", command=self._open_destination).pack(side="left")
        self.start_button = ttk.Button(action_row, text="다운로드 시작", style="Primary.TButton", command=self._start_download)
        self.start_button.pack(side="right")
        self.cancel_button = ttk.Button(action_row, text="취소", command=self._cancel_download, state="disabled")
        self.cancel_button.pack(side="right", padx=8)

        statusbar = tk.Frame(self, bg="#f5f5f5", bd=1, relief="sunken")
        statusbar.pack(fill="x", side="bottom")
        tk.Label(statusbar, textvariable=self.status, bg="#f5f5f5", anchor="w", padx=7, pady=3, font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True)
        tk.Label(statusbar, text="StreamGrab 0.2.0", bg="#f5f5f5", padx=8, font=("Segoe UI", 8)).pack(side="right")

    def _choose_destination(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.destination.get() or str(Path.home()))
        if selected:
            self.destination.set(selected)

    def _paste_url(self) -> None:
        try:
            self.url.set(self.clipboard_get().strip())
        except tk.TclError:
            self.status.set("클립보드에 텍스트가 없습니다")

    def _start_download(self) -> None:
        if self._process is not None:
            self.status.set("이미 다운로드가 진행 중입니다")
            return
        url = self.url.get().strip()
        if not is_valid_web_url(url):
            messagebox.showwarning("주소 확인", "http:// 또는 https://로 시작하는 올바른 주소를 입력하세요.")
            self.url_entry.focus_set()
            return
        destination = Path(self.destination.get().strip()).expanduser()
        if not str(destination):
            messagebox.showwarning("경로 확인", "저장 경로를 선택하세요.")
            return
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror("경로 오류", f"저장 폴더를 만들 수 없습니다.\n{error}")
            return

        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self._cancel_requested = False
        self.progress_text.set("영상 정보를 확인하고 있습니다...")
        self.status.set("다운로드 준비 중")
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self._worker = threading.Thread(target=self._run_download, args=(url, destination), daemon=True)
        self._worker.start()

    def _run_download(self, url: str, destination: Path) -> None:
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        output_encoding = locale.getpreferredencoding(False) or "utf-8"
        try:
            process = subprocess.Popen(
                cli_command(url, destination),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding=output_encoding,
                errors="replace",
                bufsize=1,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
            self._process = process
            if self._cancel_requested:
                process.terminate()
            output: list[str] = []
            assert process.stdout is not None
            while chunk := process.stdout.readline():
                output.append(chunk)
                match = _PROGRESS_PATTERN.search(chunk)
                if match:
                    self._events.put(("progress", float(match.group(1))))
                elif "후처리" in chunk or "병합" in chunk:
                    self._events.put(("message", "영상 파일을 병합하고 있습니다..."))
                elif "저장 시작:" in chunk:
                    self._events.put(("message", chunk.strip()))
            code = process.wait()
            self._events.put(("finished", (code, "".join(output))))
        except OSError as error:
            self._events.put(("finished", (1, str(error))))

    def _process_events(self) -> None:
        try:
            while True:
                event, value = self._events.get_nowait()
                if event == "progress":
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=float(value))
                    self.progress_text.set(f"다운로드 중 · {float(value):.1f}%")
                    self.status.set("다운로드 중")
                elif event == "message":
                    self.progress_text.set(str(value))
                elif event == "finished":
                    code, output = value  # type: ignore[misc]
                    self._finish_download(int(code), str(output))
                elif event == "ffmpeg_installed":
                    success, output = value  # type: ignore[misc]
                    self._finish_ffmpeg_install(bool(success), str(output))
        except queue.Empty:
            pass
        if not self._closing:
            self.after(100, self._process_events)

    def _finish_download(self, code: int, output: str) -> None:
        cancelled = self._cancel_requested
        self._process = None
        self.progress.stop()
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        if code != 0 and _FFMPEG_REQUIRED in output:
            self.progress.configure(mode="determinate", value=0)
            self.progress_text.set("FFmpeg 설치가 필요합니다")
            self.status.set("추가 구성 필요")
            should_install = messagebox.askyesno(
                "FFmpeg 설치",
                "이 영상은 HLS 형식이어서 FFmpeg가 필요합니다.\n\n"
                "지금 자동으로 설치한 뒤 다운로드를 이어서 진행할까요?",
            )
            if should_install:
                self._begin_ffmpeg_install()
            return
        if code == 0:
            self.progress.configure(mode="determinate", value=100)
            self.progress_text.set("다운로드가 완료되었습니다")
            self.status.set("완료")
        else:
            self.progress.configure(mode="determinate", value=0)
            self.progress_text.set("사용자가 다운로드를 취소했습니다" if cancelled else "다운로드에 실패했습니다")
            self.status.set("취소됨" if cancelled else "실패")
            if not cancelled:
                detail = failure_detail(output)
                messagebox.showerror("다운로드 실패", detail or "다운로드 중 오류가 발생했습니다.")

    def _begin_ffmpeg_install(self) -> None:
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="disabled")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.progress_text.set("FFmpeg를 설치하고 있습니다...")
        self.status.set("FFmpeg 설치 중")
        self._worker = threading.Thread(
            target=self._install_ffmpeg, daemon=True
        )
        self._worker.start()

    def _install_ffmpeg(self) -> None:
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        command = [
            "winget",
            "install",
            "--id",
            "Gyan.FFmpeg",
            "-e",
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--disable-interactivity",
            "--silent",
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding=locale.getpreferredencoding(False),
                errors="replace",
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
            output = "\n".join(part for part in (result.stdout, result.stderr) if part)
            self._events.put(("ffmpeg_installed", (result.returncode == 0, output)))
        except OSError as error:
            self._events.put(("ffmpeg_installed", (False, str(error))))

    def _finish_ffmpeg_install(self, success: bool, output: str) -> None:
        self.progress.stop()
        self._worker = None
        if success:
            self.progress.configure(mode="determinate", value=0)
            self.progress_text.set("FFmpeg 설치 완료 · 다운로드를 다시 시작합니다")
            self.status.set("다운로드 재시작 중")
            self.start_button.configure(state="normal")
            self.after(250, self._start_download)
            return
        self.start_button.configure(state="normal")
        self.progress.configure(mode="determinate", value=0)
        self.progress_text.set("FFmpeg 자동 설치에 실패했습니다")
        self.status.set("설치 실패")
        detail = failure_detail(output)
        messagebox.showerror(
            "FFmpeg 설치 실패",
            "Windows 패키지 관리자(winget)로 FFmpeg를 설치하지 못했습니다.\n\n"
            + (detail or "Microsoft Store에서 앱 설치 관리자를 업데이트해 주세요."),
        )

    def _cancel_download(self) -> None:
        process = self._process
        worker_active = self._worker is not None and self._worker.is_alive()
        if worker_active:
            self._cancel_requested = True
            self.progress_text.set("다운로드를 취소하고 있습니다...")
            self.status.set("취소 중")
        if process is not None and process.poll() is None:
            process.terminate()

    def _open_destination(self) -> None:
        path = Path(self.destination.get()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as error:
            messagebox.showerror("폴더 열기", str(error))

    def _on_close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            if not messagebox.askyesno("종료", "다운로드가 진행 중입니다. 취소하고 종료할까요?"):
                return
            self._process.terminate()
        self._closing = True
        self.destroy()


def main() -> None:
    # A frozen GUI executable re-enters itself in CLI mode for each download.
    # Keeping the worker out of the Tk process makes cancellation reliable and
    # prevents network/extractor work from freezing the window.
    if sys.argv[1:2] == ["--cli"]:
        from streamgrab.cli import main as cli_main

        raise SystemExit(cli_main(sys.argv[2:]))
    app = StreamGrabApp()
    app.mainloop()


if __name__ == "__main__":
    main()
