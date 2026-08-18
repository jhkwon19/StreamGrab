"""Shared data models passed between extractors and downloaders."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StreamType(str, Enum):
    DIRECT = "direct"
    HLS = "hls"
    DASH = "dash"


@dataclass(frozen=True, slots=True)
class StreamInfo:
    """A media stream discovered by an extractor."""

    url: str
    title: str
    stream_type: StreamType
    referer: str | None = None

