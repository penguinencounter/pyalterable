import logging
from typing import NoReturn, Optional, Protocol
from collections.abc import Callable


class StopProtocol(Protocol):
    def __call__(self, reason: str, colorize: bool = ...) -> NoReturn:
        ...


def mk_stop(log: logging.Logger) -> StopProtocol:
    def stop(reason: str, colorize: bool = False) -> NoReturn:
        log.critical(reason, extra={"markup": colorize})
        exit(1)

    return stop
