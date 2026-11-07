"""Extractor for the public movie API used by current Mingky sites."""

from __future__ import annotations

import re
from urllib.parse import quote, urljoin, urlsplit

from streamgrab.exceptions import StreamNotFoundError
from streamgrab.extractors.generic import GenericExtractor
from streamgrab.models import StreamInfo
from streamgrab.network import fetch_json, fetch_page


_HOST_PATTERN = re.compile(r"(?:www\.)?mingky\d+\.com", re.IGNORECASE)
_MOVIE_PATH_PATTERN = re.compile(r"^/movie/([^/?#]+)/*$")


def is_mingky_movie_url(url: str) -> bool:
    parsed = urlsplit(url)
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and _HOST_PATTERN.fullmatch(parsed.hostname)
        and _MOVIE_PATH_PATTERN.match(parsed.path)
    )


class MingkyExtractor:
    """Resolve a movie page through its API and embedded player page."""

    def extract(self, page_url: str, timeout: float) -> list[StreamInfo]:
        parsed = urlsplit(page_url)
        match = _MOVIE_PATH_PATTERN.match(parsed.path)
        if not match or not is_mingky_movie_url(page_url):
            return []

        movie_id = match.group(1)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        api_url = urljoin(origin, f"/api/movies/{quote(movie_id, safe='')}")
        metadata = fetch_json(api_url, timeout, referer=page_url)
        if not isinstance(metadata, dict) or metadata.get("ok") is False:
            raise StreamNotFoundError("영상 정보를 찾지 못했습니다")

        embed_url = metadata.get("embed_url")
        if not isinstance(embed_url, str) or not embed_url.strip():
            raise StreamNotFoundError("영상 플레이어 주소를 찾지 못했습니다")
        embed_url = urljoin(page_url, embed_url.strip())

        player = fetch_page(embed_url, timeout)
        streams = GenericExtractor().extract(player.url, player.text)
        if not streams:
            raise StreamNotFoundError("영상 플레이어에서 스트림을 찾지 못했습니다")

        title = metadata.get("title")
        if not isinstance(title, str) or not title.strip():
            return streams
        return [
            StreamInfo(
                url=stream.url,
                title=title.strip(),
                stream_type=stream.stream_type,
                referer=stream.referer,
            )
            for stream in streams
        ]
