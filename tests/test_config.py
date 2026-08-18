from pathlib import Path

import pytest

from streamgrab.config import AppConfig, load_config
from streamgrab.exceptions import ConfigError


def test_load_config_uses_defaults() -> None:
    assert load_config() == AppConfig()


def test_load_config_reads_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "streamgrab.toml"
    config_path.write_text(
        '\n'.join(
            [
                'output_directory = "media"',
                'default_quality = "1080p"',
                "[retry]",
                "count = 5",
                "[network]",
                "timeout = 12.5",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.output_directory == Path("media")
    assert config.default_quality == "1080p"
    assert config.retry_count == 5
    assert config.network_timeout == 12.5


def test_load_config_rejects_unknown_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "streamgrab.toml"
    config_path.write_text("unexpected = true", encoding="utf-8")

    with pytest.raises(ConfigError, match="지원하지 않는 설정 항목"):
        load_config(config_path)


def test_load_config_rejects_unknown_nested_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "streamgrab.toml"
    config_path.write_text("[network]\nretries = 2", encoding="utf-8")

    with pytest.raises(ConfigError, match="network.retries"):
        load_config(config_path)
