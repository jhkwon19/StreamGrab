"""Generic extraction from standard HTML media elements."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from streamgrab.models import StreamInfo, StreamType


_MEDIA_ATTRIBUTES = ("src", "data-source")


class GenericExtractor:
    """Find common media URLs without running JavaScript."""

    def extract(self, page_url: str, html: str) -> list[StreamInfo]:
        parser = _MediaHTMLParser()
        parser.feed(html)
        parser.close()

        default_title = parser.document_title or _title_from_url(page_url)
        streams: list[StreamInfo] = []
        seen: set[str] = set()

        for candidate, media_title in parser.candidates:
            absolute_url = urljoin(page_url, candidate.strip())
            parsed = urlsplit(absolute_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                continue
            stream_type = detect_stream_type(absolute_url)
            if stream_type is None or absolute_url in seen:
                continue
            seen.add(absolute_url)
            streams.append(
                StreamInfo(
                    url=absolute_url,
                    title=media_title or default_title,
                    stream_type=stream_type,
                    referer=page_url,
                )
            )

        return streams


def detect_stream_type(url: str) -> StreamType | None:
    path = urlsplit(url).path.lower()
    if path.endswith(".m3u8"):
        return StreamType.HLS
    if path.endswith(".mpd"):
        return StreamType.DASH
    if path.endswith((".mp4", ".webm")):
        return StreamType.DIRECT
    return None


class _MediaHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.candidates: list[tuple[str, str | None]] = []
        self.document_title = ""
        self._inside_title = False
        self._title_parts: list[str] = []
        self._video_title: str | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self._inside_title = True
            return
        if tag == "video":
            self._video_title = attributes.get("title")
            self._add_candidates(attributes, self._video_title)
        elif tag == "source":
            self._add_candidates(attributes, self._video_title)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._inside_title = False
            self.document_title = " ".join(self._title_parts).strip()
        elif tag == "video":
            self._video_title = None

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            stripped = data.strip()
            if stripped:
                self._title_parts.append(stripped)

    def _add_candidates(
        self, attributes: dict[str, str | None], title: str | None
    ) -> None:
        for name in _MEDIA_ATTRIBUTES:
            value = attributes.get(name)
            if value:
                self.candidates.append((value, title))


def _title_from_url(url: str) -> str:
    path_name = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    return path_name or "video"
