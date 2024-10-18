from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from tenacity import Retrying, stop_after_attempt, wait_fixed

WrappedFnR = TypeVar("WrappedFnR")


@dataclass
class RetryStrategy:
    attempts: int = 0
    delay: int = 0

    # This method currently retries a function when any exception occurs.
    def retry(self, fn: Callable[..., WrappedFnR], *args: any, **kwargs: any) -> WrappedFnR:
        retryer = Retrying(stop=stop_after_attempt(self.attempts), wait=wait_fixed(self.delay))
        return retryer(fn, *args, **kwargs)
