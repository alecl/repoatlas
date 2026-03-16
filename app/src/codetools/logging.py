import logging
import os

# Create a logger for the codetools module
logger = logging.getLogger("codetools")


# Configure based on environment variable
def configure_logging():
    # Default handler to avoid "No handler found" warnings
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    # Check environment variable
    log_level = os.environ.get("CODETOOLS_LOG_LEVEL", "INFO").upper()
    print(f"Setting log level to {log_level}")

    # Map log levels (TRACE is handled separately)
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    # If the env level is TRACE, set the logger level to DEBUG so trace messages (handled as DEBUG)
    # will be visible, and patch logger.trace accordingly.
    if log_level == "TRACE":
        logger.setLevel(logging.DEBUG)

        def trace(msg, *args, **kwargs):
            # You can optionally prefix the message with a marker if desired.
            logger.debug("[TRACE] " + str(msg), *args, **kwargs)

        logger.trace = trace
    else:
        # Set logger level using our map, defaulting to INFO
        logger.setLevel(level_map.get(log_level, logging.INFO))
        # Disable trace logging
        logger.trace = lambda *args, **kwargs: None

    # Add a stream handler if in debug mode (or if TRACE is enabled which uses debug level)
    if logger.level <= logging.DEBUG:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)


# Configure the logger when this module is imported
configure_logging()
