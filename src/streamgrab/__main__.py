"""Allow StreamGrab to run with ``python -m streamgrab``."""

import sys

from streamgrab.ytdlp_runtime import handle_runtime_args


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if arguments[:1] == ["--cli"]:
        arguments = arguments[1:]
    handled = handle_runtime_args(arguments)
    if handled is not None:
        raise SystemExit(handled)

    from streamgrab.cli import main

    raise SystemExit(main(arguments))
