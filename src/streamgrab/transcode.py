"""Make saved videos use a codec the target player understands.

Many TVs only decode H.264/H.265 from USB storage, while YouTube serves most
HD videos as VP9 or AV1. These helpers steer yt-dlp towards the requested
codec and, when the source does not offer it, re-encode with FFmpeg.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys

from streamgrab.downloaders.hls import _find_ffmpeg as find_ffmpeg
from streamgrab.exceptions import FFmpegError


logger = logging.getLogger("streamgrab")

VIDEO_CODECS = ("h264", "h265", "original")
DEFAULT_VIDEO_CODEC = "h264"
CODEC_LABELS = {"h264": "H.264", "h265": "H.265"}
FFMPEG_REQUIRED_MESSAGE = "영상 코덱 변환에는 FFmpeg가 필요합니다"

# ffprobe codec_name for each target.
_PROBE_NAMES = {"h264": "h264", "h265": "hevc"}
# yt-dlp vcodec prefixes that already satisfy the target.
_YTDLP_PREFIXES = {"h264": ("avc1",), "h265": ("hvc1", "hev1")}
_ENCODER_ARGS = {
    "h264": [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-profile:v", "high", "-pix_fmt", "yuv420p",
    ],
    "h265": [
        "-c:v", "libx265", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p", "-tag:v", "hvc1",
        "-x265-params", "log-level=error",
    ],
}


def format_selector(video_codec: str, fallback: str) -> str:
    """Prefer streams already encoded with the target codec."""
    prefixes = _YTDLP_PREFIXES.get(video_codec)
    if not prefixes:
        return fallback
    preferred = [
        f"bv*[vcodec^={prefix}]+ba[ext=m4a]/bv*[vcodec^={prefix}]+ba/b[vcodec^={prefix}]"
        for prefix in prefixes
    ]
    return "/".join([*preferred, fallback])


_DISPLAY_NAMES = {
    "h264": "H.264", "hevc": "H.265", "vp9": "VP9", "av1": "AV1",
    "vp8": "VP8", "mpeg4": "MPEG-4", "mpeg2video": "MPEG-2",
}


def probe_video_codec(path: Path) -> str | None:
    """Human-readable video codec of ``path`` (e.g. "VP9"), or None if unknown."""
    ffmpeg = find_ffmpeg()
    ffprobe = _find_ffprobe(ffmpeg) if ffmpeg else None
    if ffprobe is None:
        return None
    try:
        probe = _probe(ffprobe, path)
    except (FFmpegError, ValueError):
        return None
    video = next((s for s in probe["streams"] if s.get("codec_type") == "video"), None)
    if video is None:
        return None
    name = str(video.get("codec_name") or "")
    return _DISPLAY_NAMES.get(name, name.upper() or None)


def converted_path(source: Path, video_codec: str, folder: Path | None = None) -> Path:
    """Name for a converted copy, e.g. ``clip.mp4`` -> ``clip (H.264).mp4``."""
    label = CODEC_LABELS[video_codec]
    stem = re.sub(r"\s*\((?:H\.264|H\.265)\)(?: \d+)?$", "", source.stem)
    target = (folder or source.parent) / f"{stem} ({label}).mp4"
    counter = 2
    while target.exists() or target == source:
        target = (folder or source.parent) / f"{stem} ({label}) {counter}.mp4"
        counter += 1
    return target


def convert_file(source: Path, video_codec: str, folder: Path | None = None) -> Path:
    """Convert an existing video into a new file next to it, keeping the original."""
    if not source.is_file():
        raise FFmpegError(f"변환할 파일을 찾지 못했습니다: {source}")
    if video_codec not in _PROBE_NAMES:
        raise ValueError(f"변환 대상 코덱은 h264 또는 h265여야 합니다: {video_codec}")
    if folder is not None:
        folder.mkdir(parents=True, exist_ok=True)
    destination = converted_path(source, video_codec, folder)
    print(f"변환 대상: {source.name}")
    return ensure_video_codec(source, video_codec, destination=destination)


def ensure_video_codec(
    path: Path, video_codec: str, destination: Path | None = None
) -> Path:
    """Re-encode ``path`` to ``video_codec`` when needed; return the final file.

    Without ``destination`` the file is replaced in place (used after downloads).
    With ``destination`` a new file is always written and ``path`` is kept.
    """
    if video_codec == "original":
        return path
    if video_codec not in _PROBE_NAMES:
        raise ValueError(f"지원하지 않는 영상 코덱입니다: {video_codec}")
    keep_source = destination is not None

    ffmpeg = find_ffmpeg()
    ffprobe = _find_ffprobe(ffmpeg) if ffmpeg else None
    if ffmpeg is None or ffprobe is None:
        raise FFmpegError(FFMPEG_REQUIRED_MESSAGE)

    probe = _probe(ffprobe, path)
    video = next((s for s in probe["streams"] if s.get("codec_type") == "video"), None)
    if video is None:
        return path
    audio = next((s for s in probe["streams"] if s.get("codec_type") == "audio"), None)
    label = CODEC_LABELS[video_codec]
    target = _PROBE_NAMES[video_codec]

    audio_ok = audio is None or tv_safe_audio(audio)
    if video.get("codec_name") == target:
        needs_tag = video_codec == "h265" and video.get("codec_tag_string") != "hvc1"
        if path.suffix.lower() == ".mp4" and not needs_tag and audio_ok and not keep_source:
            return path
        video_args = ["-c:v", "copy"]
        if video_codec == "h265":
            video_args += ["-tag:v", "hvc1"]
        print(f"{label} 형식이므로 재인코딩 없이 MP4로 정리합니다")
    else:
        print(f"{label}로 변환 시작: 원본 코덱 {video.get('codec_name', '알 수 없음')}")
        video_args = list(_ENCODER_ARGS[video_codec])

    if destination is None:
        destination = path.with_suffix(".mp4")
    temporary = destination.with_name(f"{destination.stem}.converting.mp4")
    audio_file = destination.with_name(f"{destination.stem}.converting.aac")
    duration = _float(probe.get("format", {}).get("duration"))
    try:
        inputs = ["-i", str(path)]
        maps = ["-map", "0:v:0"]
        if audio is not None:
            _prepare_tv_audio(ffmpeg, path, audio, audio_file)
            inputs += ["-i", str(audio_file)]
            maps += ["-map", "1:a:0"]
        command = [
            ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            *inputs, *maps,
            *video_args, "-c:a", "copy",
            "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats",
            str(temporary),
        ]
        _run_with_progress(command, duration, label)
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        audio_file.unlink(missing_ok=True)
    if not keep_source and destination != path:
        path.unlink(missing_ok=True)
    print(f"변환 완료: {destination}")
    return destination


def tv_safe_audio(stream: dict) -> bool:
    """AAC-LC with a plain 2-byte AudioSpecificConfig, which every TV decodes.

    YouTube audio pads the config with zero bytes (16 bytes instead of 2).
    PCs ignore that, but many TV/LCD hardware decoders then play no sound.
    """
    return (
        stream.get("codec_name") == "aac"
        and stream.get("profile") == "LC"
        and int(stream.get("extradata_size") or 0) == 2
        and int(stream.get("channels") or 0) in {1, 2}
    )


def _prepare_tv_audio(ffmpeg: str, source: Path, audio: dict, target: Path) -> None:
    """Write the first audio track as ADTS AAC-LC.

    Muxing ADTS into MP4 rebuilds a clean 2-byte AudioSpecificConfig, so AAC-LC
    stereo is fixed losslessly (stream copy). Anything else is re-encoded to
    AAC-LC stereo.
    """
    lossless = (
        audio.get("codec_name") == "aac"
        and audio.get("profile") == "LC"
        and int(audio.get("channels") or 0) in {1, 2}
    )
    codec_args = ["-c:a", "copy"] if lossless else ["-c:a", "aac", "-b:a", "192k", "-ac", "2"]
    command = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-map", "0:a:0", "-vn", *codec_args, "-f", "adts", str(target),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", creationflags=_NO_WINDOW,
        )
    except OSError as error:
        raise FFmpegError(f"FFmpeg를 실행할 수 없습니다: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ""
        raise FFmpegError(f"오디오 정리에 실패했습니다 {detail}".strip())


def _find_ffprobe(ffmpeg: str) -> str | None:
    ffmpeg_path = Path(ffmpeg)
    sibling = ffmpeg_path.with_name(ffmpeg_path.name.replace("ffmpeg", "ffprobe"))
    if sibling.is_file():
        return str(sibling)
    from shutil import which

    return which("ffprobe")


def _probe(ffprobe: str, path: Path) -> dict:
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-show_entries",
                "stream=codec_type,codec_name,codec_tag_string,profile,"
                "channels,extradata_size:format=duration",
                "-of", "json", str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_NO_WINDOW,
        )
    except OSError as error:
        raise FFmpegError(f"ffprobe를 실행할 수 없습니다: {error}") from error
    if result.returncode != 0:
        raise FFmpegError(f"영상 정보를 읽지 못했습니다: {result.stderr.strip()}")
    data = json.loads(result.stdout or "{}")
    data.setdefault("streams", [])
    return data


def _run_with_progress(command: list[str], duration: float | None, label: str) -> None:
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_NO_WINDOW,
        )
    except OSError as error:
        raise FFmpegError(f"FFmpeg를 실행할 수 없습니다: {error}") from error

    rendered = False
    try:
        assert process.stdout is not None
        for line in process.stdout:
            key, _, value = line.strip().partition("=")
            if key == "out_time_us" and duration:
                seconds = (_float(value) or 0) / 1_000_000
                _render(label, min(100.0, max(0.0, seconds / duration * 100)))
                rendered = True
        stderr = process.stderr.read() if process.stderr else ""
        code = process.wait()
    except BaseException:
        process.kill()
        process.wait()
        raise
    if rendered:
        _render(label, 100.0)
        print(file=sys.stderr)
    if code != 0:
        detail = stderr.strip().splitlines()[-1] if stderr.strip() else ""
        raise FFmpegError(
            f"{label} 변환에 실패했습니다 (FFmpeg 오류 코드 {code}) {detail}".strip()
        )


def _render(label: str, percent: float) -> None:
    width = 30
    filled = int(width * percent / 100)
    bar = "#" * filled + "-" * (width - filled)
    print(f"\r변환 [{label}] [{bar}] {percent:5.1f}%", end="", file=sys.stderr, flush=True)


def _float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
