import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

from streamgrab import ytdlp_runtime as rt


def _wheel(package: str, version: str, extra: dict[str, str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"{package}/__init__.py", f"__version__ = {version!r}\n")
        archive.writestr(f"{package}-{version}.dist-info/METADATA", f"Version: {version}\n")
        archive.writestr("unrelated/evil.py", "raise SystemExit\n")
        for name, content in (extra or {}).items():
            archive.writestr(name, content)
    return buffer.getvalue()


class FakePyPI:
    def __init__(self, version: str = "2099.1.2", ejs: str | None = "9.9.9") -> None:
        self.version = version
        self.ejs = ejs
        self.files = {
            "https://files.pythonhosted.org/yt.whl": _wheel("yt_dlp", version),
            "https://files.pythonhosted.org/ejs.whl": _wheel("yt_dlp_ejs", ejs or "0"),
        }
        self.bad_hash = False
        self.requested: list[str] = []

    def _entry(self, url: str, filename: str) -> dict:
        digest = hashlib.sha256(self.files[url]).hexdigest()
        if self.bad_hash:
            digest = "0" * 64
        return {
            "packagetype": "bdist_wheel",
            "filename": filename,
            "url": url,
            "digests": {"sha256": digest},
        }

    def fetch_json(self, url: str) -> dict:
        self.requested.append(url)
        if "yt-dlp-ejs" in url:
            return {"urls": [self._entry("https://files.pythonhosted.org/ejs.whl", "yt_dlp_ejs-py3-none-any.whl")]}
        requires = [f'yt-dlp-ejs=={self.ejs}; extra == "default"'] if self.ejs else []
        return {
            "info": {"version": self.version, "requires_dist": requires},
            "urls": [self._entry("https://files.pythonhosted.org/yt.whl", "yt_dlp-py3-none-any.whl")],
        }

    def fetch_bytes(self, url: str) -> bytes:
        return self.files[url]


@pytest.fixture
def bundled(monkeypatch):
    monkeypatch.setattr(rt, "bundled_version", lambda package="yt-dlp": "2026.10.26")


def _update(home: Path, pypi: FakePyPI, selftest=lambda folder, version: True, force=True):
    return rt.check_and_update(
        force=force, home=home, log=lambda _m: None,
        fetch_json=pypi.fetch_json, fetch_bytes=pypi.fetch_bytes, selftest=selftest,
    )


def test_parse_version_handles_dev_builds() -> None:
    assert rt.parse_version("2026.08.30.232658.dev0") == (2026, 8, 30, 232658)
    assert rt.parse_version("2026.10.26") > rt.parse_version("2026.08.30.232658")
    assert rt.parse_version(None) == ()


def test_update_installs_verified_wheels_and_switches(tmp_path: Path, bundled) -> None:
    result = _update(tmp_path, FakePyPI())

    assert result.updated and result.active == "2099.1.2" and result.source == "external"
    assert (tmp_path / "current.txt").read_text() == "2099.1.2"
    install = tmp_path / "2099.1.2"
    assert (install / "yt_dlp" / "__init__.py").is_file()
    assert (install / "yt_dlp_ejs" / "__init__.py").is_file()
    assert not (install / "unrelated").exists()
    manifest = json.loads((install / "manifest.json").read_text())
    assert manifest["yt-dlp"] == "2099.1.2" and manifest["yt-dlp-ejs"] == "9.9.9"
    assert not list(tmp_path.glob(".staging-*"))
    assert not (tmp_path / ".update.lock").exists()


def test_hash_mismatch_keeps_current_version(tmp_path: Path, bundled) -> None:
    pypi = FakePyPI()
    pypi.bad_hash = True

    result = _update(tmp_path, pypi)

    assert not result.updated and "해시" in result.message
    assert not (tmp_path / "current.txt").exists()
    assert not (tmp_path / "2099.1.2").exists()


def test_failed_selftest_keeps_previous_install(tmp_path: Path, bundled) -> None:
    _update(tmp_path, FakePyPI("2099.1.2"))

    result = _update(tmp_path, FakePyPI("2099.2.1"), selftest=lambda folder, version: False)

    assert not result.updated and "자가 점검" in result.message
    assert (tmp_path / "current.txt").read_text() == "2099.1.2"
    assert not (tmp_path / "2099.2.1").exists()


def test_rejects_path_traversal_in_wheel(tmp_path: Path, bundled) -> None:
    pypi = FakePyPI()
    pypi.files["https://files.pythonhosted.org/yt.whl"] = _wheel(
        "yt_dlp", "2099.1.2", {"yt_dlp/../../escape.py": "x"}
    )

    result = _update(tmp_path, pypi)

    assert not result.updated and "안전하지 않은" in result.message
    assert not (tmp_path.parent / "escape.py").exists()


def test_already_latest_does_not_download(tmp_path: Path, bundled) -> None:
    pypi = FakePyPI("2026.10.26")
    result = _update(tmp_path, pypi)
    assert not result.updated and result.source == "bundled"
    assert pypi.requested == [rt.PYPI_JSON.format(name="yt-dlp")]


def test_check_is_throttled_unless_forced(tmp_path: Path, bundled) -> None:
    _update(tmp_path, FakePyPI("2026.10.26"))
    pypi = FakePyPI()
    assert not _update(tmp_path, pypi, force=False).checked
    assert pypi.requested == []
    assert _update(tmp_path, pypi, force=True).updated


def test_keeps_only_recent_installs(tmp_path: Path, bundled) -> None:
    for version in ("2099.1.1", "2099.1.2", "2099.1.3"):
        _update(tmp_path, FakePyPI(version))
    installs = sorted(p.name for p in tmp_path.iterdir() if p.is_dir())
    assert installs == ["2099.1.2", "2099.1.3"]


def test_activate_prefers_newer_external(tmp_path: Path, bundled, monkeypatch) -> None:
    _update(tmp_path, FakePyPI("2099.1.2"))
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "yt_dlp", raising=False)

    install = rt.activate(tmp_path)

    assert install is not None and sys.path[0] == str(tmp_path / "2099.1.2")


