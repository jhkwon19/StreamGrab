from pathlib import Path

from streamgrab.gui_support import cli_command, failure_detail, is_valid_web_url


def test_valid_web_urls() -> None:
    assert is_valid_web_url("https://example.com/watch?v=1")
    assert is_valid_web_url(" http://localhost/video.mp4 ")


def test_invalid_web_urls() -> None:
    assert not is_valid_web_url("")
    assert not is_valid_web_url("example.com/video")
    assert not is_valid_web_url("file:///tmp/video.mp4")


def test_cli_command_uses_module_in_development(monkeypatch) -> None:
    monkeypatch.delattr("sys.frozen", raising=False)
    command = cli_command("https://example.com/video", Path("downloads"))
    assert command[1:3] == ["-m", "streamgrab"]
    assert command[-2:] == ["--output", "downloads"]


def test_cli_command_reenters_frozen_executable(monkeypatch) -> None:
    monkeypatch.setattr("sys.frozen", True, raising=False)
    command = cli_command("https://example.com/video", Path("downloads"))
    assert command[1:3] == ["--cli", "https://example.com/video"]


def test_failure_detail_prefers_error_over_late_buffered_start_message() -> None:
    output = (
        "ERROR: 직접 미디어 다운로드에 실패했습니다: 파일이 이미 있습니다\n"
        "저장 시작: D:\\Desktop\\video.mp4\n"
    )
    assert failure_detail(output) == "직접 미디어 다운로드에 실패했습니다: 파일이 이미 있습니다"


def test_worker_output_survives_emoji_titles() -> None:
    """Titles such as 'Yummy 😋' must reach the GUI instead of crashing cp949."""
    import subprocess
    import sys

    from streamgrab.gui_support import worker_environment

    env = worker_environment()
    env.pop("PYTHONIOENCODING")  # frozen builds may ignore it; rely on our own setup
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    script = (
        "from streamgrab.gui_support import configure_output_streams;"
        "configure_output_streams();"
        "print('저장 시작: Yummy \U0001f60b')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        env=env,
        check=True,
    )
    assert result.stdout.strip() == "저장 시작: Yummy \U0001f60b"
