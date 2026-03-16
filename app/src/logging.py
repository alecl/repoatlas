import logging
import os
import sys
from typing import Any

# Create a logger for the codetools module
logger: Any = logging.getLogger("codetools")

# read once, at import time
_SHOW_EXCEPTION_TRACE = os.environ.get("CODETOOLS_LOG_EXCEPTION_TRACE", "false").lower() in (
    "1",
    "true",
    "yes",
)


def configure_logging():
    # -- your existing setup --
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    log_level = os.environ.get("CODETOOLS_LOG_LEVEL", "INFO").upper()
    print(f"Setting log level to {log_level}")
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    if log_level == "TRACE":
        logger.setLevel(logging.DEBUG)

        def trace(msg, *args, **kwargs):
            logger.debug("[TRACE] " + str(msg), *args, **kwargs)

        logger.trace = trace
    else:
        logger.setLevel(level_map.get(log_level, logging.INFO))
        logger.trace = lambda *args, **kwargs: None

    if logger.level <= logging.DEBUG:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # -- end of existing setup --

    # now monkey‐patch all the methods so they inject exc_info if desired
    def _wrap(orig):
        def wrapped(msg, *args, **kwargs):
            # if we're in an exception handler AND user didn't explicitly pass exc_info
            if (
                _SHOW_EXCEPTION_TRACE
                and "exc_info" not in kwargs
                and sys.exc_info()[0] is not None
            ):
                kwargs["exc_info"] = True
            return orig(msg, *args, **kwargs)

        return wrapped

    for name in (
        "debug",
        "info",
        "warning",
        "warn",
        "error",
        "critical",
        "exception",
        "trace",
    ):
        # grab the existing bound method
        orig = getattr(logger, name)
        # replace it with our wrapper
        setattr(logger, name, _wrap(orig))


# configure at import time
configure_logging()
