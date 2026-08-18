"""YouTube support delegated to the maintained yt-dlp backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yt_dlp
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from streamgrab.exceptions import DownloadError, StreamNotFoundError
from streamgrab.backends.ytdlp_common import (
    YtDlpProgress as _YouTubeProgress,
    base_options as _base_options,
    find_supported_node as _find_supported_node,
    format_size as _format_size,
    node_version as _node_version,
    output_template as _output_template,
    redact_url_queries as _redact_url_queries,
    short_codec as _short_codec,
)
DEFAULT_FORMAT = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b"
_YOUTUBE_HOSTS = {"youtube.com", "youtube-nocookie.com", "youtu.be"}


def is_youtube_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in _YOUTUBE_HOSTS)


def list_youtube_formats(url: str) -> None:
    info = _extract_info(url, format_selector=None)
    formats = info.get("formats") or []
    if not formats:
        raise StreamNotFoundError("YouTube 형식 정보를 찾지 못했습니다")

    print("ID     Resolution  FPS   Video codec       Audio codec       Size")
    for media_format in formats:
        video_codec = media_format.get("vcodec")
        audio_codec = media_format.get("acodec")
        if video_codec == "none" and audio_codec == "none":
            continue
        if video_codec == "none":
            resolution = "audio"
        else:
            resolution = media_format.get("resolution") or "unknown"
        size = _format_size(
            media_format.get("filesize") or media_format.get("filesize_approx")
        )
        print(
            f"{str(media_format.get('format_id', '?')):<6} "
            f"{resolution:<11} "
            f"{str(media_format.get('fps') or '-'):<5} "
            f"{_short_codec(video_codec):<17} "
            f"{_short_codec(audio_codec):<17} "
            f"{size}"
        )


def download_youtube(
    url: str, output: Path, format_selector: str | None = None
) -> None:
    selector = format_selector or DEFAULT_FORMAT
    info = _extract_info(url, selector)
    progress = _YouTubeProgress.from_info(info)
    output_template = _output_template(output)
    output_template.parent.mkdir(parents=True, exist_ok=True)

    options = _base_options()
    options.update(
        {
            "format": selector,
            "outtmpl": str(output_template),
            "merge_output_format": "mp4",
            "overwrites": False,
            "continuedl": True,
            "windowsfilenames": True,
            "noprogress": True,
            "progress_hooks": [progress.download_hook],
            "postprocessor_hooks": [progress.postprocessor_hook],
        }
    )

    title = info.get("title") or info.get("id") or "YouTube video"
    print(f"저장 시작: {title}")
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            result = downloader.download([url])
    except YtDlpDownloadError as error:
        progress.finish_line()
        raise DownloadError(
            f"YouTube 다운로드에 실패했습니다: {_redact_url_queries(str(error))}"
        ) from error

    if result != 0:
        progress.finish_line()
        raise DownloadError(f"YouTube 다운로드가 오류 코드 {result}로 종료되었습니다")
    progress.complete()
    print(f"저장 완료: {output if output.suffix else output.resolve()}")


def _extract_info(url: str, format_selector: str | None) -> dict[str, Any]:
    options = _base_options()
    options["skip_download"] = True
    if format_selector:
        options["format"] = format_selector
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)
    except YtDlpDownloadError as error:
        raise StreamNotFoundError(
            "YouTube 영상 정보를 가져오지 못했습니다: "
            f"{_redact_url_queries(str(error))}"
        ) from error
    if not info:
        raise StreamNotFoundError("YouTube 영상 정보를 찾지 못했습니다")
    return info
