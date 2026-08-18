"""Downloader selection."""

from __future__ import annotations

from pathlib import Path

from streamgrab.downloaders.direct import download_direct
from streamgrab.downloaders.hls import download_hls
from streamgrab.exceptions import UnsupportedStreamError
from streamgrab.models import StreamInfo, StreamType


def download_stream(stream: StreamInfo, destination: Path, timeout: float) -> None:
    if stream.stream_type is StreamType.DIRECT:
        download_direct(stream, destination, timeout)
    elif stream.stream_type is StreamType.HLS:
        download_hls(stream, destination)
    else:
        raise UnsupportedStreamError(f"아직 지원하지 않는 스트림: {stream.stream_type.value}")

