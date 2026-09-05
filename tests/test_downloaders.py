from pathlib import Path
import subprocess

from streamgrab.downloaders import hls
from streamgrab.exceptions import FFmpegError
from streamgrab.models import StreamInfo, StreamType


def test_hls_downloader_uses_ffmpeg_without_shell(
    monkeypatch, tmp_path: Path
) -> None:
    called: dict[str, object] = {}
    stream = StreamInfo(
        url="https://media.example/master.m3u8",
        title="Example",
        stream_type=StreamType.HLS,
        referer="https://example.com/watch",
    )

    monkeypatch.setattr(hls.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    def fake_run(command, **kwargs):
        called["command"] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(hls.subprocess, "run", fake_run)

    hls.download_hls(stream, tmp_path / "output.mp4")

    command = called["command"]
    assert isinstance(command, list)
    assert "-referer" in command
    assert "-c" in command
    assert "copy" in command


def test_simple_hls_playlist_resolves_segment_urls() -> None:
    playlist = """#EXTM3U
#EXT-X-TARGETDURATION:4
#EXTINF:4,
file0.ts
#EXTINF:4,
segments/file1.ts?token=value
#EXT-X-ENDLIST
"""

    assert hls._parse_simple_media_playlist(
        "https://media.example/path/master.m3u8", playlist
    ) == [
        "https://media.example/path/file0.ts",
        "https://media.example/path/segments/file1.ts?token=value",
    ]


def test_simple_hls_playlist_rejects_encryption() -> None:
    playlist = """#EXTM3U
#EXT-X-KEY:METHOD=AES-128,URI="key.bin"
#EXTINF:4,
file0.ts
"""

    try:
        hls._parse_simple_media_playlist(
            "https://media.example/master.m3u8", playlist
        )
    except FFmpegError as error:
        assert "암호화된 HLS" in str(error)
    else:
        raise AssertionError("encrypted playlist was accepted")


def test_hls_downloader_falls_back_when_ffmpeg_gets_403(
    monkeypatch, tmp_path: Path
) -> None:
    stream = StreamInfo(
        url="https://media.example/master.m3u8",
        title="Example",
        stream_type=StreamType.HLS,
    )
    fallback: dict[str, object] = {}
    monkeypatch.setattr(hls.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        hls.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 1, stderr="Server returned 403 Forbidden"
        ),
    )

    def fake_fallback(selected, destination, ffmpeg):
        fallback.update(
            stream=selected, destination=destination, ffmpeg=ffmpeg
        )

    monkeypatch.setattr(hls, "_download_simple_hls_over_http2", fake_fallback)
    destination = tmp_path / "output.mp4"

    hls.download_hls(stream, destination)

    assert fallback == {
        "stream": stream,
        "destination": destination,
        "ffmpeg": "/usr/bin/ffmpeg",
    }


def test_segment_progress_uses_single_carriage_return_line(capsys) -> None:
    hls._render_segment_progress(5, 10)
    hls._render_segment_progress(10, 10)

    progress = capsys.readouterr().err
    assert "\r다운로드 [###############---------------]  50.0%" in progress
    assert progress.endswith("100.0%\n")


def test_find_ffmpeg_in_winget_packages(monkeypatch, tmp_path: Path) -> None:
    executable = (
        tmp_path
        / "Microsoft"
        / "WinGet"
        / "Packages"
        / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        / "ffmpeg-8.0-full_build"
        / "bin"
        / "ffmpeg.exe"
    )
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setattr(hls.shutil, "which", lambda _name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert hls._find_ffmpeg() == str(executable)
