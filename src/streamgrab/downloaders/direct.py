"""Downloader for direct MP4 and WebM resources."""

from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from streamgrab.exceptions import DownloadError
from streamgrab.models import StreamInfo
from streamgrab.network import USER_AGENT


def download_direct(stream: StreamInfo, destination: Path, timeout: float) -> None:
    headers = {"User-Agent": USER_AGENT}
    if stream.referer:
        headers["Referer"] = stream.referer
    request = Request(stream.url, headers=headers)
    temporary = destination.with_suffix(f"{destination.suffix}.part")
    temporary_created = False

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        # A cancelled process can leave a partial file behind. Reusing the
        # destination must restart cleanly instead of failing with FileExistsError.
        with urlopen(request, timeout=timeout) as response, temporary.open("wb") as file:
            temporary_created = True
            while chunk := response.read(1024 * 1024):
                file.write(chunk)
        temporary.replace(destination)
    except (HTTPError, URLError, OSError) as error:
        if temporary_created and temporary.exists():
            temporary.unlink()
        raise DownloadError(f"직접 미디어 다운로드에 실패했습니다: {error}") from error
