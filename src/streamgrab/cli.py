"""Command-line entry point for StreamGrab."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from streamgrab import __version__
from streamgrab.backends.youtube import (
    download_youtube,
    is_youtube_url,
    list_youtube_formats,
)
from streamgrab.backends.generic_ytdlp import (
    download_generic,
    list_generic_formats,
)
from streamgrab.config import load_config
from streamgrab.downloaders import download_stream
from streamgrab.exceptions import (
    ConfigError,
    NetworkError,
    StreamGrabError,
    StreamNotFoundError,
)
from streamgrab.extractors import ExtractionPipeline
from streamgrab.filenames import output_path
from streamgrab.transcode import (
    AUDIO_CODECS,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_VIDEO_CODEC,
    VIDEO_CODECS,
    convert_file,
    ensure_video_codec,
)
from streamgrab.gui_support import configure_output_streams
from streamgrab.logging import configure_logging
from streamgrab.models import StreamInfo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="streamgrab",
        description="웹 영상 스트림을 분석하고 저장하는 도구",
    )
    parser.add_argument("url", nargs="?", help="분석할 웹페이지 또는 미디어 URL")
    parser.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        help="사용할 TOML 설정 파일",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="PATH",
        help="출력 디렉터리 또는 파일 경로",
    )
    parser.add_argument(
        "-f",
        "--format",
        default=None,
        metavar="ID",
        help="스트림 번호 또는 플랫폼 형식 ID (기본값: 최고 품질)",
    )
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="발견한 스트림을 표시하고 종료",
    )
    parser.add_argument(
        "--codec",
        choices=VIDEO_CODECS,
        default=DEFAULT_VIDEO_CODEC,
        help="저장할 영상 코덱 (기본값: h264, TV 호환). original은 변환하지 않음",
    )
    parser.add_argument(
        "--audio",
        choices=AUDIO_CODECS,
        default=DEFAULT_AUDIO_CODEC,
        help="저장할 오디오 코덱 (기본값: aac). AAC를 못 읽는 주방 TV 등은 mp3 또는 ac3",
    )
    parser.add_argument(
        "--convert",
        nargs="+",
        type=Path,
        metavar="FILE",
        help="이미 저장된 영상을 --codec 형식으로 변환 (원본은 유지, -o로 저장 폴더 지정)",
    )
    parser.add_argument("--debug", action="store_true", help="디버그 로그 활성화")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_output_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = configure_logging(args.debug)

    try:
        config = load_config(args.config)
    except ConfigError as error:
        parser.error(str(error))

    logger.debug("설정 로드 완료: %s", config)

    if args.convert:
        return _convert_files(parser, args.convert, args.codec, args.output, args.audio)

    if not args.url:
        parser.print_help()
        return 0

    try:
        if is_youtube_url(args.url):
            if args.list_formats:
                list_youtube_formats(args.url)
            else:
                download_youtube(
                    args.url,
                    args.output or config.output_directory,
                    args.format,
                    args.codec,
                    args.audio,
                )
            return 0

        try:
            streams = _find_streams(args.url, config.network_timeout)
        except (NetworkError, StreamNotFoundError):
            try:
                if args.list_formats:
                    list_generic_formats(args.url)
                else:
                    download_generic(
                        args.url,
                        args.output or config.output_directory,
                        args.format,
                        args.codec,
                        args.audio,
                    )
                return 0
            except (StreamGrabError, OSError) as backend_error:
                logger.info("yt-dlp 분석 실패 후 브라우저 네트워크 분석을 시도합니다")
                try:
                    streams = _find_browser_streams(
                        args.url, config.network_timeout
                    )
                except (StreamGrabError, OSError) as browser_error:
                    raise StreamNotFoundError(
                        "모든 자동 분석 단계에서 영상을 찾지 못했습니다. "
                        f"yt-dlp: {backend_error}; 브라우저: {browser_error}"
                    ) from browser_error
        if args.list_formats:
            _print_streams(streams)
            return 0
        format_number = _generic_format_number(args.format)
        if format_number < 1 or format_number > len(streams):
            raise StreamNotFoundError(
                f"스트림 번호는 1부터 {len(streams)} 사이여야 합니다"
            )

        selected = streams[format_number - 1]
        destination = output_path(
            selected, args.output or config.output_directory
        )
        print(f"저장 시작: {destination}", flush=True)
        download_stream(selected, destination, config.network_timeout)
        destination = ensure_video_codec(destination, args.codec, audio_codec=args.audio)
        print(f"저장 완료: {destination}", flush=True)
        return 0
    except (StreamGrabError, OSError) as error:
        logger.error("%s", error)
        return 1


def _convert_files(
    parser: argparse.ArgumentParser,
    files: Sequence[Path],
    video_codec: str,
    folder: Path | None,
    audio_codec: str = "aac",
) -> int:
    if video_codec == "original":
        parser.error("--convert에는 --codec h264 또는 --codec h265를 지정하세요")
    logger = logging.getLogger("streamgrab")
    failures = 0
    for index, source in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] {source}")
        try:
            convert_file(source, video_codec, folder, audio_codec)
        except (StreamGrabError, OSError) as error:
            failures += 1
            logger.error("%s", error)
    return 1 if failures else 0


def _find_streams(url: str, timeout: float) -> list[StreamInfo]:
    return ExtractionPipeline().extract_static(url, timeout)


def _find_browser_streams(url: str, timeout: float) -> list[StreamInfo]:
    return ExtractionPipeline().extract_browser(url, timeout)


def _print_streams(streams: list[StreamInfo]) -> None:
    print("ID  Type    Title")
    for index, stream in enumerate(streams, start=1):
        print(f"{index:<3} {stream.stream_type.value:<7} {stream.title}")


def _generic_format_number(value: str | None) -> int:
    if value is None:
        return 1
    try:
        return int(value)
    except ValueError as error:
        raise StreamNotFoundError(
            "일반 웹페이지의 형식 ID는 숫자여야 합니다"
        ) from error
