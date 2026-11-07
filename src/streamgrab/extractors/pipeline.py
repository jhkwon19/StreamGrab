"""Staged extraction pipeline for static pages, embeds and browser fallback."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from urllib.parse import unquote, urlsplit

from streamgrab.exceptions import NetworkError, StreamNotFoundError
from streamgrab.extractors.browser import BrowserNetworkExtractor
from streamgrab.extractors.generic import GenericExtractor, detect_stream_type
from streamgrab.extractors.mingky import MingkyExtractor, is_mingky_movie_url
from streamgrab.models import StreamInfo
from streamgrab.network import fetch_page, validate_http_url


MAX_IFRAME_DEPTH = 2
MAX_STATIC_PAGES = 8


class ExtractionPipeline:
    """Run cheap generic stages first and a real browser only on demand."""

    def extract_static(self, url: str, timeout: float) -> list[StreamInfo]:
        validate_http_url(url)
        direct_type = detect_stream_type(url)
        if direct_type is not None:
            title = unquote(Path(urlsplit(url).path).stem) or "video"
            return [StreamInfo(url=url, title=title, stream_type=direct_type)]

        generic = GenericExtractor()
        queue: deque[tuple[str, str | None, int]] = deque([(url, None, 0)])
        visited: set[str] = set()
        discovered: list[StreamInfo] = []
        last_network_error: NetworkError | None = None

        while queue and len(visited) < MAX_STATIC_PAGES:
            page_url, referer, depth = queue.popleft()
            if page_url in visited:
                continue
            visited.add(page_url)
            try:
                page = fetch_page(page_url, min(timeout, 10.0), referer=referer)
            except NetworkError as error:
                last_network_error = error
                continue

            streams = generic.extract(page.url, page.text)
            discovered.extend(streams)
            if depth < MAX_IFRAME_DEPTH:
                queue.extend(
                    (iframe, page.url, depth + 1)
                    for iframe in generic.iframe_urls(page.url, page.text)
                    if iframe not in visited
                )

        if discovered:
            return _rank(_deduplicate(discovered))
        if is_mingky_movie_url(url):
            return _rank(_deduplicate(MingkyExtractor().extract(url, timeout)))
        if last_network_error and len(visited) == 1:
            raise last_network_error
        raise StreamNotFoundError("정적 페이지와 iframe에서 영상 스트림을 찾지 못했습니다")

    def extract_browser(self, url: str, timeout: float) -> list[StreamInfo]:
        validate_http_url(url)
        streams = BrowserNetworkExtractor().extract(url, timeout)
        if not streams:
            raise StreamNotFoundError("브라우저 네트워크에서도 영상 스트림을 찾지 못했습니다")
        return _rank(_deduplicate(streams))


def _deduplicate(streams: list[StreamInfo]) -> list[StreamInfo]:
    unique: list[StreamInfo] = []
    seen: set[str] = set()
    for stream in streams:
        if stream.url in seen:
            continue
        seen.add(stream.url)
        unique.append(stream)
    return unique


def _rank(streams: list[StreamInfo]) -> list[StreamInfo]:
    priorities = {"hls": 3, "dash": 2, "direct": 1}
    return sorted(
        streams,
        key=lambda stream: priorities.get(stream.stream_type.value, 0),
        reverse=True,
    )
