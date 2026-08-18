"""yt-dlp fallback for embedded players and protected generic pages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from streamgrab.backends.ytdlp_common import (
    YtDlpProgress,
    base_options,
    format_size,
    output_template,
    redact_url_queries,
    short_codec,
)
from streamgrab.exceptions import DownloadError, StreamNotFoundError


DEFAULT_FORMAT = "bv*+ba/b"
_GENERIC_EXTRACTOR_ARGS = {"generic": {"impersonate": [""]}}


def list_generic_formats(url: str) -> None:
    info = _extract_info(url, format_selector=None)
    formats = info.get("formats") or []
    if not formats:
        raise StreamNotFoundError("보호된 페이지의 영상 형식을 찾지 못했습니다")

    print("ID     Resolution  FPS   Video codec       Audio codec       Size")
    for media_format in formats:
        video_codec = media_format.get("vcodec")
        audio_codec = media_format.get("acodec")
        if video_codec == "none" and audio_codec == "none":
            continue
        resolution = (
            "audio"
            if video_codec == "none"
            else media_format.get("resolution") or "unknown"
        )
        size = format_size(
            media_format.get("filesize") or media_format.get("filesize_approx")
        )
        print(
            f"{str(media_format.get('format_id', '?')):<6} "
            f"{resolution:<11} "
            f"{str(media_format.get('fps') or '-'):<5} "
            f"{short_codec(video_codec):<17} "
            f"{short_codec(audio_codec):<17} "
            f"{size}"
        )


def download_generic(
    url: str, output: Path, format_selector: str | None = None
) -> None:
    selector = format_selector or DEFAULT_FORMAT
    info = _extract_info(url, selector)
    progress = YtDlpProgress.from_info(info)
    template = output_template(output)
    template.parent.mkdir(parents=True, exist_ok=True)

    options = _options()
    options.update(
        {
            "format": selector,
            "outtmpl": str(template),
            "merge_output_format": "mp4",
            "overwrites": False,
            "continuedl": True,
            "windowsfilenames": True,
            "noprogress": True,
            "progress_hooks": [progress.download_hook],
            "postprocessor_hooks": [progress.postprocessor_hook],
        }
    )

    title = info.get("title") or info.get("id") or "web video"
    print(f"저장 시작: {title}")
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            result = downloader.download([url])
    except YtDlpDownloadError as error:
        progress.finish_line()
        raise DownloadError(
            "보호된 페이지 다운로드에 실패했습니다: "
            f"{redact_url_queries(str(error))}"
        ) from error

    if result != 0:
        progress.finish_line()
        raise DownloadError(f"yt-dlp가 오류 코드 {result}로 종료되었습니다")
    progress.complete()
    print(f"저장 완료: {output if output.suffix else output.resolve()}")


def _extract_info(url: str, format_selector: str | None) -> dict[str, Any]:
    options = _options()
    options["skip_download"] = True
    if format_selector:
        options["format"] = format_selector
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)
    except YtDlpDownloadError as error:
        raise StreamNotFoundError(
            "보호된 페이지에서도 영상 정보를 가져오지 못했습니다: "
            f"{redact_url_queries(str(error))}"
        ) from error
    if not info:
        raise StreamNotFoundError("보호된 페이지의 영상 정보를 찾지 못했습니다")
    return info


def _options() -> dict[str, Any]:
    options = base_options()
    options["extractor_args"] = _GENERIC_EXTRACTOR_ARGS
    return options
