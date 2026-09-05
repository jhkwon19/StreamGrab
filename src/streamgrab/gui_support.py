"""Platform-independent helpers used by the desktop interface."""

from __future__ import annotations

from pathlib import Path
import sys
from urllib.parse import urlsplit


def is_valid_web_url(value: str) -> bool:
    parsed = urlsplit(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def cli_command(url: str, destination: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--cli", url, "--output", str(destination)]
    return [sys.executable, "-m", "streamgrab", url, "--output", str(destination)]


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
        if not line.startswith("다운로드 [") and not line.startswith("저장 시작:")
    ]
    return meaningful[-1] if meaningful else (lines[-1] if lines else "")
