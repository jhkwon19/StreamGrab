"""Last-resort media discovery through an installed Chromium browser."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from typing import Any
from urllib.error import URLError
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

from websockets.exceptions import WebSocketException
from websockets.sync.client import ClientConnection, connect

from streamgrab.exceptions import StreamNotFoundError
from streamgrab.extractors.generic import detect_stream_type
from streamgrab.models import StreamInfo, StreamType


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
logger = logging.getLogger("streamgrab")
_PLAY_EXPRESSION = r"""
(() => {
  for (const video of document.querySelectorAll('video')) {
    video.muted = true;
    video.play().catch(() => {});
  }
  for (const element of document.querySelectorAll(
    '.vjs-big-play-button,.jw-icon-playback,.plyr__control--overlaid'
  )) {
    try { element.click(); } catch (_) {}
  }
})()
"""


class BrowserNetworkExtractor:
    """Observe real media requests made by Edge or Chrome in headless mode."""

    def extract(self, page_url: str, timeout: float) -> list[StreamInfo]:
        executable = find_chromium_browser()
        if executable is None:
            raise StreamNotFoundError(
                "자동 브라우저 분석에 사용할 Microsoft Edge 또는 Chrome을 찾지 못했습니다"
            )

        observation_time = min(max(timeout, 8.0), 20.0)
        port = _available_port()
        profile = browser_profile_directory()
        profile.mkdir(parents=True, exist_ok=True)
        try:
            return _extract_with_browser(
                executable,
                port,
                str(profile),
                page_url,
                observation_time,
                headless=True,
            )
        except _ChallengeRequired:
            logger.info(
                "Cloudflare 확인을 위해 전용 브라우저 창을 엽니다. "
                "확인 화면이 나타나면 완료해 주세요"
            )
            port = _available_port()
            try:
                return _extract_with_browser(
                    executable,
                    port,
                    str(profile),
                    page_url,
                    max(45.0, observation_time),
                    headless=False,
                )
            except _ChallengeRequired as error:
                raise StreamNotFoundError(
                    "브라우저의 Cloudflare 확인을 완료하지 못했습니다"
                ) from error
            except (OSError, URLError, ValueError, WebSocketException, TimeoutError) as error:
                raise StreamNotFoundError(
                    f"화면 표시 브라우저 분석에 실패했습니다: {error}"
                ) from error
        except (OSError, URLError, ValueError, WebSocketException, TimeoutError) as error:
            raise StreamNotFoundError(
                f"브라우저 네트워크 분석에 실패했습니다: {error}"
            ) from error


def browser_profile_directory() -> Path:
    if os.name == "nt" and (local := os.environ.get("LOCALAPPDATA")):
        return Path(local) / "StreamGrab" / "browser-profile"
    return Path.home() / ".cache" / "streamgrab" / "browser-profile"


def _extract_with_browser(
    executable: str,
    port: int,
    profile: str,
    page_url: str,
    timeout: float,
    *,
    headless: bool,
) -> list[StreamInfo]:
    process = _launch_browser(executable, port, profile, headless=headless)
    browser_websocket: str | None = None
    try:
        version = _wait_for_json(port, "/json/version", process, 8.0)
        browser_websocket = str(version.get("webSocketDebuggerUrl") or "") or None
        targets = _wait_for_json(port, "/json/list", process, 5.0)
        target = next(
            (
                item
                for item in targets
                if item.get("type") == "page" and item.get("webSocketDebuggerUrl")
            ),
            None,
        )
        if target is None:
            raise StreamNotFoundError("브라우저 분석 탭을 열지 못했습니다")
        return _observe_page(
            str(target["webSocketDebuggerUrl"]),
            page_url,
            timeout,
            str(version.get("User-Agent") or "") or None,
            challenge_grace=6.0 if headless else timeout,
        )
    finally:
        if browser_websocket:
            _close_browser(browser_websocket)
        _stop_browser(process)


def find_chromium_browser() -> str | None:
    names = (
        ("msedge.exe", "chrome.exe", "chromium.exe")
        if os.name == "nt"
        else ("microsoft-edge", "google-chrome", "chromium", "chromium-browser")
    )
    for name in names:
        if discovered := shutil.which(name):
            return discovered

    candidates: list[Path] = []
    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        program_files = Path(os.environ.get("PROGRAMFILES", ""))
        program_files_x86 = Path(os.environ.get("PROGRAMFILES(X86)", ""))
        candidates.extend(
            [
                program_files_x86 / "Microsoft/Edge/Application/msedge.exe",
                program_files / "Microsoft/Edge/Application/msedge.exe",
                program_files / "Google/Chrome/Application/chrome.exe",
                local / "Google/Chrome/Application/chrome.exe",
            ]
        )
    elif sys_platform() == "darwin":
        candidates.extend(
            [
                Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            ]
        )
    return str(next((path for path in candidates if path.is_file()), "")) or None


def sys_platform() -> str:
    import sys

    return sys.platform


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _launch_browser(
    executable: str, port: int, profile: str, *, headless: bool
) -> subprocess.Popen[str]:
    command = [
        executable,
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-extensions",
        "--disable-gpu",
        "--edge-skip-compat-layer-relaunch",
        "--mute-audio",
        "--no-default-browser-check",
        "--no-first-run",
        "--remote-allow-origins=*",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "about:blank",
    ]
    if headless:
        command.insert(1, "--headless=new")
    else:
        command.insert(1, "--window-size=1100,800")
    try:
        return subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=_NO_WINDOW,
        )
    except OSError as error:
        raise StreamNotFoundError(f"브라우저를 실행할 수 없습니다: {error}") from error


def _wait_for_json(
    port: int, path: str, process: subprocess.Popen[str], timeout: float
) -> Any:
    deadline = time.monotonic() + timeout
    address = f"http://127.0.0.1:{port}{path}"
    last_error: Exception | None = None
    launcher_exited = False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            # Edge can replace its short-lived launcher with the real browser
            # process. The debugging endpoint may become ready just after that
            # hand-off, so an exited Popen handle is not sufficient evidence
            # that the browser itself failed.
            launcher_exited = True
        try:
            with urlopen(address, timeout=0.5) as response:
                return json.loads(response.read(1024 * 1024).decode("utf-8"))
        except (OSError, URLError, ValueError) as error:
            last_error = error
            time.sleep(0.1)
    if launcher_exited:
        raise StreamNotFoundError(
            "자동 분석 브라우저가 디버깅 연결 전에 종료되었습니다"
        )
    raise StreamNotFoundError(f"브라우저 연결 시간이 초과되었습니다: {last_error}")


def _observe_page(
    websocket_url: str,
    page_url: str,
    timeout: float,
    user_agent: str | None,
    *,
    challenge_grace: float,
) -> list[StreamInfo]:
    with connect(
        websocket_url,
        open_timeout=5,
        close_timeout=2,
        max_size=4 * 1024 * 1024,
    ) as websocket:
        client = _CDPClient(websocket)
        client.command("Network.enable")
        client.command("Page.enable")
        client.command("Runtime.enable")
        client.command(
            "Target.setAutoAttach",
            {
                "autoAttach": True,
                "waitForDebuggerOnStart": False,
                "flatten": True,
            },
        )
        client.command("Page.navigate", {"url": page_url})

        candidates: dict[str, tuple[StreamType, str | None]] = {}
        request_referers: dict[str, str | None] = {}
        deadline = time.monotonic() + timeout
        play_at = time.monotonic() + 2.0
        stop_after: float | None = None
        play_triggered = False
        challenge_detected = False
        challenge_started: float | None = None

        while time.monotonic() < deadline:
            now = time.monotonic()
            if not play_triggered and now >= play_at:
                client.command(
                    "Runtime.evaluate",
                    {"expression": _PLAY_EXPRESSION, "returnByValue": True},
                )
                play_triggered = True
            event = client.event(timeout=min(0.5, max(0.01, deadline - now)))
            if event:
                challenge_detected = challenge_detected or _is_challenge_event(
                    event, page_url
                )
                if challenge_detected and challenge_started is None:
                    challenge_started = time.monotonic()
                if event.get("method") == "Target.attachedToTarget":
                    attached = event.get("params") or {}
                    target_type = str((attached.get("targetInfo") or {}).get("type") or "")
                    session_id = str(attached.get("sessionId") or "")
                    if session_id and target_type in {"iframe", "page"}:
                        try:
                            client.command("Network.enable", session_id=session_id)
                        except (StreamNotFoundError, TimeoutError):
                            pass
                _record_event(event, page_url, candidates, request_referers)
                if candidates and stop_after is None:
                    stop_after = max(play_at + 4.0, time.monotonic() + 3.0)
            if stop_after is not None and time.monotonic() >= stop_after:
                break
            if (
                challenge_started is not None
                and not candidates
                and time.monotonic() >= challenge_started + challenge_grace
            ):
                break

        title, final_url = _browser_page_info(client)
        title = title or _title_from_url(page_url)
        logger.debug("브라우저 분석 최종 페이지: %s", final_url)
        if not candidates and (
            challenge_detected or title.lower() in {"just a moment...", "잠시만 기다리십시오..."}
        ):
            raise _ChallengeRequired
        ranked = sorted(
            candidates.items(),
            key=lambda item: _candidate_score(item[0], item[1][0]),
            reverse=True,
        )
        return [
            StreamInfo(
                url=url,
                title=title,
                stream_type=stream_type,
                referer=referer or page_url,
                user_agent=user_agent,
            )
            for url, (stream_type, referer) in ranked
        ]


def _record_event(
    event: dict[str, Any],
    page_url: str,
    candidates: dict[str, tuple[StreamType, str | None]],
    request_referers: dict[str, str | None],
) -> None:
    method = event.get("method")
    params = event.get("params") or {}
    request_id = str(params.get("requestId") or "")
    if method == "Network.requestWillBeSent":
        request = params.get("request") or {}
        headers = request.get("headers") or {}
        referer = _header(headers, "referer") or params.get("documentURL") or page_url
        request_referers[request_id] = str(referer) if referer else None
        url = str(request.get("url") or "")
        if stream_type := _stream_type(url, None, str(params.get("type") or "")):
            candidates.setdefault(url, (stream_type, request_referers[request_id]))
    elif method == "Network.responseReceived":
        response = params.get("response") or {}
        url = str(response.get("url") or "")
        mime_type = str(response.get("mimeType") or "")
        resource_type = str(params.get("type") or "")
        if stream_type := _stream_type(url, mime_type, resource_type):
            candidates[url] = (
                stream_type,
                request_referers.get(request_id) or page_url,
            )


def _is_challenge_event(event: dict[str, Any], page_url: str) -> bool:
    if event.get("method") != "Network.responseReceived":
        return False
    response = (event.get("params") or {}).get("response") or {}
    if str(response.get("url") or "").split("#", 1)[0] != page_url.split("#", 1)[0]:
        return False
    headers = response.get("headers") or {}
    return (
        int(response.get("status") or 0) == 403
        and (_header(headers, "cf-mitigated") or "").lower() == "challenge"
    )


def _stream_type(url: str, mime_type: str | None, resource_type: str) -> StreamType | None:
    if not url.startswith(("http://", "https://")):
        return None
    if detected := detect_stream_type(url):
        return detected
    mime = (mime_type or "").lower()
    if "mpegurl" in mime or "vnd.apple.mpegurl" in mime:
        return StreamType.HLS
    if "dash+xml" in mime:
        return StreamType.DASH
    if mime.startswith("video/") and mime not in {"video/mp2t"}:
        return StreamType.DIRECT
    if resource_type == "Media" and mime in {"application/octet-stream", "binary/octet-stream"}:
        return StreamType.DIRECT
    return None


def _candidate_score(url: str, stream_type: StreamType) -> int:
    score = {
        StreamType.HLS: 300,
        StreamType.DASH: 250,
        StreamType.DIRECT: 100,
    }[stream_type]
    path = urlsplit(url).path.lower()
    if any(word in path for word in ("master", "index", "playlist", "manifest")):
        score += 20
    return score


def _header(headers: dict[str, Any], name: str) -> str | None:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered and value:
            return str(value)
    return None


def _browser_title(client: _CDPClient) -> str:
    return _browser_page_info(client)[0]


def _browser_page_info(client: _CDPClient) -> tuple[str, str]:
    try:
        result = client.command(
            "Runtime.evaluate",
            {
                "expression": (
                    "JSON.stringify({title: document.title, href: location.href})"
                ),
                "returnByValue": True,
            },
        )
        value = (result.get("result") or {}).get("value")
        data = json.loads(str(value)) if value else {}
        return str(data.get("title") or "").strip(), str(data.get("href") or "")
    except (StreamNotFoundError, ValueError, WebSocketException, json.JSONDecodeError):
        return "", ""


def _title_from_url(url: str) -> str:
    return unquote(urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]) or "video"


def _stop_browser(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _close_browser(websocket_url: str) -> None:
    try:
        with connect(
            websocket_url,
            open_timeout=2,
            close_timeout=1,
            max_size=1024 * 1024,
        ) as websocket:
            websocket.send(json.dumps({"id": 1, "method": "Browser.close"}))
            try:
                websocket.recv(timeout=1)
            except (TimeoutError, WebSocketException):
                pass
    except (OSError, ValueError, WebSocketException, TimeoutError):
        pass


class _CDPClient:
    def __init__(self, websocket: ClientConnection) -> None:
        self.websocket = websocket
        self.next_id = 1
        self.events: list[dict[str, Any]] = []

    def command(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        command_id = self.next_id
        self.next_id += 1
        payload: dict[str, Any] = {
            "id": command_id,
            "method": method,
            "params": params or {},
        }
        if session_id:
            payload["sessionId"] = session_id
        self.websocket.send(json.dumps(payload))
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            try:
                raw = self.websocket.recv(
                    timeout=max(0.01, deadline - time.monotonic())
                )
            except TimeoutError as error:
                raise StreamNotFoundError(
                    f"브라우저 명령 {method} 응답 시간이 초과되었습니다"
                ) from error
            message = json.loads(str(raw))
            if message.get("id") == command_id:
                if error := message.get("error"):
                    raise StreamNotFoundError(
                        f"브라우저 명령 {method} 실패: {error.get('message', error)}"
                    )
                return message.get("result") or {}
            if message.get("method"):
                self.events.append(message)
        raise StreamNotFoundError(f"브라우저 명령 {method} 응답 시간이 초과되었습니다")

    def event(self, timeout: float) -> dict[str, Any] | None:
        if self.events:
            return self.events.pop(0)
        try:
            raw = self.websocket.recv(timeout=timeout)
        except TimeoutError:
            return None
        message = json.loads(str(raw))
        return message if message.get("method") else None


class _ChallengeRequired(Exception):
    pass
