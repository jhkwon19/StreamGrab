"""FFmpeg-backed HLS downloader."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urljoin, urlsplit

from streamgrab.exceptions import FFmpegError
from streamgrab.models import StreamInfo
from streamgrab.network import USER_AGENT


logger = logging.getLogger("streamgrab")


def download_hls(stream: StreamInfo, destination: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FFmpegError("HLS 저장에는 FFmpeg가 필요합니다")

    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "warning"]
    command.extend(["-user_agent", USER_AGENT])
    if stream.referer:
        command.extend(["-referer", stream.referer])
    command.extend(["-i", stream.url, "-map", "0", "-c", "copy", "-n", str(destination)])

    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except OSError as error:
        raise FFmpegError(f"FFmpeg를 실행할 수 없습니다: {error}") from error

    if result.returncode == 0:
        return

    # Some CDNs accept the same headers over HTTP/2 but reject FFmpeg's
    # HTTP/1.1 client. In that specific case curl transports the plain TS
    # segments and FFmpeg only remuxes the resulting local stream.
    if "403 Forbidden" in result.stderr:
        if destination.exists():
            destination.unlink()
        logger.info("CDN이 HTTP/2를 요구하여 호환 모드로 전환합니다")
        _download_simple_hls_over_http2(stream, destination, ffmpeg)
        return

    detail = _last_error_line(result.stderr)
    raise FFmpegError(
        f"FFmpeg가 오류 코드 {result.returncode}로 종료되었습니다{detail}"
    )


def _download_simple_hls_over_http2(
    stream: StreamInfo, destination: Path, ffmpeg: str
) -> None:
    curl = shutil.which("curl")
    if curl is None:
        raise FFmpegError(
            "CDN이 HTTP/2를 요구하지만 curl을 찾을 수 없습니다"
        )

    playlist_command = _curl_command(curl, stream)
    playlist_command.extend(
        ["--silent", "--show-error", "--max-filesize", "5242880", stream.url]
    )
    try:
        playlist_result = subprocess.run(
            playlist_command, capture_output=True, text=True
        )
    except OSError as error:
        raise FFmpegError(f"curl을 실행할 수 없습니다: {error}") from error

    if playlist_result.returncode != 0:
        detail = _last_error_line(playlist_result.stderr)
        raise FFmpegError(f"HLS 재생목록 요청에 실패했습니다{detail}")

    segment_urls = _parse_simple_media_playlist(stream.url, playlist_result.stdout)
    temporary = destination.with_suffix(f"{destination.suffix}.segments.part")
    temporary_created = False
    try:
        completed_segments = 0
        _render_segment_progress(completed_segments, len(segment_urls))
        with temporary.open("xb") as segment_file:
            temporary_created = True
            for offset in range(0, len(segment_urls), 10):
                batch = segment_urls[offset : offset + 10]
                segment_command = _curl_command(curl, stream)
                segment_command.extend(["--silent", "--show-error", *batch])
                segment_result = subprocess.run(
                    segment_command, stdout=segment_file
                )
                if segment_result.returncode != 0:
                    print(file=sys.stderr)
                    raise FFmpegError(
                        "HTTP/2 HLS 세그먼트 다운로드에 실패했습니다"
                    )
                completed_segments += len(batch)
                _render_segment_progress(completed_segments, len(segment_urls))

        logger.info("다운로드한 세그먼트를 MP4로 병합합니다")
        remux_command = [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "mpegts",
            "-i",
            str(temporary),
            "-map",
            "0",
            "-c",
            "copy",
            "-n",
            str(destination),
        ]
        remux_result = subprocess.run(remux_command)
        if remux_result.returncode != 0:
            raise FFmpegError(
                f"다운로드한 HLS 병합에 실패했습니다: {remux_result.returncode}"
            )
    except OSError as error:
        raise FFmpegError(f"HLS 임시 파일을 처리할 수 없습니다: {error}") from error
    finally:
        if temporary_created and temporary.exists():
            temporary.unlink()


def _curl_command(curl: str, stream: StreamInfo) -> list[str]:
    command = [
        curl,
        "--http2",
        "--location",
        "--fail",
        "--fail-early",
        "--user-agent",
        USER_AGENT,
    ]
    if stream.referer:
        command.extend(["--referer", stream.referer])
    return command


def _parse_simple_media_playlist(playlist_url: str, content: str) -> list[str]:
    if not content.lstrip().startswith("#EXTM3U"):
        raise FFmpegError("올바른 HLS 재생목록이 아닙니다")
    if "#EXT-X-STREAM-INF" in content:
        raise FFmpegError("HTTP/2 우회 경로에서는 HLS 마스터 목록을 아직 지원하지 않습니다")
    if "#EXT-X-KEY" in content:
        raise FFmpegError("암호화된 HLS 재생목록은 HTTP/2 우회 경로에서 지원하지 않습니다")
    if "#EXT-X-MAP" in content or "#EXT-X-BYTERANGE" in content:
        raise FFmpegError("분할 MP4 또는 byte-range HLS는 아직 지원하지 않습니다")

    urls: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        absolute = urljoin(playlist_url, line)
        parsed = urlsplit(absolute)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise FFmpegError("지원하지 않는 HLS 세그먼트 URL입니다")
        urls.append(absolute)

    if not urls:
        raise FFmpegError("HLS 세그먼트를 찾지 못했습니다")
    if len(urls) > 50_000:
        raise FFmpegError("HLS 세그먼트 수가 허용 범위를 초과합니다")
    return urls


def _last_error_line(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return f": {lines[-1]}" if lines else ""


def _render_segment_progress(completed: int, total: int) -> None:
    ratio = completed / total
    width = 30
    filled = min(width, int(ratio * width))
    bar = "#" * filled + "-" * (width - filled)
    ending = "\n" if completed >= total else ""
    print(
        f"\r다운로드 [{bar}] {ratio * 100:5.1f}%",
        end=ending,
        file=sys.stderr,
        flush=True,
    )
