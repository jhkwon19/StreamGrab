from pathlib import Path

from streamgrab.filenames import output_path, safe_filename
from streamgrab.models import StreamInfo, StreamType


def test_safe_filename_replaces_invalid_characters() -> None:
    assert safe_filename('a/b:c*?"<>|') == "a_b_c______"


def test_output_path_avoids_existing_file(tmp_path: Path) -> None:
    stream = StreamInfo(
        url="https://example.com/master.m3u8",
        title="Example",
        stream_type=StreamType.HLS,
    )
    (tmp_path / "Example.mp4").touch()

    assert output_path(stream, tmp_path) == tmp_path / "Example (1).mp4"

