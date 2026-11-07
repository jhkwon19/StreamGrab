from streamgrab.extractors.generic import GenericExtractor
from streamgrab.models import StreamType


def test_extracts_video_data_source() -> None:
    html = """
    <html>
      <head><title>Page title</title></head>
      <body>
        <video title="Video title" data-source="/media/master.m3u8"></video>
      </body>
    </html>
    """

    streams = GenericExtractor().extract("https://example.com/watch/1", html)

    assert len(streams) == 1
    assert streams[0].url == "https://example.com/media/master.m3u8"
    assert streams[0].title == "Video title"
    assert streams[0].stream_type is StreamType.HLS
    assert streams[0].referer == "https://example.com/watch/1"


def test_extracts_source_and_removes_duplicates() -> None:
    html = """
    <title>Example</title>
    <video src="https://cdn.example/video.mp4">
      <source src="https://cdn.example/video.mp4" type="video/mp4">
      <source src="https://cdn.example/video.webm" type="video/webm">
    </video>
    """

    streams = GenericExtractor().extract("https://example.com", html)

    assert [stream.stream_type for stream in streams] == [
        StreamType.DIRECT,
        StreamType.DIRECT,
    ]


def test_ignores_unsupported_sources() -> None:
    streams = GenericExtractor().extract(
        "https://example.com", '<video src="javascript:alert(1)"></video>'
    )

    assert streams == []


def test_ignores_non_http_media_url() -> None:
    streams = GenericExtractor().extract(
        "https://example.com", '<video src="data:video/mp4;base64,AAAA"></video>'
    )

    assert streams == []


def test_extracts_preloaded_hls_fetch() -> None:
    html = """
    <title>Embedded player</title>
    <link rel="preload" as="fetch" href="/playlist/index.m3u8" crossorigin>
    """

    streams = GenericExtractor().extract("https://player.example/embed/1", html)

    assert len(streams) == 1
    assert streams[0].url == "https://player.example/playlist/index.m3u8"
    assert streams[0].referer == "https://player.example/embed/1"


def test_extracts_media_url_from_inline_player_script() -> None:
    html = r'''<script>player.mount("https:\/\/media.example\/index.m3u8")</script>'''

    streams = GenericExtractor().extract("https://example.com/watch/1", html)

    assert [stream.url for stream in streams] == [
        "https://media.example/index.m3u8"
    ]
