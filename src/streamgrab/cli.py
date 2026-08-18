"""Command-line entry point for StreamGrab."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlsplit

from streamgrab import __version__
from streamgrab.config import load_config
from streamgrab.downloaders import download_stream
from streamgrab.exceptions import ConfigError, StreamGrabError, StreamNotFoundError
from streamgrab.extractors import GenericExtractor
from streamgrab.extractors.generic import detect_stream_type
from streamgrab.filenames import output_path
from streamgrab.logging import configure_logging
from streamgrab.models import StreamInfo
from streamgrab.network import fetch_page, validate_http_url


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
        type=int,
        default=1,
        metavar="ID",
        help="다운로드할 스트림 번호 (기본값: 1)",
    )
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="발견한 스트림을 표시하고 종료",
    )
    parser.add_argument("--debug", action="store_true", help="디버그 로그 활성화")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = configure_logging(args.debug)

    try:
        config = load_config(args.config)
    except ConfigError as error:
        parser.error(str(error))

    logger.debug("설정 로드 완료: %s", config)

    if not args.url:
        parser.print_help()
        return 0

    try:
        streams = _find_streams(args.url, config.network_timeout)
        if args.list_formats:
            _print_streams(streams)
            return 0
        if args.format < 1 or args.format > len(streams):
            raise StreamNotFoundError(
                f"스트림 번호는 1부터 {len(streams)} 사이여야 합니다"
            )

        selected = streams[args.format - 1]
        destination = output_path(
            selected, args.output or config.output_directory
        )
        print(f"저장 시작: {destination}")
        download_stream(selected, destination, config.network_timeout)
        print(f"저장 완료: {destination}")
        return 0
    except (StreamGrabError, OSError) as error:
        logger.error("%s", error)
        return 1


def _find_streams(url: str, timeout: float) -> list[StreamInfo]:
    validate_http_url(url)
    direct_type = detect_stream_type(url)
    if direct_type is not None:
        title = unquote(Path(urlsplit(url).path).stem) or "video"
        return [StreamInfo(url=url, title=title, stream_type=direct_type)]

    page = fetch_page(url, timeout)
    streams = GenericExtractor().extract(page.url, page.text)
    if not streams:
        raise StreamNotFoundError("지원하는 영상 스트림을 찾지 못했습니다")
    return streams


def _print_streams(streams: list[StreamInfo]) -> None:
    print("ID  Type    Title")
    for index, stream in enumerate(streams, start=1):
        print(f"{index:<3} {stream.stream_type.value:<7} {stream.title}")
