"""Allow StreamGrab to run with ``python -m streamgrab``."""

from streamgrab.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

