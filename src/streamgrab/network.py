"""Small HTTP client used by page analysis and direct downloads."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from streamgrab.exceptions import InvalidURLError, NetworkError


USER_AGENT = "StreamGrab/0.1 (+https://github.com/streamgrab)"
MAX_PAGE_SIZE = 10 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class PageResponse:
    url: str
    text: str
    content_type: str


def validate_http_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidURLError("http 또는 https URL을 입력해야 합니다")
    if parsed.username or parsed.password:
        raise InvalidURLError("사용자 정보가 포함된 URL은 지원하지 않습니다")


def fetch_page(url: str, timeout: float) -> PageResponse:
    """Fetch a bounded HTML response without executing page scripts."""

    validate_http_url(url)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise NetworkError(f"HTML 페이지가 아닙니다: {content_type}")

            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > MAX_PAGE_SIZE:
                raise NetworkError("분석할 페이지가 허용 크기를 초과합니다")

            payload = response.read(MAX_PAGE_SIZE + 1)
            if len(payload) > MAX_PAGE_SIZE:
                raise NetworkError("분석할 페이지가 허용 크기를 초과합니다")

            charset = response.headers.get_content_charset() or "utf-8"
            return PageResponse(
                url=response.geturl(),
                text=payload.decode(charset, errors="replace"),
                content_type=content_type,
            )
    except NetworkError:
        raise
    except (HTTPError, URLError, OSError, ValueError) as error:
        raise NetworkError(f"페이지를 가져올 수 없습니다: {error}") from error

