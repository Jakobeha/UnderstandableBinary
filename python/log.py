import logging
import os
import sys

# Extra verbose log level
EXTRA_VERBOSE = 5

log: logging.Logger


def setup(log_level):
    if log_level == "EXTRA_VERBOSE":
        log_level = EXTRA_VERBOSE

    global log
    log = logging.getLogger("UnderstandableBinary")
    log.setLevel(log_level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.NOTSET)
    handler.setFormatter(logging.Formatter('[%(asctime)s %(name)s] %(levelname)s: %(message)s'))
    log.addHandler(handler)


setup(os.getenv("LOG_LEVEL", "INFO"))
