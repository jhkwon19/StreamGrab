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
    assert cli_command("https://e.com/v", Path("d"), "h265", "mp3")[-6:] == [
        "--codec", "h265", "--audio", "mp3", "--output", "d",
    ]
    command = convert_command(Path("a.mp4"), "h264", Path("out"), "ac3")
    assert command[-8:] == [
        "--convert", "a.mp4", "--codec", "h264", "--audio", "ac3", "--output", "out",
    ]


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
        cli,
        "convert_file",
        lambda source, codec, folder, audio: calls.append((source, codec, folder, audio)),
    )
    assert cli.main([
        "--convert", "a.mp4", "b.mkv", "--codec", "h265", "--audio", "mp3", "-o", str(tmp_path),
    ]) == 0
    assert calls == [
        (Path("a.mp4"), "h265", tmp_path, "mp3"),
        (Path("b.mkv"), "h265", tmp_path, "mp3"),
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


def test_converted_path_does_not_stack_codec_suffixes(tmp_path: Path) -> None:
    source = tmp_path / "clip (H.265).mp4"
    source.touch()
    assert converted_path(source, "h265") == tmp_path / "clip (H.265) 2.mp4"
    assert converted_path(source, "h264") == tmp_path / "clip (H.264).mp4"


def test_tv_safe_audio_rejects_padded_youtube_config() -> None:
    from streamgrab.transcode import tv_safe_audio

    good = {"codec_name": "aac", "profile": "LC", "extradata_size": 2, "channels": 2}
    assert tv_safe_audio(good)
    assert not tv_safe_audio({**good, "extradata_size": 16})  # YouTube m4a
    assert not tv_safe_audio({**good, "extradata_size": 5})   # explicit SBR signalling
    assert not tv_safe_audio({**good, "profile": "HE-AAC"})
    assert not tv_safe_audio({**good, "channels": 6})


def _audio_config_size(path: Path) -> int:
    ffmpeg = find_ffmpeg()
    from streamgrab.transcode import _find_ffprobe, _probe

    probe = _probe(_find_ffprobe(ffmpeg), path)
    audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    return int(audio["extradata_size"])


def test_h264_download_with_non_tv_audio_is_fixed_in_place(tmp_path: Path) -> None:
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        pytest.skip("FFmpeg not installed")
    clip = tmp_path / "already h264.mp4"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(clip),
        ],
        check=True,
        capture_output=True,
    )
    assert _audio_config_size(clip) != 2

    result = ensure_video_codec(clip, "h264")

    assert result == clip
    assert probe_video_codec(result) == "H.264"
    assert _audio_config_size(result) == 2
    assert not list(tmp_path.glob("*.converting.*"))


def test_converted_files_have_tv_safe_audio(tmp_path: Path) -> None:
    clip = _make_vp9_clip(tmp_path)
    result = convert_file(clip, "h265")
    assert _audio_config_size(result) == 2


def _audio_codec(path: Path) -> str:
    from streamgrab.transcode import _find_ffprobe, _probe

    probe = _probe(_find_ffprobe(find_ffmpeg()), path)
    return next(s for s in probe["streams"] if s["codec_type"] == "audio")["codec_name"]


@pytest.mark.parametrize(("audio", "expected", "suffix"), [
    ("mp3", "mp3", "(H.264 MP3).mp4"),
    ("ac3", "ac3", "(H.264 AC-3).mp4"),
])
def test_convert_file_to_kitchen_tv_audio(tmp_path: Path, audio, expected, suffix) -> None:
    """Some kitchen TVs (e.g. COSTEL CVK-118AF) decode MP3/AC-3 but not AAC."""
    clip = _make_vp9_clip(tmp_path)

    result = convert_file(clip, "h264", audio_codec=audio)

    assert result.name.endswith(suffix)
    assert probe_video_codec(result) == "H.264"
    assert _audio_codec(result) == expected
    assert not list(tmp_path.glob("*.converting.*"))


def test_download_fix_switches_audio_without_touching_h264_video(tmp_path: Path) -> None:
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        pytest.skip("FFmpeg not installed")
    clip = tmp_path / "already h264.mp4"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(clip),
        ],
        check=True,
        capture_output=True,
    )

    result = ensure_video_codec(clip, "h264", audio_codec="mp3")

    assert result == clip and _audio_codec(result) == "mp3"
    assert ensure_video_codec(result, "h264", audio_codec="mp3") == clip  # already fine


def test_converted_path_strips_previous_audio_label(tmp_path: Path) -> None:
    source = tmp_path / "clip (H.265 MP3).mp4"
    assert converted_path(source, "h264", audio_codec="mp3") == tmp_path / "clip (H.264 MP3).mp4"
