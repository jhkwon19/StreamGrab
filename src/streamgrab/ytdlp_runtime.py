"""Keep yt-dlp up to date outside the frozen executable.

YouTube changes often and a yt-dlp frozen into ``StreamGrab.exe`` goes stale.
The packaged app therefore looks for a newer copy next to the executable::

    StreamGrab\\
    ├─ StreamGrab.exe            (bundled yt-dlp = fallback)
    └─ yt-dlp\\
       ├─ current.txt            name of the active install folder
       ├─ state.json             last update check
       └─ 2026.10.26\\           yt_dlp + matching yt_dlp_ejs + manifest.json

Workers call :func:`activate` before importing yt-dlp, so a finished update
applies to the next download without restarting the GUI. Updates download the
PyPI wheels, verify their SHA-256, unpack into a staging folder, smoke-test the
import in a fresh process and only then switch ``current.txt``.

This module must not import yt-dlp itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from importlib import metadata
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
from typing import Callable
import urllib.request
import zipfile


PYPI_JSON = "https://pypi.org/pypi/{name}/json"
PYPI_VERSION_JSON = "https://pypi.org/pypi/{name}/{version}/json"
CHECK_INTERVAL = timedelta(hours=24)
KEEP_INSTALLS = 2
STATUS_PREFIX = "@@YTDLP "
_PACKAGES = {"yt-dlp": "yt_dlp", "yt-dlp-ejs": "yt_dlp_ejs"}
_EJS_PIN = re.compile(r"^yt-dlp-ejs\s*==\s*([0-9][\w.]*)")
_LOCK_STALE = timedelta(minutes=15)


class UpdateError(Exception):
    """Raised when an update cannot be completed safely."""


# --------------------------------------------------------------------- paths
def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def ytdlp_home() -> Path:
    """Folder holding external yt-dlp installs.

    Next to the executable when it is writable, otherwise in LOCALAPPDATA.
    ``STREAMGRAB_YTDLP_HOME`` overrides both (used by tests and power users).
    """
    override = os.environ.get("STREAMGRAB_YTDLP_HOME")
    if override:
        return Path(override)
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
    fallback = local / "StreamGrab" / "yt-dlp"
    if not is_frozen():
        return fallback
    beside_exe = Path(sys.executable).resolve().parent / "yt-dlp"
    return beside_exe if _is_writable(beside_exe) else fallback


def _is_writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / f".write-test-{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


# ------------------------------------------------------------------ versions
def parse_version(value: str | None) -> tuple[int, ...]:
    """'2026.08.30.232658.dev0' -> (2026, 8, 30, 232658). Unknown -> ()."""
    if not value:
        return ()
    parts: list[int] = []
    for piece in value.strip().split("."):
        match = re.match(r"\d+", piece)
        if not match:
            break
        parts.append(int(match.group()))
    return tuple(parts)


def bundled_version(package: str = "yt-dlp") -> str | None:
    """Version shipped inside the executable (or installed with pip in dev)."""
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


@dataclass(frozen=True)
class Install:
    folder: Path
    ytdlp: str
    ejs: str | None


def read_install(folder: Path) -> Install | None:
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (folder / "yt_dlp" / "__init__.py").is_file():
        return None
    version = manifest.get("yt-dlp")
    if not isinstance(version, str):
        return None
    ejs = manifest.get("yt-dlp-ejs")
    return Install(folder, version, ejs if isinstance(ejs, str) else None)


def current_install(home: Path | None = None) -> Install | None:
    home = home or ytdlp_home()
    try:
        name = (home / "current.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    return read_install(home / name)


def active_version(home: Path | None = None) -> tuple[str | None, str]:
    """(version, "external" | "bundled") that a worker would use."""
    install = current_install(home)
    bundled = bundled_version()
    if install and parse_version(install.ytdlp) > parse_version(bundled):
        return install.ytdlp, "external"
    return bundled, "bundled"


def activate(home: Path | None = None) -> Install | None:
    """Put a newer external yt-dlp first on sys.path. Call before importing it."""
    if "yt_dlp" in sys.modules:
        return None
    install = current_install(home)
    if install is None:
        return None
    if parse_version(install.ytdlp) <= parse_version(bundled_version()):
        return None
    sys.path.insert(0, str(install.folder))
    return install


# -------------------------------------------------------------------- update
@dataclass
class UpdateResult:
    active: str | None
    source: str
    updated: bool = False
    checked: bool = False
    message: str = ""

    def as_json(self) -> str:
        # ASCII-only so the status line survives any console/pipe encoding.
        return json.dumps(self.__dict__, ensure_ascii=True)


def check_and_update(
    *,
    force: bool = False,
    home: Path | None = None,
    log: Callable[[str], None] = print,
    fetch_json: Callable[[str], dict] | None = None,
    fetch_bytes: Callable[[str], bytes] | None = None,
    selftest: Callable[[Path, str], bool] | None = None,
) -> UpdateResult:
    home = home or ytdlp_home()
    fetch_json = fetch_json or _fetch_json
    fetch_bytes = fetch_bytes or _fetch_bytes
    selftest = selftest or run_selftest
    active, source = active_version(home)
    result = UpdateResult(active, source)

    if not force and not _check_due(home):
        result.message = "최근에 확인했습니다"
        return result

    home.mkdir(parents=True, exist_ok=True)
    with _UpdateLock(home) as acquired:
        if not acquired:
            result.message = "다른 창에서 업데이트를 확인하는 중입니다"
            return result
        result.checked = True
        try:
            info = fetch_json(PYPI_JSON.format(name="yt-dlp"))
            latest = str(info["info"]["version"])
            if parse_version(latest) <= parse_version(active):
                result.message = f"yt-dlp {active}이(가) 최신입니다"
                _save_state(home, latest)
                return result

            log(f"yt-dlp {latest} 업데이트를 내려받는 중")
            ejs_version = _ejs_pin(info["info"].get("requires_dist") or [])
            install = _install(
                home, latest, info, ejs_version, fetch_json, fetch_bytes, selftest
            )
            (home / "current.tmp").write_text(install.folder.name, encoding="utf-8")
            os.replace(home / "current.tmp", home / "current.txt")
            _prune(home, keep=install.folder.name)
            _save_state(home, latest)
        except (UpdateError, OSError, ValueError, KeyError) as error:
            result.message = f"yt-dlp 업데이트 실패: {error}"
            return result

    result.active, result.source = active_version(home)
    result.updated = True
    result.message = f"yt-dlp {latest}(으)로 업데이트했습니다"
    return result


def _ejs_pin(requires_dist: list[str]) -> str | None:
    for requirement in requires_dist:
        match = _EJS_PIN.match(requirement)
        if match:
            return match.group(1)
    return None


def _install(
    home: Path,
    version: str,
    info: dict,
    ejs_version: str | None,
    fetch_json: Callable[[str], dict],
    fetch_bytes: Callable[[str], bytes],
    selftest: Callable[[Path, str], bool],
) -> Install:
    final = home / version
    if (existing := read_install(final)) is not None:
        return existing

    staging = home / f".staging-{version}-{os.getpid()}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        _extract_wheel(_download_wheel(info, fetch_bytes), staging, "yt_dlp")
        if ejs_version:
            ejs_info = fetch_json(PYPI_VERSION_JSON.format(name="yt-dlp-ejs", version=ejs_version))
            _extract_wheel(_download_wheel(ejs_info, fetch_bytes), staging, "yt_dlp_ejs")
        manifest = {
            "yt-dlp": version,
            "yt-dlp-ejs": ejs_version,
            "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if not selftest(staging, version):
            raise UpdateError("새 yt-dlp 자가 점검에 실패했습니다")
        shutil.rmtree(final, ignore_errors=True)
        os.replace(staging, final)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    install = read_install(final)
    if install is None:
        raise UpdateError("설치된 yt-dlp를 읽지 못했습니다")
    return install


def _download_wheel(info: dict, fetch_bytes: Callable[[str], bytes]) -> bytes:
    wheels = [
        entry for entry in info.get("urls", [])
        if entry.get("packagetype") == "bdist_wheel"
        and str(entry.get("filename", "")).endswith("py3-none-any.whl")
    ]
    if not wheels:
        raise UpdateError("PyPI에서 설치 파일(wheel)을 찾지 못했습니다")
    wheel = wheels[0]
    expected = str(wheel.get("digests", {}).get("sha256", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise UpdateError("PyPI가 SHA-256 해시를 제공하지 않았습니다")
    data = fetch_bytes(str(wheel["url"]))
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise UpdateError(f"{wheel.get('filename')} 해시가 일치하지 않습니다")
    return data


def _extract_wheel(data: bytes, destination: Path, package: str) -> None:
    """Extract only ``package/`` and its dist-info, refusing unsafe paths."""
    root = destination.resolve()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = [
            name for name in archive.namelist()
            if name.startswith(f"{package}/")
            or (name.startswith(f"{package}-") and ".dist-info/" in name)
        ]
        if not any(name.startswith(f"{package}/") for name in members):
            raise UpdateError(f"설치 파일에 {package} 패키지가 없습니다")
        for name in members:
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise UpdateError(f"설치 파일에 안전하지 않은 경로가 있습니다: {name}")
            target = (root / Path(*relative.parts)).resolve()
            if root not in target.parents:
                raise UpdateError(f"설치 파일에 안전하지 않은 경로가 있습니다: {name}")
            if name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))


def _prune(home: Path, keep: str) -> None:
    installs = sorted(
        (entry for entry in home.iterdir() if entry.is_dir() and read_install(entry)),
        key=lambda entry: parse_version(entry.name),
        reverse=True,
    )
    survivors = {keep, *(entry.name for entry in installs[:KEEP_INSTALLS])}
    for entry in installs:
        if entry.name not in survivors:
            shutil.rmtree(entry, ignore_errors=True)
    for leftover in home.glob(".staging-*"):
        shutil.rmtree(leftover, ignore_errors=True)


def _check_due(home: Path) -> bool:
    try:
        state = json.loads((home / "state.json").read_text(encoding="utf-8"))
        last = datetime.fromisoformat(state["last_check"])
    except (OSError, ValueError, KeyError, TypeError):
        return True
    return datetime.now(timezone.utc) - last >= CHECK_INTERVAL


def _save_state(home: Path, latest: str) -> None:
    state = {
        "last_check": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "latest_seen": latest,
    }
    (home / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


class _UpdateLock:
    """Cross-process lock so two windows never install at the same time."""

    def __init__(self, home: Path) -> None:
        self.path = home / ".update.lock"
        self.acquired = False

    def __enter__(self) -> bool:
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except OSError:
                    continue
                if age > _LOCK_STALE.total_seconds():
                    self.path.unlink(missing_ok=True)
                    continue
                return False
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            self.acquired = True
            return True
        return False

    def __exit__(self, *exc: object) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)


# ---------------------------------------------------------------- networking
def _request(url: str) -> urllib.request.Request:
    from streamgrab import __version__

    return urllib.request.Request(url, headers={"User-Agent": f"StreamGrab/{__version__}"})


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(_request(url), timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_bytes(url: str) -> bytes:
    if not url.startswith("https://files.pythonhosted.org/"):
        raise UpdateError(f"예상하지 못한 다운로드 주소입니다: {url}")
    with urllib.request.urlopen(_request(url), timeout=120) as response:
        return response.read()


# ------------------------------------------------------------------ selftest
def worker_prefix() -> list[str]:
    if is_frozen():
        return [sys.executable, "--cli"]
    return [sys.executable, "-m", "streamgrab"]


def run_selftest(folder: Path, expected: str) -> bool:
    """Import the staged yt-dlp in a clean process before switching to it."""
    try:
        result = subprocess.run(
            [*worker_prefix(), "--ytdlp-selftest", str(folder), expected],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "SELFTEST OK" in result.stdout


def _selftest_main(folder: str, expected: str) -> int:
    sys.path.insert(0, folder)
    try:
        import yt_dlp
        from yt_dlp.extractor.youtube import YoutubeIE  # noqa: F401
        from yt_dlp.version import __version__ as loaded

        if not Path(yt_dlp.__file__).resolve().is_relative_to(Path(folder).resolve()):
            print(f"SELFTEST FAIL loaded from {yt_dlp.__file__}")
            return 1
        if parse_version(loaded) != parse_version(expected):
            print(f"SELFTEST FAIL version {loaded} != {expected}")
            return 1
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}):
            pass
    except Exception as error:  # noqa: BLE001 - report any import failure
        print(f"SELFTEST FAIL {type(error).__name__}: {error}")
        return 1
    print(f"SELFTEST OK {loaded}")
    return 0


# --------------------------------------------------------------- entry hook
def handle_runtime_args(argv: list[str]) -> int | None:
    """Handle yt-dlp maintenance flags before the CLI (and yt-dlp) is imported.

    Returns an exit code when a flag was handled, otherwise activates the
    external yt-dlp for the upcoming CLI run and returns None.
    """
    from streamgrab.gui_support import configure_output_streams

    # These commands print Korean messages before cli.main() would set up the
    # streams, so match the GUI's UTF-8 decoding here as well.
    configure_output_streams()
    if argv[:1] == ["--ytdlp-selftest"] and len(argv) == 3:
        return _selftest_main(argv[1], argv[2])
    if argv[:1] == ["--ytdlp-status"]:
        version, source = active_version()
        print(STATUS_PREFIX + UpdateResult(version, source).as_json(), flush=True)
        return 0
    if argv[:1] == ["--update-ytdlp"]:
        result = check_and_update(force="--force" in argv[1:])
        print(result.message, flush=True)
        print(STATUS_PREFIX + result.as_json(), flush=True)
        return 0 if "실패" not in result.message else 1
    activate()
    return None
