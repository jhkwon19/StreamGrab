from pathlib import Path

from streamgrab.models import StreamInfo, StreamType

import pytest

from streamgrab import cli
from streamgrab.cli import main
from streamgrab.exceptions import NetworkError, StreamNotFoundError


def test_cli_without_arguments_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "usage: streamgrab" in output


def test_cli_lists_discovered_streams(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "_find_streams",
        lambda url, timeout: [
            StreamInfo(
                url="https://media.example/video/master.m3u8",
                title="Example",
                stream_type=StreamType.HLS,
                referer=url,
            )
        ],
    )

    assert main(["https://example.com/video", "--list-formats"]) == 0

    output = capsys.readouterr().out
    assert "hls" in output
    assert "Example" in output


def test_cli_routes_youtube_to_specialized_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, object] = {}
    monkeypatch.setattr(cli, "is_youtube_url", lambda url: True)

    def fake_download(url, output, format_selector):
        called.update(
            url=url, output=output, format_selector=format_selector
        )

    monkeypatch.setattr(cli, "download_youtube", fake_download)

    assert (
        main(
            [
                "https://www.youtube.com/watch?v=example",
                "-f",
                "137+140",
                "-o",
                "media",
            ]
        )
        == 0
    )
    assert called == {
        "url": "https://www.youtube.com/watch?v=example",
        "output": Path("media"),
        "format_selector": "137+140",
    }


def test_cli_falls_back_to_ytdlp_when_static_page_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, object] = {}
    monkeypatch.setattr(cli, "is_youtube_url", lambda url: False)

    def blocked(url, timeout):
        raise NetworkError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(cli, "_find_streams", blocked)
    monkeypatch.setattr(
        cli,
        "download_generic",
        lambda url, output, format_selector: called.update(
            url=url, output=output, format_selector=format_selector
        ),
    )

    assert main(["https://protected.example/watch", "-o", "media"]) == 0
    assert called == {
        "url": "https://protected.example/watch",
        "output": Path("media"),
        "format_selector": None,
    }


def test_cli_lists_ytdlp_formats_after_static_extraction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []
    monkeypatch.setattr(cli, "is_youtube_url", lambda url: False)
    monkeypatch.setattr(
        cli,
        "_find_streams",
        lambda url, timeout: (_ for _ in ()).throw(
            StreamNotFoundError("no static media")
        ),
    )
    monkeypatch.setattr(cli, "list_generic_formats", called.append)

    assert main(["https://embedded.example/watch", "--list-formats"]) == 0
    assert called == ["https://embedded.example/watch"]
