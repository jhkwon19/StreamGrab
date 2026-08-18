"""Safe output filename helpers."""

from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import urlsplit

from streamgrab.models import StreamInfo, StreamType


_INVALID_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def safe_filename(title: str, fallback: str = "video") -> str:
    cleaned = _INVALID_FILENAME.sub("_", title).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        cleaned = fallback
    if cleaned.upper() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned[:180].rstrip(" .") or fallback


def output_path(stream: StreamInfo, output: Path) -> Path:
    """Resolve an output directory or explicit filename without overwriting."""

    extension = _extension_for(stream)
    if output.suffix:
        candidate = output
    else:
        candidate = output / f"{safe_filename(stream.title)}{extension}"

    if not candidate.exists():
        return candidate

    for number in range(1, 10_000):
        alternate = candidate.with_name(
            f"{candidate.stem} ({number}){candidate.suffix}"
        )
        if not alternate.exists():
            return alternate
    raise OSError("사용 가능한 출력 파일명을 만들 수 없습니다")


def _extension_for(stream: StreamInfo) -> str:
    if stream.stream_type is StreamType.DIRECT:
        suffix = Path(urlsplit(stream.url).path).suffix.lower()
        if suffix in {".mp4", ".webm"}:
            return suffix
    return ".mp4"
