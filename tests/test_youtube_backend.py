from pathlib import Path

from streamgrab.backends.youtube import (
    DEFAULT_FORMAT,
    _YouTubeProgress,
    _find_supported_node,
    _output_template,
    _redact_url_queries,
    download_youtube,
    is_youtube_url,
    list_youtube_formats,
)
from streamgrab.backends import youtube
from streamgrab.backends import ytdlp_common


def test_recognizes_youtube_hosts_without_matching_impostors() -> None:
    assert is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert is_youtube_url("https://youtu.be/abc")
    assert is_youtube_url("https://www.youtube-nocookie.com/embed/abc")
    assert not is_youtube_url("https://youtube.com.example.org/watch?v=abc")


def test_output_template_supports_directory_and_filename() -> None:
    assert _output_template(Path("downloads")).name.endswith(".%(ext)s")
    assert _output_template(Path("downloads/video.mp4")) == Path(
        "downloads/video.mp4"
    )


def test_progress_aggregates_video_and_audio(
    capsys,
) -> None:
    progress = _YouTubeProgress(totals={"video": 800, "audio": 200})

    progress.download_hook(
        {
            "status": "downloading",
            "downloaded_bytes": 400,
            "total_bytes": 800,
            "info_dict": {"format_id": "video"},
        }
    )
    progress.download_hook(
        {
            "status": "finished",
            "downloaded_bytes": 200,
            "total_bytes": 200,
            "info_dict": {"format_id": "audio"},
        }
    )

    output = capsys.readouterr().err
    assert "40.0%" in output
    assert "60.0%" in output


def test_progress_never_moves_backwards(capsys) -> None:
    progress = _YouTubeProgress(totals={"video": 100})

    progress.download_hook(
        {
            "status": "downloading",
            "downloaded_bytes": 60,
            "total_bytes": 100,
            "info_dict": {"format_id": "video"},
        }
    )
    progress.download_hook(
        {
            "status": "downloading",
            "downloaded_bytes": 20,
            "total_bytes": 100,
            "info_dict": {"format_id": "video"},
        }
    )

    output = capsys.readouterr().err
    assert output.count("60.0%") == 2
    assert "20.0%" not in output


def test_postprocessing_notice_is_emitted_once(caplog) -> None:
    progress = _YouTubeProgress(totals={})

    progress.postprocessor_hook({"status": "started"})
    progress.postprocessor_hook({"status": "started"})

    messages = [record.message for record in caplog.records]
    assert messages.count("영상 후처리 또는 병합을 진행합니다") == 1


def test_redacts_signed_query_values_from_backend_logs() -> None:
    message = "failed https://media.example/video?token=secret&sig=value now"

    assert _redact_url_queries(message) == "failed https://media.example/video now"


def test_list_formats_skips_storyboard_entries(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        youtube,
        "_extract_info",
        lambda url, format_selector: {
            "formats": [
                {"format_id": "sb0", "vcodec": "none", "acodec": "none"},
                {
                    "format_id": "137",
                    "resolution": "1920x1080",
                    "fps": 30,
                    "vcodec": "avc1.640028",
                    "acodec": "none",
                    "filesize": 1024,
                },
            ]
        },
    )

    list_youtube_formats("https://youtu.be/example")

    output = capsys.readouterr().out
    assert "137" in output
    assert "1920x1080" in output
    assert "sb0" not in output


def test_download_uses_safe_ytdlp_defaults(monkeypatch, tmp_path: Path) -> None:
    recorded: dict[str, object] = {}
    info = {
        "id": "example",
        "title": "Example",
        "requested_formats": [
            {"format_id": "video", "filesize": 800},
            {"format_id": "audio", "filesize": 200},
        ],
    }
    monkeypatch.setattr(youtube, "_extract_info", lambda url, selector: info)

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

    monkeypatch.setattr(youtube.yt_dlp, "YoutubeDL", FakeYoutubeDL)

    download_youtube("https://youtu.be/example", tmp_path)

    options = recorded["options"]
    assert isinstance(options, dict)
    assert options["format"] == DEFAULT_FORMAT
    assert options["noplaylist"] is True
    assert options["overwrites"] is False
    assert "http_chunk_size" not in options
    assert recorded["urls"] == ["https://youtu.be/example"]


def test_finds_supported_node_from_nvm_when_active_node_is_old(
    monkeypatch, tmp_path: Path
) -> None:
    old_node = tmp_path / "v20.19.6" / "bin" / "node"
    new_node = tmp_path / "v22.21.1" / "bin" / "node"
    old_node.parent.mkdir(parents=True)
    new_node.parent.mkdir(parents=True)
    old_node.touch()
    new_node.touch()

    monkeypatch.setattr(ytdlp_common.shutil, "which", lambda name: str(old_node))
    monkeypatch.setattr(ytdlp_common.Path, "home", lambda: tmp_path.parent)
    monkeypatch.setattr(
        ytdlp_common,
        "node_version",
        lambda path: (22, 21, 1) if path == new_node else (20, 19, 6),
    )
    monkeypatch.setattr(
        ytdlp_common.Path,
        "glob",
        lambda self, pattern: iter([old_node, new_node]),
    )
    _find_supported_node.cache_clear()

    assert _find_supported_node() == str(new_node)
    _find_supported_node.cache_clear()
