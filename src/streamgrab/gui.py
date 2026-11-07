"""Native desktop interface for StreamGrab."""

from __future__ import annotations

from dataclasses import dataclass
import locale
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from streamgrab import __version__
from streamgrab.transcode import output_label
from streamgrab.gui_support import (
    AUDIO_CHOICES,
    CODEC_CHOICES,
    CONVERT_CODEC_CHOICES,
    VIDEO_FILE_TYPES,
    cli_command,
    convert_command,
    failure_detail,
    is_valid_web_url,
    parse_progress,
    remove_partial_conversions,
    terminate_tree,
    worker_environment,
    auto_update_enabled,
    load_settings,
    save_settings,
    parse_ytdlp_status,
    ytdlp_command,
)

_FFMPEG_REQUIRED = "FFmpeg가 필요합니다"
_FONT = "Segoe UI"
_PAD = 14
_COLORS = {
    "bg": "#f7f7f7",
    "surface": "#ffffff",
    "tab": "#ececec",
    "border": "#dcdcdc",
    "border_strong": "#c4c4c4",
    "text": "#1f1f1f",
    "muted": "#6b6b6b",
    "disabled": "#a8a8a8",
    "hover": "#eef3f9",
    "pressed": "#dfe8f3",
    "selected": "#dcebfa",
    "track": "#e4e4e4",
    "thumb": "#c8c8c8",
    "accent": "#0b5cad",
    "accent_hover": "#1769bd",
    "accent_pressed": "#094b8e",
    "accent_disabled": "#9db8d6",
}


@dataclass
class _ConvertItem:
    path: Path
    status: str = "대기"


