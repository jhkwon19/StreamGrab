from pathlib import Path

from streamgrab.backends import generic_ytdlp
from streamgrab.backends.generic_ytdlp import download_generic, list_generic_formats


def test_list_generic_formats_prints_native_format(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        generic_ytdlp,
        "_extract_info",
        lambda url, format_selector: {
            "formats": [
                {
                    "format_id": "4731",
                    "resolution": "1280x720",
                    "fps": 30,
                    "vcodec": "avc1.640020",
                    "acodec": "mp4a.40.2",
                    "filesize_approx": 1024,
                }
            ]
        },
    )

    list_generic_formats("https://protected.example/watch")

    output = capsys.readouterr().out
    assert "4731" in output
    assert "1280x720" in output


def test_download_generic_enables_impersonation(monkeypatch, tmp_path: Path) -> None:
    recorded: dict[str, object] = {}
    monkeypatch.setattr(
        generic_ytdlp,
        "_extract_info",
        lambda url, selector: {
            "id": "example",
            "title": "Example",
            "format_id": "4731",
            "filesize": 100,
        },
    )

    class FakeYoutubeDL:
        def __init__(self, options):
            recorded["options"] = options

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def download(self, urls):
            recorded["urls"] = urls
            return 0

    monkeypatch.setattr(generic_ytdlp.yt_dlp, "YoutubeDL", FakeYoutubeDL)

    download_generic("https://protected.example/watch", tmp_path)

    options = recorded["options"]
    assert isinstance(options, dict)
    assert options["extractor_args"] == {"generic": {"impersonate": [""]}}
    assert options["noplaylist"] is True
    assert options["overwrites"] is False
    assert recorded["urls"] == ["https://protected.example/watch"]
