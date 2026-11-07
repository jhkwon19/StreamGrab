import json

from streamgrab.extractors import browser
from streamgrab.extractors.browser import (
    BrowserNetworkExtractor,
    _browser_title,
    _is_challenge_event,
    _record_event,
    _stream_type,
)
from streamgrab.models import StreamInfo, StreamType


def test_browser_network_response_detects_extensionless_hls() -> None:
    candidates = {}
    referers = {}
    _record_event(
        {
            "method": "Network.requestWillBeSent",
            "params": {
                "requestId": "42",
                "documentURL": "https://player.example/embed/1",
                "request": {"url": "https://media.example/play?id=1", "headers": {}},
            },
        },
        "https://example.com/watch/1",
        candidates,
        referers,
    )
    _record_event(
        {
            "method": "Network.responseReceived",
            "params": {
                "requestId": "42",
                "type": "Fetch",
                "response": {
                    "url": "https://media.example/play?id=1",
                    "mimeType": "application/vnd.apple.mpegurl",
                },
            },
        },
        "https://example.com/watch/1",
        candidates,
        referers,
    )

    assert candidates == {
        "https://media.example/play?id=1": (
            StreamType.HLS,
            "https://player.example/embed/1",
        )
    }


def test_browser_recognizes_dash_mime_type() -> None:
    assert (
        _stream_type(
            "https://media.example/manifest?id=1",
            "application/dash+xml",
            "Fetch",
        )
        is StreamType.DASH
    )


def test_browser_title_reads_runtime_value() -> None:
    class FakeClient:
        def command(self, method, params=None):
            return {
                "result": {
                    "type": "string",
                    "value": '{"title":"Page title","href":"https://example.com"}',
                }
            }

    assert _browser_title(FakeClient()) == "Page title"


def test_detects_cloudflare_challenge_response() -> None:
    event = {
        "method": "Network.responseReceived",
        "params": {
            "response": {
                "url": "https://example.com/watch/1",
                "status": 403,
                "headers": {"cf-mitigated": "challenge"},
            }
        },
    }

    assert _is_challenge_event(event, "https://example.com/watch/1")


def test_retries_cloudflare_challenge_in_visible_browser(monkeypatch) -> None:
    attempts: list[bool] = []
    expected = StreamInfo(
        url="https://media.example/master.m3u8",
        title="Example",
        stream_type=StreamType.HLS,
    )
    monkeypatch.setattr(browser, "find_chromium_browser", lambda: "browser.exe")

    def fake_extract(*args, headless):
        attempts.append(headless)
        if headless:
            raise browser._ChallengeRequired
        return [expected]

    monkeypatch.setattr(browser, "_extract_with_browser", fake_extract)

    assert BrowserNetworkExtractor().extract("https://example.com/watch/1", 10) == [
        expected
    ]
    assert attempts == [True, False]


def test_wait_for_browser_survives_edge_launcher_handoff(monkeypatch) -> None:
    payload = {"webSocketDebuggerUrl": "ws://127.0.0.1/devtools/browser/1"}

    class ExitedLauncher:
        def poll(self):
            return 0

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps(payload).encode()

    monkeypatch.setattr(browser, "urlopen", lambda *_args, **_kwargs: Response())

    assert browser._wait_for_json(1234, "/json/version", ExitedLauncher(), 1) == payload
