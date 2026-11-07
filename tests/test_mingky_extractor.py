from streamgrab.extractors import mingky
from streamgrab.extractors.mingky import MingkyExtractor, is_mingky_movie_url
from streamgrab.network import PageResponse


def test_recognizes_numbered_mingky_movie_hosts() -> None:
    assert is_mingky_movie_url("https://mingky22.com/movie/350524")
    assert is_mingky_movie_url("https://www.mingky23.com/movie/example")
    assert not is_mingky_movie_url("https://mingky22.com/search?q=350524")
    assert not is_mingky_movie_url("https://example.com/movie/350524")


def test_resolves_movie_api_and_embedded_hls(monkeypatch) -> None:
    requested: dict[str, object] = {}

    def fake_fetch_json(url, timeout, referer=None):
        requested.update(api_url=url, api_referer=referer, timeout=timeout)
        return {
            "ok": True,
            "title": "Movie title",
            "embed_url": "https://player.example/player/350524",
        }

    def fake_fetch_page(url, timeout):
        requested.update(player_url=url, player_timeout=timeout)
        return PageResponse(
            url=url,
            text=(
                '<title>Player title</title><link rel="preload" as="fetch" '
                'href="https://media.example/350524/index.m3u8">'
            ),
            content_type="text/html",
        )

    monkeypatch.setattr(mingky, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(mingky, "fetch_page", fake_fetch_page)

    streams = MingkyExtractor().extract(
        "https://mingky22.com/movie/350524", timeout=12.5
    )

    assert requested == {
        "api_url": "https://mingky22.com/api/movies/350524",
        "api_referer": "https://mingky22.com/movie/350524",
        "timeout": 12.5,
        "player_url": "https://player.example/player/350524",
        "player_timeout": 12.5,
    }
    assert len(streams) == 1
    assert streams[0].url == "https://media.example/350524/index.m3u8"
    assert streams[0].title == "Movie title"
    assert streams[0].referer == "https://player.example/player/350524"
