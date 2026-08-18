from streamgrab.models import StreamInfo, StreamType

import pytest

from streamgrab import cli
from streamgrab.cli import main


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
