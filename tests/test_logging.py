import logging

from streamgrab.logging import configure_logging


def test_debug_logging_level() -> None:
    logger = configure_logging(debug=True)

    assert logger.level == logging.DEBUG


def test_logging_does_not_add_duplicate_handlers() -> None:
    logger = configure_logging()
    handler_count = len(logger.handlers)

    configure_logging()

    assert len(logger.handlers) == handler_count

