"""Platform-independent helpers used by the desktop interface."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

# Set by the GUI on its download worker so both sides agree on UTF-8 for the
# piped output. Without it Windows falls back to the ANSI code page (cp949 on
# Korean systems), which cannot encode emoji found in many video titles.
WORKER_UTF8_ENV = "STREAMGRAB_UTF8_OUTPUT"


def worker_environment() -> dict[str, str]:
    env = dict(os.environ)
    env[WORKER_UTF8_ENV] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def configure_output_streams() -> None:
    """Never let an unencodable title or path crash a download while printing."""
    use_utf8 = os.environ.get(WORKER_UTF8_ENV) == "1"
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            if use_utf8:
                reconfigure(encoding="utf-8", errors="replace")
            else:
                reconfigure(errors="replace")
        except (ValueError, OSError):
            pass


def is_valid_web_url(value: str) -> bool:
    parsed = urlsplit(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


CODEC_CHOICES = {
    "H.264 (TV·휴대폰 호환, 권장)": "h264",
    "H.265 / HEVC (용량 절약)": "h265",
    "원본 유지 (VP9·AV1일 수 있음)": "original",
}
AUDIO_CHOICES = {
    "AAC (일반 TV·휴대폰)": "aac",
    "MP3 (주방 TV 등 AAC 미지원 기기)": "mp3",
    "AC-3 / 돌비 (방송용 TV)": "ac3",
}
CONVERT_CODEC_CHOICES = {
    label: codec for label, codec in CODEC_CHOICES.items() if codec != "original"
}
VIDEO_FILE_TYPES = (
    ("영상 파일", "*.mp4 *.mkv *.webm *.mov *.avi *.m4v *.ts *.flv *.wmv"),
    ("모든 파일", "*.*"),
)

_PROGRESS_PATTERN = re.compile(r"(다운로드|변환)(?: \[[^]]+])+\s+([\d.]+)%")


def _worker_prefix() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--cli"]
    return [sys.executable, "-m", "streamgrab"]


def settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "StreamGrab" / "settings.json"


def load_settings() -> dict:
    """Last choices in the GUI (codec, audio, folders). Missing/broken -> {}."""
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(values: dict) -> None:
    path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        pass


def auto_update_enabled() -> bool:
    """Auto-update only the packaged app; developers manage yt-dlp with pip."""
    return bool(getattr(sys, "frozen", False)) or os.environ.get("STREAMGRAB_AUTO_UPDATE") == "1"


def ytdlp_command(*, force: bool, update: bool) -> list[str]:
    if not update:
        return [*_worker_prefix(), "--ytdlp-status"]
    return [*_worker_prefix(), "--update-ytdlp", *(["--force"] if force else [])]


def parse_ytdlp_status(output: str) -> dict | None:
    from streamgrab.ytdlp_runtime import STATUS_PREFIX

    for line in reversed(output.splitlines()):
        if line.startswith(STATUS_PREFIX):
            try:
                return json.loads(line[len(STATUS_PREFIX):])
            except ValueError:
                return None
    return None


def cli_command(
    url: str, destination: Path, video_codec: str = "h264", audio_codec: str = "aac"
) -> list[str]:
    return [
        *_worker_prefix(), url, "--codec", video_codec, "--audio", audio_codec,
        "--output", str(destination),
    ]


def convert_command(
    source: Path, video_codec: str, folder: Path | None = None, audio_codec: str = "aac"
) -> list[str]:
    command = [
        *_worker_prefix(), "--convert", str(source), "--codec", video_codec,
        "--audio", audio_codec,
    ]
    if folder is not None:
        command += ["--output", str(folder)]
    return command


def parse_progress(line: str) -> tuple[str, float] | None:
    """Return ("다운로드"|"변환", percent) from a worker progress line."""
    match = _PROGRESS_PATTERN.search(line)
    if match is None:
        return None
    return match.group(1), float(match.group(2))


def terminate_tree(process: subprocess.Popen) -> None:
    """Stop the worker and its FFmpeg children (terminate() leaves them on Windows)."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        process.terminate()


def remove_partial_conversions(folder: Path) -> None:
    leftovers = [
        leftover
        for pattern in ("*.converting.mp4", "*.converting.aac", "*.converting.mp3", "*.converting.ac3")
        for leftover in folder.glob(pattern)
    ]
    for leftover in leftovers:
        try:
            leftover.unlink()
        except OSError:
            pass


def failure_detail(output: str) -> str:
    """Select the useful error from mixed buffered stdout/stderr output."""
    lines = [
        line.strip()
        for line in output.replace("\r", "\n").splitlines()
        if line.strip()
    ]
    errors = [line for line in lines if line.upper().startswith("ERROR:")]
    if errors:
        return errors[-1].split(":", 1)[1].strip()
    meaningful = [
        line
        for line in lines
        if not line.startswith(("다운로드 [", "변환 [", "저장 시작:", "변환 대상:"))
    ]
    return meaningful[-1] if meaningful else (lines[-1] if lines else "")
