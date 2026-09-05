"""Allow StreamGrab to run with ``python -m streamgrab``."""

import sys

from streamgrab.cli import main


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if arguments[:1] == ["--cli"]:
        arguments = arguments[1:]
    raise SystemExit(main(arguments))
