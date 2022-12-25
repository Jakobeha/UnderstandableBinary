import logging
import os
import sys
from typing import Optional, Iterable

from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from utils import T

# Extra verbose log level
EXTRA_VERBOSE = 5

log: logging.Logger


class _PbarStub:
    def update(self, n):
        pass


class WithLoggingPbar:
    def __init__(self, logging_redirect_tdqm, tdqm):
        self.logging_redirect_tdqm = logging_redirect_tdqm
        self.tdqm = tdqm

    def __enter__(self):
        if self.logging_redirect_tdqm is not None:
            self.logging_redirect_tdqm.__enter__()
        if self.tdqm is not None:
            return self.tdqm.__enter__()
        else:
            return _PbarStub()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.tdqm is not None:
            self.tdqm.__exit__(exc_type, exc_val, exc_tb)
        if self.logging_redirect_tdqm is not None:
            self.logging_redirect_tdqm.__exit__(exc_type, exc_val, exc_tb)


def logging_progress(
        iterator: Iterable[T],
        desc: Optional[str] = None,
        level: int = None,
        logger: Optional[logging.Logger] = None,
        position: Optional[int] = None,
        leave: bool = True,
        total: Optional[int] = None) -> Iterable[T]:
    """Returns `iterator` but displays a progress bar while iterating."""
    logger = logger or log
    level = level or logging.INFO

    if logger.level > level:
        return iterator
    else:
        if desc is not None:
            log.log(level, desc)
        with logging_redirect_tqdm(loggers=[logger], tqdm_class=tqdm):
            for item in tqdm(iterator, position=position, leave=leave, total=total):
                yield item


def logging_progress_bar(
        desc: Optional[str] = None,
        level: int = None,
        logger: Optional[logging.Logger] = None,
        position: Optional[int] = None,
        leave: bool = True,
        total: Optional[int] = None) -> WithLoggingPbar:
    """Passes a progress bar you can use in a method"""
    logger = logger or log
    level = level or logging.INFO

    if logger.level > level:
        return WithLoggingPbar(None, None)
    else:
        if desc is not None:
            log.log(level, desc)
        return WithLoggingPbar(
            logging_redirect_tqdm(loggers=[logger], tqdm_class=tqdm),
            tqdm(position=position, leave=leave, total=total)
        )


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