class StreamGrabApp(tk.Tk):
    """Tabbed desktop shell that drives the CLI in a worker process."""

    def __init__(self) -> None:
        super().__init__()
        self.title("StreamGrab")
        self.geometry("760x660")
        self.minsize(640, 600)

        # Download tab state
        self.url = tk.StringVar()
        settings = load_settings()
        self.destination = tk.StringVar(
            value=str(settings.get("destination") or Path.home() / "Downloads")
        )
        self.download_codec = tk.StringVar(
            value=_label_for(CODEC_CHOICES, settings.get("download_codec"))
        )
        self.download_audio = tk.StringVar(
            value=_label_for(AUDIO_CHOICES, settings.get("download_audio"))
        )
        self.download_text = tk.StringVar(value="주소를 입력하고 다운로드를 시작하세요")
        self.download_percent = tk.StringVar(value="")

        # Convert tab state
        self.convert_codec = tk.StringVar(
            value=_label_for(CONVERT_CODEC_CHOICES, settings.get("convert_codec"))
        )
        self.convert_audio = tk.StringVar(
            value=_label_for(AUDIO_CHOICES, settings.get("convert_audio"))
        )
        self.convert_target = tk.StringVar(value="same")
        self.convert_hint = tk.StringVar()
        self.convert_folder = tk.StringVar(
            value=str(settings.get("convert_folder") or Path.home() / "Videos")
        )
        self.convert_text = tk.StringVar(value="변환할 영상 파일을 추가하세요")
        self.convert_percent = tk.StringVar(value="")
        self._items: dict[str, _ConvertItem] = {}
        self._convert_queue: list[str] = []
        self._convert_current: str | None = None
        self._convert_results = {"ok": 0, "failed": 0}

        self.status = tk.StringVar(value="준비")
        self.ytdlp_text = tk.StringVar(value="yt-dlp 확인 중…")

        # Worker state (one job at a time across both tabs)
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._process: subprocess.Popen[str] | None = None
        self._worker: threading.Thread | None = None
        self._job: str | None = None  # "download" | "convert" | "ffmpeg"
        self._resume_after_ffmpeg: str | None = None
        self._closing = False
        self._cancel_requested = False
        self._ytdlp_checking = False

        self._apply_theme()
        self._build_layout()
        self._square_window_corners()
        self.bind("<Control-Return>", lambda _event: self._start_current_tab())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._process_events)
        self.after(600, lambda: self._check_ytdlp(force=False, user=False))
        self.url_entry.focus_set()

    # ------------------------------------------------------------------ style
    def _apply_theme(self) -> None:
        """Flat, square-cornered theme built on ttk's 'clam' engine."""
        c = _COLORS
        self.configure(bg=c["bg"])
        style = ttk.Style(self)
        style.theme_use("clam")
        base = (_FONT, 9)

        style.configure(
            ".",
            background=c["bg"], foreground=c["text"], font=base,
            bordercolor=c["border"], lightcolor=c["bg"], darkcolor=c["bg"],
            troughcolor=c["track"], focuscolor=c["accent"],
            selectbackground=c["accent"], selectforeground="#ffffff",
            insertcolor=c["text"],
        )
        style.map(".", foreground=[("disabled", c["disabled"])])

        # Text
        style.configure("Title.TLabel", font=(_FONT, 15, "bold"))
        style.configure("Subtitle.TLabel", foreground=c["muted"])
        style.configure("Section.TLabel", font=(_FONT, 9, "bold"))
        style.configure("Hint.TLabel", font=(_FONT, 8), foreground=c["muted"])
        style.configure("Percent.TLabel", font=(_FONT, 9, "bold"), foreground=c["accent"])
        style.configure("Status.TLabel", font=(_FONT, 8), foreground=c["muted"])

        # Square bordered panels
        style.configure(
            "Card.TFrame", relief="solid", borderwidth=1,
            bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"],
        )

        # Buttons
        style.configure(
            "TButton", font=base, padding=(12, 4), relief="solid", borderwidth=1,
            background=c["surface"], bordercolor=c["border_strong"],
            lightcolor=c["surface"], darkcolor=c["surface"],
        )
        style.map(
            "TButton",
            background=[("disabled", c["bg"]), ("pressed", c["pressed"]), ("active", c["hover"])],
            lightcolor=[("pressed", c["pressed"]), ("active", c["hover"])],
            darkcolor=[("pressed", c["pressed"]), ("active", c["hover"])],
            bordercolor=[("disabled", c["border"])],
        )
        style.configure(
            "Accent.TButton", foreground="#ffffff", background=c["accent"],
            bordercolor=c["accent"], lightcolor=c["accent"], darkcolor=c["accent"],
            font=(_FONT, 9, "bold"),
        )
        style.map(
            "Accent.TButton",
            foreground=[("disabled", "#ffffff")],
            background=[("disabled", c["accent_disabled"]), ("pressed", c["accent_pressed"]),
                        ("active", c["accent_hover"])],
            bordercolor=[("disabled", c["accent_disabled"]), ("pressed", c["accent_pressed"]),
                         ("active", c["accent_hover"])],
            lightcolor=[("disabled", c["accent_disabled"]), ("pressed", c["accent_pressed"]),
                        ("active", c["accent_hover"])],
            darkcolor=[("disabled", c["accent_disabled"]), ("pressed", c["accent_pressed"]),
                       ("active", c["accent_hover"])],
        )

        # Inputs
        field = dict(
            fieldbackground=c["surface"], bordercolor=c["border_strong"],
            lightcolor=c["surface"], darkcolor=c["surface"], padding=(6, 4),
        )
        style.configure("TEntry", **field)
        style.map(
            "TEntry",
            fieldbackground=[("disabled", c["bg"])],
            bordercolor=[("focus", c["accent"])],
            lightcolor=[("focus", c["accent"])],
        )
        style.configure(
            "TCombobox", **field, background=c["surface"], arrowcolor=c["muted"],
            arrowsize=12,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", c["surface"])],
            background=[("active", c["hover"]), ("readonly", c["surface"])],
            selectbackground=[("readonly", c["surface"])],
            selectforeground=[("readonly", c["text"])],
            bordercolor=[("focus", c["accent"])],
            lightcolor=[("focus", c["accent"])],
        )
        self.option_add("*TCombobox*Listbox.font", base)
        self.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
        self.option_add("*TCombobox*Listbox.borderWidth", 0)

        style.configure("TRadiobutton", indicatorcolor=c["surface"], indicatorsize=12)
        style.map(
            "TRadiobutton",
            indicatorcolor=[("selected", c["accent"])],
            background=[("active", c["bg"])],
        )

        # Tabs: compact and flat, the selected one merges into the page
        style.configure(
            "TNotebook", background=c["bg"], borderwidth=1, tabmargins=(0, 0, 0, 0),
            bordercolor=c["border"], lightcolor=c["bg"], darkcolor=c["bg"],
        )
        style.configure(
            "TNotebook.Tab", font=base, padding=(14, 3), borderwidth=1,
            background=c["tab"], foreground=c["muted"], bordercolor=c["border"],
            lightcolor=c["tab"], darkcolor=c["tab"],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", c["bg"]), ("active", c["hover"])],
            foreground=[("selected", c["text"])],
            lightcolor=[("selected", c["bg"])],
            darkcolor=[("selected", c["bg"])],
            expand=[("selected", (0, 0, 0, 0))],
        )

        # Progress, list, scrollbars
        style.configure(
            "Treeview", font=base, rowheight=26, background=c["surface"],
            fieldbackground=c["surface"], bordercolor=c["border"],
            lightcolor=c["surface"], darkcolor=c["surface"],
        )
        style.map(
            "Treeview",
            background=[("selected", c["selected"])],
            foreground=[("selected", c["text"])],
        )
        style.configure(
            "Treeview.Heading", font=(_FONT, 9, "bold"), relief="flat", padding=(6, 4),
            background=c["tab"], bordercolor=c["border"],
            lightcolor=c["tab"], darkcolor=c["tab"],
        )
        style.map("Treeview.Heading", background=[("active", c["hover"])])
        style.configure(
            "Vertical.TScrollbar", background=c["thumb"], troughcolor=c["surface"],
            bordercolor=c["surface"], lightcolor=c["thumb"], darkcolor=c["thumb"],
            arrowcolor=c["muted"], arrowsize=12, gripcount=0,
        )
        style.map("Vertical.TScrollbar", background=[("active", c["muted"])])
        style.configure("TSeparator", background=c["border"])
        style.configure(
            "Link.TButton", font=(_FONT, 8, "underline"), foreground=c["accent"],
            background=c["bg"], bordercolor=c["bg"], lightcolor=c["bg"],
            darkcolor=c["bg"], relief="flat", padding=(6, 0),
        )
        style.map(
            "Link.TButton",
            background=[("active", c["bg"]), ("pressed", c["bg"]), ("disabled", c["bg"])],
            lightcolor=[("active", c["bg"]), ("pressed", c["bg"])],
            darkcolor=[("active", c["bg"]), ("pressed", c["bg"])],
            bordercolor=[("disabled", c["bg"])],
            foreground=[("disabled", c["disabled"]), ("active", c["accent_hover"])],
        )

    def _card(self, parent: tk.Misc) -> ttk.Frame:
        return ttk.Frame(parent, style="Card.TFrame", padding=_PAD)

    def _square_window_corners(self) -> None:
        """Ask Windows 11 not to round this window's corners."""
        if os.name != "nt":
            return
        try:
            import ctypes

            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            preference = ctypes.c_int(1)  # DWMWCP_DONOTROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference)
            )  # 33 = DWMWA_WINDOW_CORNER_PREFERENCE
        except (AttributeError, OSError):
            pass

    # ----------------------------------------------------------------- layout
    def _build_layout(self) -> None:
        # Pack the status bar first so it keeps its space when the window shrinks.
        statusbar = ttk.Frame(self, padding=(20, 4, 20, 8))
        statusbar.pack(fill="x", side="bottom")
        ttk.Separator(self).pack(fill="x", side="bottom")
        ttk.Label(statusbar, textvariable=self.status, style="Status.TLabel").pack(side="left")
        self.ytdlp_button = ttk.Button(
            statusbar, text="업데이트 확인", style="Link.TButton",
            command=lambda: self._check_ytdlp(force=True, user=True),
        )
        self.ytdlp_button.pack(side="right")
        ttk.Label(statusbar, textvariable=self.ytdlp_text, style="Status.TLabel").pack(side="right")
        ttk.Label(
            statusbar, text=f"StreamGrab {__version__}  ·  ", style="Status.TLabel"
        ).pack(side="right")

        root = ttk.Frame(self, padding=(20, 16, 20, 8))
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="StreamGrab", style="Title.TLabel").pack(side="left")
        ttk.Label(
            header, text="  웹 영상 다운로드 · 코덱 변환", style="Subtitle.TLabel"
        ).pack(side="left", pady=(8, 0))

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)
        download_tab = ttk.Frame(self.notebook, padding=(4, 14, 4, 4))
        convert_tab = ttk.Frame(self.notebook, padding=(4, 14, 4, 4))
        self.notebook.add(download_tab, text="다운로드")
        self.notebook.add(convert_tab, text="코덱 변환")
        self._build_download_tab(download_tab)
        self._build_convert_tab(convert_tab)

    def _build_download_tab(self, tab: ttk.Frame) -> None:
        form = self._card(tab)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="영상 주소").grid(row=0, column=0, sticky="w", padx=(0, 14))
        self.url_entry = ttk.Entry(form, textvariable=self.url)
        self.url_entry.grid(row=0, column=1, sticky="ew")
        ttk.Button(form, text="붙여넣기", command=self._paste_url, width=9).grid(
            row=0, column=2, padx=(8, 0)
        )

        ttk.Label(form, text="저장 폴더").grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(form, textvariable=self.destination).grid(
            row=1, column=1, sticky="ew", pady=(12, 0)
        )
        ttk.Button(form, text="찾아보기", command=self._choose_destination, width=9).grid(
            row=1, column=2, padx=(8, 0), pady=(12, 0)
        )

        ttk.Label(form, text="코덱").grid(row=2, column=0, sticky="w", pady=(12, 0))
        self._codec_row(form, self.download_codec, CODEC_CHOICES, self.download_audio).grid(
            row=2, column=1, columnspan=2, sticky="w", pady=(12, 0)
        )
        ttk.Label(
            form,
            text="TV에서 화면이 안 나오면 H.264, 소리가 안 나오면 MP3를 고르세요. 받은 뒤 자동 변환합니다.",
            style="Hint.TLabel",
        ).grid(row=3, column=1, columnspan=2, sticky="w", pady=(6, 0))

        progress_card = self._card(tab)
        progress_card.pack(fill="x", pady=(14, 0))
        top = ttk.Frame(progress_card)
        top.pack(fill="x")
        ttk.Label(top, textvariable=self.download_text).pack(side="left")
        ttk.Label(top, textvariable=self.download_percent, style="Percent.TLabel").pack(side="right")
        self.download_bar = _ThinBar(progress_card)
        self.download_bar.pack(fill="x", pady=(10, 0))

        actions = ttk.Frame(tab)
        actions.pack(fill="x", side="bottom", pady=(14, 0))
        ttk.Button(actions, text="폴더 열기", command=lambda: self._open_folder(self.destination.get())).pack(side="left")
        self.download_button = ttk.Button(
            actions, text="다운로드 시작", style="Accent.TButton", command=self._start_download, width=14
        )
        self.download_button.pack(side="right")
        self.download_cancel = ttk.Button(actions, text="취소", command=self._cancel, state="disabled", width=8)
        self.download_cancel.pack(side="right", padx=8)

    def _build_convert_tab(self, tab: ttk.Frame) -> None:
        list_card = self._card(tab)
        list_card.pack(fill="both", expand=True)

        toolbar = ttk.Frame(list_card)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Label(toolbar, text="변환할 파일", style="Section.TLabel").pack(side="left")
        self.clear_button = ttk.Button(toolbar, text="목록 비우기", command=self._clear_files)
        self.clear_button.pack(side="right")
        self.remove_button = ttk.Button(toolbar, text="선택 제거", command=self._remove_selected)
        self.remove_button.pack(side="right", padx=6)
        self.add_button = ttk.Button(toolbar, text="파일 추가…", command=self._add_files)
        self.add_button.pack(side="right")

        table = ttk.Frame(list_card)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            table, columns=("name", "codec", "size", "status"), show="headings", height=4
        )
        for column, title, width, anchor, stretch in (
            ("name", "파일", 300, "w", True),
            ("codec", "현재 코덱", 90, "center", False),
            ("size", "크기", 90, "e", False),
            ("status", "상태", 120, "center", False),
        ):
            self.tree.heading(column, text=title, anchor=anchor)
            self.tree.column(column, width=width, anchor=anchor, stretch=stretch)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Delete>", lambda _event: self._remove_selected())

        options = self._card(tab)
        options.pack(fill="x", pady=(14, 0))
        options.columnconfigure(2, weight=1)
        ttk.Label(options, text="변환 코덱").grid(row=0, column=0, sticky="w", padx=(0, 14))
        self._codec_row(options, self.convert_codec, CONVERT_CODEC_CHOICES, self.convert_audio).grid(
            row=0, column=1, columnspan=3, sticky="w"
        )

        ttk.Label(options, text="저장 위치").grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Radiobutton(
            options, text="원본과 같은 폴더", value="same",
            variable=self.convert_target, command=self._sync_target_state,
        ).grid(row=1, column=1, sticky="w", pady=(12, 0))
        ttk.Radiobutton(
            options, text="다른 폴더", value="folder",
            variable=self.convert_target, command=self._sync_target_state,
        ).grid(row=2, column=1, sticky="w", pady=(6, 0))
        self.convert_folder_entry = ttk.Entry(options, textvariable=self.convert_folder)
        self.convert_folder_entry.grid(row=2, column=2, sticky="ew", padx=(8, 0), pady=(6, 0))
        self.convert_folder_button = ttk.Button(
            options, text="찾아보기", command=self._choose_convert_folder, width=9
        )
        self.convert_folder_button.grid(row=2, column=3, padx=(8, 0), pady=(6, 0))
        ttk.Label(options, textvariable=self.convert_hint, style="Hint.TLabel").grid(
            row=3, column=1, columnspan=3, sticky="w", pady=(8, 0)
        )
        for variable in (self.convert_codec, self.convert_audio):
            variable.trace_add("write", lambda *_args: self._sync_convert_hint())
        self._sync_convert_hint()
        self._sync_target_state()

        progress = ttk.Frame(tab)
        progress.pack(fill="x", pady=(14, 0))
        top = ttk.Frame(progress)
        top.pack(fill="x")
        ttk.Label(top, textvariable=self.convert_text).pack(side="left")
        ttk.Label(top, textvariable=self.convert_percent, style="Percent.TLabel").pack(side="right")
        self.convert_bar = _ThinBar(progress)
        self.convert_bar.pack(fill="x", pady=(8, 0))

        actions = ttk.Frame(tab)
        actions.pack(fill="x", side="bottom", pady=(14, 0))
        ttk.Button(actions, text="폴더 열기", command=self._open_convert_folder).pack(side="left")
        self.convert_button = ttk.Button(
            actions, text="변환 시작", style="Accent.TButton", command=self._start_convert, width=14
        )
        self.convert_button.pack(side="right")
        self.convert_cancel = ttk.Button(actions, text="취소", command=self._cancel, state="disabled", width=8)
        self.convert_cancel.pack(side="right", padx=8)

        # Bottom sections keep their size; the file list takes what is left.
        for widget in (list_card, options, progress, actions):
            widget.pack_forget()
        actions.pack(fill="x", side="bottom", pady=(14, 0))
        progress.pack(fill="x", side="bottom", pady=(14, 0))
        options.pack(fill="x", side="bottom", pady=(14, 0))
        list_card.pack(fill="both", expand=True)

    # ------------------------------------------------------------ small UI bits
    def _start_current_tab(self) -> None:
        if self.notebook.index("current") == 0:
            self._start_download()
        else:
            self._start_convert()

    def _paste_url(self) -> None:
        try:
            self.url.set(self.clipboard_get().strip())
        except tk.TclError:
            self.status.set("클립보드에 텍스트가 없습니다")

    def _choose_destination(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.destination.get() or str(Path.home()))
        if selected:
            self.destination.set(selected)

    def _choose_convert_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.convert_folder.get() or str(Path.home()))
        if selected:
            self.convert_folder.set(selected)
            self.convert_target.set("folder")
            self._sync_target_state()

    def _codec_row(
        self,
        parent: tk.Misc,
        video: tk.StringVar,
        video_choices: dict[str, str],
        audio: tk.StringVar,
    ) -> ttk.Frame:
        row = ttk.Frame(parent)
        ttk.Combobox(
            row, textvariable=video, values=list(video_choices), state="readonly", width=27,
        ).pack(side="left")
        ttk.Label(row, text="오디오").pack(side="left", padx=(14, 8))
        ttk.Combobox(
            row, textvariable=audio, values=list(AUDIO_CHOICES), state="readonly", width=30,
        ).pack(side="left")
        return row

    def _sync_convert_hint(self) -> None:
        label = output_label(
            CONVERT_CODEC_CHOICES[self.convert_codec.get()], AUDIO_CHOICES[self.convert_audio.get()]
        )
        self.convert_hint.set(f"원본 파일은 그대로 두고 '파일명 ({label}).mp4' 형식의 새 파일을 만듭니다.")

    def _save_settings(self) -> None:
        save_settings({
            "destination": self.destination.get().strip(),
            "download_codec": CODEC_CHOICES[self.download_codec.get()],
            "download_audio": AUDIO_CHOICES[self.download_audio.get()],
            "convert_codec": CONVERT_CODEC_CHOICES[self.convert_codec.get()],
            "convert_audio": AUDIO_CHOICES[self.convert_audio.get()],
            "convert_folder": self.convert_folder.get().strip(),
        })

    def _sync_target_state(self) -> None:
        state = "normal" if self.convert_target.get() == "folder" else "disabled"
        self.convert_folder_entry.configure(state=state)
        self.convert_folder_button.configure(state=state)

    def _open_convert_folder(self) -> None:
        if self.convert_target.get() == "folder":
            self._open_folder(self.convert_folder.get())
        elif self._items:
            self._open_folder(str(next(iter(self._items.values())).path.parent))
        else:
            self.status.set("목록에 파일이 없습니다")

    def _open_folder(self, folder: str) -> None:
        path = Path(folder).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as error:
            messagebox.showerror("폴더 열기", str(error))

    def _set_busy(self, busy: bool) -> None:
        idle = "disabled" if busy else "normal"
        for button in (self.download_button, self.convert_button, self.add_button,
                       self.remove_button, self.clear_button):
            button.configure(state=idle)
        cancel_state = "normal" if busy and self._job in {"download", "convert"} else "disabled"
        self.download_cancel.configure(state=cancel_state if self._job == "download" else "disabled")
        self.convert_cancel.configure(state=cancel_state if self._job == "convert" else "disabled")

    @staticmethod
    def _set_bar(bar: _ThinBar, value: float | None) -> None:
        """None shows an animated bar while the worker has no percentage yet."""
        if value is None:
            bar.pulse()
        else:
            bar.set(value)

    # ------------------------------------------------------------- file list
    def _add_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="변환할 영상 선택", filetypes=VIDEO_FILE_TYPES
        )
        known = {item.path for item in self._items.values()}
        added = 0
        for name in selected:
            path = Path(name)
            if path in known:
                continue
            try:
                size = _human_size(path.stat().st_size)
            except OSError:
                size = "-"
            iid = self.tree.insert("", "end", values=(path.name, "확인 중", size, "대기"))
            self._items[iid] = _ConvertItem(path)
            threading.Thread(target=self._probe_codec, args=(iid, path), daemon=True).start()
            added += 1
        if added:
            self.convert_text.set(f"{len(self._items)}개 파일 · 변환 준비 완료")
            self.status.set(f"파일 {added}개를 추가했습니다")

    def _probe_codec(self, iid: str, path: Path) -> None:
        from streamgrab.transcode import probe_video_codec

        self._events.put(("codec", (iid, probe_video_codec(path) or "-")))

    def _remove_selected(self) -> None:
        if self._job == "convert":
            return
        for iid in self.tree.selection():
            self.tree.delete(iid)
            self._items.pop(iid, None)

    def _clear_files(self) -> None:
        if self._job == "convert":
            return
        self.tree.delete(*self.tree.get_children())
        self._items.clear()
        self.convert_text.set("변환할 영상 파일을 추가하세요")
        self.convert_percent.set("")
        self._set_bar(self.convert_bar, 0)

    def _set_item_status(self, iid: str, status: str) -> None:
        if iid in self._items and self.tree.exists(iid):
            self._items[iid].status = status
            self.tree.set(iid, "status", status)

    # ----------------------------------------------------------------- download
    def _start_download(self) -> None:
        if self._job is not None:
            self.status.set("다른 작업이 진행 중입니다")
            return
        url = self.url.get().strip()
        if not is_valid_web_url(url):
            messagebox.showwarning("주소 확인", "http:// 또는 https://로 시작하는 올바른 주소를 입력하세요.")
            self.url_entry.focus_set()
            return
        destination = Path(self.destination.get().strip()).expanduser()
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror("경로 오류", f"저장 폴더를 만들 수 없습니다.\n{error}")
            return

        codec = CODEC_CHOICES[self.download_codec.get()]
        audio = AUDIO_CHOICES[self.download_audio.get()]
        self._save_settings()
        self._job = "download"
        self._set_busy(True)
        self._set_bar(self.download_bar, None)
        self.download_text.set("영상 정보를 확인하고 있습니다…")
        self.download_percent.set("")
        self.status.set("다운로드 준비 중")
        self._launch(cli_command(url, destination, codec, audio))

    def _download_line(self, line: str) -> None:
        progress = parse_progress(line)
        if progress:
            kind, percent = progress
            self._set_bar(self.download_bar, percent)
            self.download_percent.set(f"{percent:.0f}%")
            self.download_text.set("코덱 변환 중" if kind == "변환" else "다운로드 중")
            self.status.set("코덱 변환 중" if kind == "변환" else "다운로드 중")
        elif "로 변환 시작" in line:
            self._set_bar(self.download_bar, 0)
            self.download_percent.set("")
            self.download_text.set(line.strip().split(":", 1)[0] + "…")
        elif "후처리" in line or "병합" in line:
            self._set_bar(self.download_bar, None)
            self.download_text.set("영상과 음성을 합치고 있습니다…")
        elif line.startswith("저장 시작:"):
            self.download_text.set(_shorten(line.strip(), 70))

    def _finish_download(self, code: int, output: str, cancelled: bool) -> None:
        if code != 0 and not cancelled and _FFMPEG_REQUIRED in output:
            self._set_bar(self.download_bar, 0)
            self._offer_ffmpeg_install("download")
            return
        if code == 0:
            self._set_bar(self.download_bar, 100)
            self.download_percent.set("100%")
            self.download_text.set("다운로드가 완료되었습니다")
            self.status.set("완료")
            return
        self._set_bar(self.download_bar, 0)
        self.download_percent.set("")
        if cancelled:
            remove_partial_conversions(Path(self.destination.get()).expanduser())
            self.download_text.set("다운로드를 취소했습니다")
            self.status.set("취소됨")
        else:
            self.download_text.set("다운로드에 실패했습니다")
            self.status.set("실패")
            messagebox.showerror("다운로드 실패", failure_detail(output) or "다운로드 중 오류가 발생했습니다.")

    # ------------------------------------------------------------------ convert
    def _start_convert(self) -> None:
        if self._job is not None:
            self.status.set("다른 작업이 진행 중입니다")
            return
        pending = [iid for iid, item in self._items.items() if item.status != "완료"]
        if not pending:
            if self._items:
                self.status.set("모든 파일이 이미 변환되었습니다")
            else:
                self._add_files()
            return
        if self.convert_target.get() == "folder":
            folder = Path(self.convert_folder.get().strip()).expanduser()
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                messagebox.showerror("경로 오류", f"저장 폴더를 만들 수 없습니다.\n{error}")
                return
        for iid in pending:
            self._set_item_status(iid, "대기")
        self._save_settings()
        self._convert_queue = pending
        self._convert_results = {"ok": 0, "failed": 0}
        self._job = "convert"
        self._set_busy(True)
        self._convert_next()

    def _convert_target_folder(self) -> Path | None:
        if self.convert_target.get() == "folder":
            return Path(self.convert_folder.get().strip()).expanduser()
        return None

    def _convert_next(self) -> None:
        if not self._convert_queue:
            self._finish_convert_batch()
            return
        iid = self._convert_queue.pop(0)
        item = self._items.get(iid)
        if item is None:
            self._convert_next()
            return
        self._convert_current = iid
        done = self._convert_results["ok"] + self._convert_results["failed"]
        total = done + len(self._convert_queue) + 1
        self._set_item_status(iid, "변환 중")
        self.tree.see(iid)
        self._set_bar(self.convert_bar, None)
        self.convert_percent.set("")
        self.convert_text.set(f"{done + 1}/{total} · {_shorten(item.path.name, 50)}")
        self.status.set("코덱 변환 중")
        codec = CONVERT_CODEC_CHOICES[self.convert_codec.get()]
        audio = AUDIO_CHOICES[self.convert_audio.get()]
        self._launch(convert_command(item.path, codec, self._convert_target_folder(), audio))

    def _convert_line(self, line: str) -> None:
        progress = parse_progress(line)
        if progress and self._convert_current:
            percent = progress[1]
            self._set_bar(self.convert_bar, percent)
            self.convert_percent.set(f"{percent:.0f}%")
            self._set_item_status(self._convert_current, f"변환 중 {percent:.0f}%")

    def _finish_convert_item(self, code: int, output: str, cancelled: bool) -> None:
        iid = self._convert_current
        self._convert_current = None
        if code != 0 and not cancelled and _FFMPEG_REQUIRED in output:
            if iid:
                self._set_item_status(iid, "대기")
            self._convert_queue.clear()
            self._set_bar(self.convert_bar, 0)
            self._offer_ffmpeg_install("convert")
            return
        if cancelled:
            if iid:
                self._set_item_status(iid, "취소됨")
                item = self._items.get(iid)
                remove_partial_conversions(self._convert_target_folder() or item.path.parent)  # type: ignore[union-attr]
            for pending in self._convert_queue:
                self._set_item_status(pending, "대기")
            self._convert_queue.clear()
            self._job = None
            self._set_busy(False)
            self._set_bar(self.convert_bar, 0)
            self.convert_percent.set("")
            self.convert_text.set("변환을 취소했습니다")
            self.status.set("취소됨")
            return
        if code == 0:
            self._convert_results["ok"] += 1
            if iid:
                self._set_item_status(iid, "완료")
        else:
            self._convert_results["failed"] += 1
            if iid:
                self._set_item_status(iid, "실패")
                name = self._items[iid].path.name if iid in self._items else ""
                self._last_convert_error = f"{name}\n\n{failure_detail(output)}"
        self._job = "convert"
        self._convert_next()

    def _finish_convert_batch(self) -> None:
        self._job = None
        self._set_busy(False)
        ok, failed = self._convert_results["ok"], self._convert_results["failed"]
        self._set_bar(self.convert_bar, 100 if ok and not failed else 0)
        self.convert_percent.set("100%" if ok and not failed else "")
        summary = f"변환 완료 {ok}개" + (f" · 실패 {failed}개" if failed else "")
        self.convert_text.set(summary)
        self.status.set(summary)
        if failed:
            messagebox.showerror(
                "변환 실패",
                f"{failed}개 파일을 변환하지 못했습니다.\n\n마지막 오류:\n"
                + getattr(self, "_last_convert_error", ""),
            )

    # ---------------------------------------------------------- worker process
    def _launch(self, command: list[str]) -> None:
        self._cancel_requested = False
        self._worker = threading.Thread(target=self._run_worker, args=(command,), daemon=True)
        self._worker.start()

    def _run_worker(self, command: list[str]) -> None:
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=worker_environment(),
                bufsize=1,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
            self._process = process
            if self._cancel_requested:
                terminate_tree(process)
            output: list[str] = []
            assert process.stdout is not None
            while chunk := process.stdout.readline():
                output.append(chunk)
                self._events.put(("line", chunk))
            code = process.wait()
            self._events.put(("finished", (code, "".join(output))))
        except OSError as error:
            self._events.put(("finished", (1, str(error))))

    def _process_events(self) -> None:
        try:
            while True:
                event, value = self._events.get_nowait()
                if event == "line":
                    if self._job == "download":
                        self._download_line(str(value))
                    elif self._job == "convert":
                        self._convert_line(str(value))
                elif event == "finished":
                    code, output = value  # type: ignore[misc]
                    self._on_worker_finished(int(code), str(output))
                elif event == "codec":
                    iid, codec = value  # type: ignore[misc]
                    if self.tree.exists(iid):
                        self.tree.set(iid, "codec", codec)
                elif event == "ffmpeg_installed":
                    success, output = value  # type: ignore[misc]
                    self._finish_ffmpeg_install(bool(success), str(output))
                elif event == "ytdlp":
                    status, user = value  # type: ignore[misc]
                    self._finish_ytdlp_check(status, bool(user))
        except queue.Empty:
            pass
        if not self._closing:
            self.after(100, self._process_events)

    def _on_worker_finished(self, code: int, output: str) -> None:
        cancelled = self._cancel_requested
        self._process = None
        job = self._job
        if job == "download":
            self._job = None
            self._set_busy(False)
            self._finish_download(code, output, cancelled)
        elif job == "convert":
            self._finish_convert_item(code, output, cancelled)

    def _cancel(self) -> None:
        if self._job not in {"download", "convert"}:
            return
        self._cancel_requested = True
        self.status.set("취소 중")
        if self._job == "download":
            self.download_text.set("다운로드를 취소하고 있습니다…")
        else:
            self.convert_text.set("변환을 취소하고 있습니다…")
        process = self._process
        if process is not None:
            terminate_tree(process)

    # ------------------------------------------------------------------- ffmpeg
    def _offer_ffmpeg_install(self, resume: str) -> None:
        self._job = None
        self._set_busy(False)
        self.status.set("FFmpeg 설치 필요")
        should_install = messagebox.askyesno(
            "FFmpeg 설치",
            "이 작업에는 FFmpeg가 필요합니다.\n\n"
            "지금 자동으로 설치한 뒤 작업을 이어서 진행할까요?",
        )
        if not should_install:
            self.status.set("FFmpeg가 없어 작업을 중단했습니다")
            return
        self._resume_after_ffmpeg = resume
        self._job = "ffmpeg"
        self._set_busy(True)
        bar, text = (
            (self.download_bar, self.download_text)
            if resume == "download"
            else (self.convert_bar, self.convert_text)
        )
        self._set_bar(bar, None)
        text.set("FFmpeg를 설치하고 있습니다…")
        self.status.set("FFmpeg 설치 중")
        self._worker = threading.Thread(target=self._install_ffmpeg, daemon=True)
        self._worker.start()

    def _install_ffmpeg(self) -> None:
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        command = [
            "winget", "install", "--id", "Gyan.FFmpeg", "-e",
            "--accept-package-agreements", "--accept-source-agreements",
            "--disable-interactivity", "--silent",
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
        resume = self._resume_after_ffmpeg
        self._resume_after_ffmpeg = None
        self._job = None
        self._set_busy(False)
        self._set_bar(self.download_bar, 0)
        self._set_bar(self.convert_bar, 0)
        if success:
            self.status.set("FFmpeg 설치 완료 · 작업을 다시 시작합니다")
            self.after(250, self._start_download if resume == "download" else self._start_convert)
            return
        self.status.set("FFmpeg 설치 실패")
        messagebox.showerror(
            "FFmpeg 설치 실패",
            "Windows 패키지 관리자(winget)로 FFmpeg를 설치하지 못했습니다.\n\n"
            + (failure_detail(output) or "Microsoft Store에서 앱 설치 관리자를 업데이트해 주세요."),
        )

    # ------------------------------------------------------------------ yt-dlp
    def _check_ytdlp(self, *, force: bool, user: bool) -> None:
        """Show the active yt-dlp and, in the packaged app, keep it updated."""
        if self._ytdlp_checking:
            return
        self._ytdlp_checking = True
        self.ytdlp_button.configure(state="disabled")
        if user:
            self.ytdlp_text.set("yt-dlp 업데이트 확인 중…")
        threading.Thread(
            target=self._run_ytdlp_check,
            args=(ytdlp_command(force=force, update=user or auto_update_enabled()), user),
            daemon=True,
        ).start()

    def _run_ytdlp_check(self, command: list[str], user: bool) -> None:
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=worker_environment(),
                timeout=600,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
            status = parse_ytdlp_status(result.stdout) or {
                "message": failure_detail(result.stdout + result.stderr) or "yt-dlp 상태를 확인하지 못했습니다",
            }
        except (OSError, subprocess.TimeoutExpired) as error:
            status = {"message": f"yt-dlp 상태를 확인하지 못했습니다: {error}"}
        self._events.put(("ytdlp", (status, user)))

    def _finish_ytdlp_check(self, status: dict, user: bool) -> None:
        self._ytdlp_checking = False
        self.ytdlp_button.configure(state="normal")
        active = status.get("active")
        if active:
            suffix = " (내장)" if status.get("source") == "bundled" else ""
            self.ytdlp_text.set(f"yt-dlp {active}{suffix}")
        else:
            self.ytdlp_text.set("yt-dlp 알 수 없음")
        message = str(status.get("message") or "")
        if status.get("updated") or user or "실패" in message:
            if message and self._job is None:
                self.status.set(message)

    def _on_close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            if not messagebox.askyesno("종료", "작업이 진행 중입니다. 취소하고 종료할까요?"):
                return
            terminate_tree(self._process)
        self._closing = True
        self.destroy()


class _ThinBar(tk.Canvas):
    """Slim square progress bar (ttk's clam bar cannot be made thinner)."""

    _HEIGHT = 5

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(
            parent, height=self._HEIGHT, highlightthickness=0, bd=0,
            background=_COLORS["track"],
        )
        self._fill = self.create_rectangle(0, 0, 0, self._HEIGHT, width=0, fill=_COLORS["accent"])
        self._value = 0.0
        self._pulse_at: float | None = None
        self._job: str | None = None
        self.bind("<Configure>", lambda _event: self._draw())

    def set(self, value: float) -> None:
        self._stop_pulse()
        self._value = max(0.0, min(100.0, float(value)))
        self._draw()

    def pulse(self) -> None:
        if self._pulse_at is None:
            self._pulse_at = 0.0
            self._animate()

    def _stop_pulse(self) -> None:
        self._pulse_at = None
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def _animate(self) -> None:
        if self._pulse_at is None:
            return
        self._pulse_at = (self._pulse_at + 0.012) % 1.3
        self._draw()
        self._job = self.after(16, self._animate)

    def _draw(self) -> None:
        width = self.winfo_width()
        if self._pulse_at is not None:
            start = (self._pulse_at - 0.3) * width
            self.coords(self._fill, max(0, start), 0, min(width, start + 0.3 * width), self._HEIGHT)
        else:
            self.coords(self._fill, 0, 0, width * self._value / 100, self._HEIGHT)


def _label_for(choices: dict[str, str], value: object) -> str:
    """Combobox label for a saved codec key, falling back to the first choice."""
    for label, key in choices.items():
        if key == value:
            return label
    return next(iter(choices))


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return "-"


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main() -> None:
    # A frozen GUI executable re-enters itself in CLI mode for each job.
    # Keeping the worker out of the Tk process makes cancellation reliable and
    # prevents network/FFmpeg work from freezing the window.
    if sys.argv[1:2] == ["--cli"]:
        from streamgrab.ytdlp_runtime import handle_runtime_args

        # Pick the newest yt-dlp (external folder or bundled) before the CLI
        # imports it; also serves the update/self-test commands.
        handled = handle_runtime_args(sys.argv[2:])
        if handled is not None:
            raise SystemExit(handled)
        from streamgrab.cli import main as cli_main

        raise SystemExit(cli_main(sys.argv[2:]))
    app = StreamGrabApp()
    app.mainloop()


if __name__ == "__main__":
    main()
