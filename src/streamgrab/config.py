"""Application configuration and TOML loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import Any

from streamgrab.exceptions import ConfigError


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime settings with safe defaults for the CLI."""

    output_directory: Path = Path("downloads")
    default_quality: str = "best"
    retry_count: int = 3
    network_timeout: float = 30.0


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from *path*, or return defaults when omitted."""

    if path is None:
        return AppConfig()

    try:
        with path.open("rb") as config_file:
            raw = tomllib.load(config_file)
    except FileNotFoundError as error:
        raise ConfigError(f"설정 파일을 찾을 수 없습니다: {path}") from error
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"설정 파일을 읽을 수 없습니다: {path}: {error}") from error

    _validate_root_keys(raw)
    retry = _table(raw, "retry")
    network = _table(raw, "network")

    output_directory = _value(raw, "output_directory", str, "downloads")
    default_quality = _value(raw, "default_quality", str, "best")
    retry_count = _value(retry, "count", int, 3)
    network_timeout = _number_value(network, "timeout", 30.0)

    if not default_quality.strip():
        raise ConfigError("default_quality는 빈 문자열일 수 없습니다")
    if retry_count < 0:
        raise ConfigError("retry.count는 0 이상이어야 합니다")
    if network_timeout <= 0:
        raise ConfigError("network.timeout은 0보다 커야 합니다")

    return AppConfig(
        output_directory=Path(output_directory).expanduser(),
        default_quality=default_quality,
        retry_count=retry_count,
        network_timeout=network_timeout,
    )


def _validate_root_keys(raw: dict[str, Any]) -> None:
    supported = {"output_directory", "default_quality", "retry", "network"}
    unknown = sorted(set(raw) - supported)
    if unknown:
        raise ConfigError(f"지원하지 않는 설정 항목: {', '.join(unknown)}")

    _validate_table_keys(raw, "retry", {"count"})
    _validate_table_keys(raw, "network", {"timeout"})


def _validate_table_keys(
    raw: dict[str, Any], table_name: str, supported: set[str]
) -> None:
    table = _table(raw, table_name)
    unknown = sorted(set(table) - supported)
    if unknown:
        names = ", ".join(f"{table_name}.{key}" for key in unknown)
        raise ConfigError(f"지원하지 않는 설정 항목: {names}")


def _table(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{name}은 TOML 테이블이어야 합니다")
    return value


def _value(
    raw: dict[str, Any], key: str, expected_type: type, default: Any
) -> Any:
    value = raw.get(key, default)
    if not isinstance(value, expected_type) or (
        expected_type is int and isinstance(value, bool)
    ):
        raise ConfigError(f"{key}의 값 형식이 올바르지 않습니다")
    return value


def _number_value(raw: dict[str, Any], key: str, default: float) -> float:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{key}의 값 형식이 올바르지 않습니다")
    return float(value)
