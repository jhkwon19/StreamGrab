"""Exceptions shared by StreamGrab modules."""


class StreamGrabError(Exception):
    """Base class for expected StreamGrab errors."""


class ConfigError(StreamGrabError):
    """Raised when a configuration file is invalid or cannot be read."""


class InvalidURLError(StreamGrabError):
    """Raised when a URL cannot be safely handled."""


class NetworkError(StreamGrabError):
    """Raised when an HTTP request fails."""


class StreamNotFoundError(StreamGrabError):
    """Raised when no supported stream is present on a page."""


class UnsupportedStreamError(StreamGrabError):
    """Raised when a discovered stream has no downloader yet."""


class DownloadError(StreamGrabError):
    """Raised when media cannot be saved."""


class FFmpegError(DownloadError):
    """Raised when FFmpeg is missing or exits unsuccessfully."""