def test_activate_ignores_older_or_broken_external(tmp_path: Path, bundled, monkeypatch) -> None:
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "yt_dlp", raising=False)
    (tmp_path / "current.txt").write_text("missing")
    assert rt.activate(tmp_path) is None

    _update(tmp_path, FakePyPI("2026.1.1"))  # older than bundled -> not installed
    assert rt.activate(tmp_path) is None
    assert rt.active_version(tmp_path) == ("2026.10.26", "bundled")


def test_real_selftest_accepts_installed_ytdlp(tmp_path: Path) -> None:
    """The self-test process must load yt-dlp from the given folder only."""
    import yt_dlp

    assert not rt.run_selftest(tmp_path, "2026.10.26")  # empty folder -> pip copy -> rejected
    installed = Path(yt_dlp.__file__).parent
    assert rt.run_selftest(installed.parent, yt_dlp.version.__version__)


def test_update_check_output_reaches_gui_as_utf8(tmp_path: Path, monkeypatch) -> None:
    """Regression: the status bar showed mojibake after "업데이트 확인"."""
    import os
    import subprocess

    from streamgrab.gui_support import parse_ytdlp_status, worker_environment, ytdlp_command

    rt._save_state(tmp_path, "2026.10.26")  # recent check -> no network needed
    env = worker_environment()
    env.pop("PYTHONIOENCODING")
    env["STREAMGRAB_YTDLP_HOME"] = str(tmp_path)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    result = subprocess.run(
        ytdlp_command(force=False, update=True),
        capture_output=True, encoding="utf-8", errors="strict", env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "최근에 확인했습니다" in result.stdout
    assert parse_ytdlp_status(result.stdout)["message"] == "최근에 확인했습니다"
