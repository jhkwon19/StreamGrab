from pathlib import Path
import subprocess

import pytest

from streamgrab import cli
from streamgrab.gui_support import cli_command, convert_command, parse_progress
from streamgrab.transcode import (
    convert_file,
    converted_path,
    ensure_video_codec,
    find_ffmpeg,
    format_selector,
    probe_video_codec,
)


def test_h264_selector_prefers_avc1_then_falls_back() -> None:
    selector = format_selector("h264", "bv*+ba/b")
    assert selector.startswith("bv*[vcodec^=avc1]+ba[ext=m4a]")
    assert selector.endswith("/bv*+ba/b")


def test_original_selector_is_untouched() -> None:
    assert format_selector("original", "bv*+ba/b") == "bv*+ba/b"


def test_converted_path_never_overwrites(tmp_path: Path) -> None:
    source = tmp_path / "clip.webm"
    (tmp_path / "clip (H.264).mp4").touch()
    assert converted_path(source, "h264") == tmp_path / "clip (H.264) 2.mp4"


def test_gui_commands_pass_codec() -> None:
    assert cli_command("https://e.com/v", Path("d"), "h265")[-4:] == [
        "--codec", "h265", "--output", "d",
    ]
    command = convert_command(Path("a.mp4"), "h264", Path("out"))
    assert command[-6:] == ["--convert", "a.mp4", "--codec", "h264", "--output", "out"]


def test_parse_progress_distinguishes_download_and_conversion() -> None:
    assert parse_progress("다운로드 [####------]  42.0%") == ("다운로드", 42.0)
    assert parse_progress("변환 [H.264] [##--------]  12.5%") == ("변환", 12.5)
    assert parse_progress("저장 시작: 제목 [abc]") is None


def test_cli_convert_rejects_original(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--convert", "a.mp4", "--codec", "original"])


def test_cli_convert_routes_each_file(monkeypatch, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setattr(
        cli, "convert_file", lambda source, codec, folder: calls.append((source, codec, folder))
    )
    assert cli.main(["--convert", "a.mp4", "b.mkv", "--codec", "h265", "-o", str(tmp_path)]) == 0
    assert calls == [
        (Path("a.mp4"), "h265", tmp_path),
        (Path("b.mkv"), "h265", tmp_path),
    ]


def _make_vp9_clip(folder: Path) -> Path:
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        pytest.skip("FFmpeg not installed")
    clip = folder / "sample 😋.mp4"
    result = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libvpx-vp9", "-c:a", "aac", "-shortest", str(clip),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        pytest.skip("FFmpeg cannot encode VP9 here")
    return clip


def test_convert_file_keeps_original_and_writes_h264(tmp_path: Path) -> None:
    clip = _make_vp9_clip(tmp_path)
    assert probe_video_codec(clip) == "VP9"

    result = convert_file(clip, "h264")

    assert clip.exists()
    assert result == tmp_path / "sample 😋 (H.264).mp4"
    assert probe_video_codec(result) == "H.264"
    assert not list(tmp_path.glob("*.converting.mp4"))


def test_ensure_video_codec_replaces_download_in_place(tmp_path: Path) -> None:
    clip = _make_vp9_clip(tmp_path)

    result = ensure_video_codec(clip, "h265")

    assert result == clip
    assert probe_video_codec(result) == "H.265"
