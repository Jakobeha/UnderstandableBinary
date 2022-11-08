import logging
import os
import sys
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

# Extra verbose log level
EXTRA_VERBOSE = 5

log: logging.Logger


def logging_progress(desc: str, iterator=None, level=None, logger=None, total=None):
    """Returns `iterator` but displays a progress bar while iterating"""
    logger = logger or log
    level = level or logging.INFO

    if logger.level > level:
        return iterator
    else:
        log.log(level, desc)
        with logging_redirect_tqdm(loggers=[logger], tqdm_class=tqdm):
            for item in tqdm(iterator, total=total):
                yield item

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

