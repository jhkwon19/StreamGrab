from streamgrab.extractors import pipeline
from streamgrab.extractors.pipeline import ExtractionPipeline
from streamgrab.models import StreamType
from streamgrab.network import PageResponse


def test_static_pipeline_follows_iframe_and_preserves_referer(monkeypatch) -> None:
    requested: list[tuple[str, str | None]] = []

    def fake_fetch_page(url, timeout, referer=None):
        requested.append((url, referer))
        if url == "https://example.com/watch/1":
            html = '<title>Watch</title><iframe src="https://player.example/embed/1">'
        else:
            html = '<video src="https://media.example/master.m3u8"></video>'
        return PageResponse(url=url, text=html, content_type="text/html")

    monkeypatch.setattr(pipeline, "fetch_page", fake_fetch_page)

    streams = ExtractionPipeline().extract_static("https://example.com/watch/1", 30)

    assert requested == [
        ("https://example.com/watch/1", None),
        ("https://player.example/embed/1", "https://example.com/watch/1"),
    ]
    assert len(streams) == 1
    assert streams[0].stream_type is StreamType.HLS
    assert streams[0].referer == "https://player.example/embed/1"


def test_static_pipeline_deduplicates_embedded_candidates(monkeypatch) -> None:
    html = """
    <video src="https://media.example/video.mp4"></video>
    <script>const file = "https://media.example/video.mp4"</script>
    """
    monkeypatch.setattr(
        pipeline,
        "fetch_page",
        lambda url, timeout, referer=None: PageResponse(url, html, "text/html"),
    )

    streams = ExtractionPipeline().extract_static("https://example.com/watch/1", 30)

    assert [stream.url for stream in streams] == [
        "https://media.example/video.mp4"
    ]
