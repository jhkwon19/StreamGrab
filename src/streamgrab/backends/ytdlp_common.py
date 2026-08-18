"""Shared yt-dlp integration helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import logging
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any
from urllib.parse import urlsplit


logger = logging.getLogger("streamgrab")


def base_options() -> dict[str, Any]:
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": False,
        "noplaylist": True,
        "logger": YtDlpLogger(),
    }
    runtimes: dict[str, dict[str, str]] = {"deno": {}}
    supported_node = find_supported_node()
    if supported_node:
        runtimes["node"] = {"path": supported_node}
    if shutil.which("qjs"):
        runtimes["quickjs"] = {}
    options["js_runtimes"] = runtimes
    return options


@lru_cache(maxsize=1)
def find_supported_node() -> str | None:
    candidates: list[Path] = []
    active_node = shutil.which("node")
    if active_node:
        candidates.append(Path(active_node))

    nvm_versions = Path.home() / ".nvm" / "versions" / "node"
    candidates.extend(nvm_versions.glob("v*/bin/node"))

    unique_candidates = list(dict.fromkeys(candidates))
    supported = [
        (version, path)
        for path in unique_candidates
        if (version := node_version(path)) is not None and version >= (22, 0, 0)
    ]
    if not supported:
        return None
    _, selected = max(supported, key=lambda item: item[0])
    return str(selected)


def node_version(path: Path) -> tuple[int, int, int] | None:
    try:
        result = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", result.stdout.strip())
    if result.returncode != 0 or match is None:
        return None
    return tuple(int(part) for part in match.groups())


def output_template(output: Path) -> Path:
    if output.suffix:
        return output
    return output / "%(title).180B [%(id)s].%(ext)s"


def format_size(size: int | float | None) -> str:
    if not size:
        return "-"
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return "-"


def short_codec(codec: str | None) -> str:
    if not codec or codec == "none":
        return "-"
    return codec.split(".", 1)[0]


class YtDlpLogger:
    def debug(self, message: str) -> None:
        logger.debug("yt-dlp: %s", redact_url_queries(message))

    def info(self, message: str) -> None:
        logger.info("yt-dlp: %s", redact_url_queries(message))

    def warning(self, message: str) -> None:
        logger.warning("yt-dlp: %s", redact_url_queries(message))

    def error(self, message: str) -> None:
        logger.error("yt-dlp: %s", redact_url_queries(message))


@dataclass(slots=True)
class YtDlpProgress:
    totals: dict[str, int]
    downloaded: dict[str, int] = field(default_factory=dict)
    rendered: bool = False
    last_ratio: float = 0.0
    postprocessing_announced: bool = False

    @classmethod
    def from_info(cls, info: dict[str, Any]) -> YtDlpProgress:
        requested = info.get("requested_formats") or [info]
        totals: dict[str, int] = {}
        for media_format in requested:
            format_id = str(media_format.get("format_id") or "default")
            size = media_format.get("filesize") or media_format.get("filesize_approx")
            if size:
                totals[format_id] = int(size)
        return cls(totals=totals)

    def download_hook(self, status: dict[str, Any]) -> None:
        if status.get("status") not in {"downloading", "finished"}:
            return
        info = status.get("info_dict") or {}
        format_id = str(info.get("format_id") or "default")
        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        if total:
            self.totals[format_id] = int(total)
        downloaded = status.get("downloaded_bytes")
        if downloaded is not None:
            self.downloaded[format_id] = int(downloaded)
        elif status.get("status") == "finished" and format_id in self.totals:
            self.downloaded[format_id] = self.totals[format_id]
        self._render()

    def postprocessor_hook(self, status: dict[str, Any]) -> None:
        if status.get("status") == "started" and not self.postprocessing_announced:
            self.finish_line()
            logger.info("영상 후처리 또는 병합을 진행합니다")
            self.postprocessing_announced = True

    def _render(self) -> None:
        total = sum(self.totals.values())
        if total <= 0:
            return
        completed = sum(
            min(self.downloaded.get(format_id, 0), size)
            for format_id, size in self.totals.items()
        )
        ratio = max(self.last_ratio, min(1.0, completed / total))
        self.last_ratio = ratio
        width = 30
        filled = int(width * ratio)
        bar = "#" * filled + "-" * (width - filled)
        print(
            f"\r다운로드 [{bar}] {ratio * 100:5.1f}%",
            end="",
            file=sys.stderr,
            flush=True,
        )
        self.rendered = True

    def finish_line(self) -> None:
        if self.rendered:
            print(file=sys.stderr)
            self.rendered = False

    def complete(self) -> None:
        if self.totals:
            self.downloaded = dict(self.totals)
            self._render()
        self.finish_line()


_URL_PATTERN = re.compile(r"https?://[^\s\]\[<>'\"]+")


def redact_url_queries(message: str) -> str:
    def redact(match: re.Match[str]) -> str:
        url = match.group(0)
        parsed = urlsplit(url)
        return parsed._replace(query="", fragment="").geturl()

    return _URL_PATTERN.sub(redact, message)
