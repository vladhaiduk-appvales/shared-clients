from __future__ import annotations

from functools import cached_property, partial, wraps
from typing import Callable, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    Retrying,
    after_nothing,
    before_nothing,
    retry_any,
    retry_base,
    retry_if_exception,
    retry_if_exception_type,
    retry_if_result,
    retry_never,
    stop_after_attempt,
    wait_fixed,
)
from tenacity import RetryCallState as RetryState

RETRY_ATTR = "__retry__"
RETRY_ON_EXCEPTION_ATTR = "__retry_on_exception__"
RETRY_ON_RESULT_ATTR = "__retry_on_result__"

RETRY_METHODS_ATTR = "__retry_methods__"
RETRY_ON_EXCEPTION_METHODS_ATTR = "__retry_on_exception_methods__"
RETRY_ON_RESULT_METHODS_ATTR = "__retry_on_result_methods__"


def retry(fn: Callable[[RetryState], bool]) -> Callable[[RetryState], bool]:
    """Decorate a method to check for retry based on retry state.

    Methods with this decorator will always execute to check for retry, regardless of errors or success.
    """
    if hasattr(fn, RETRY_ON_EXCEPTION_ATTR):
        raise AttributeError(f"method '{fn.__name__}' is already marked for retry on exception")
    if hasattr(fn, RETRY_ON_RESULT_ATTR):
        raise AttributeError(f"method '{fn.__name__}' is already marked for retry on result")

    setattr(fn, RETRY_ATTR, True)
    return fn


def retry_on_exception(
    fn: Callable[[BaseException], bool] | None = None,
    *,
    exc_types: type[BaseException] | tuple[type[BaseException], ...] | None = None,
) -> Callable[[BaseException], bool]:
    """Decorate a method to check for retry based on exception.

    Methods with this decorator will only execute to check for retry if the method's outcome is an exception.
    """
    if fn is None:
        return partial(retry_on_exception, exc_types=exc_types)

    if hasattr(fn, RETRY_ATTR):
        raise AttributeError(f"method '{fn.__name__}' is already marked for retry")
    if hasattr(fn, RETRY_ON_RESULT_ATTR):
        raise AttributeError(f"method '{fn.__name__}' is already marked for retry on result")

    @wraps(fn)
    def wrapper(self: RetryStrategy, *args: any, **kwargs: any) -> bool:
        if exc_types and isinstance(args[0], exc_types):
            return fn(self, *args, **kwargs)
        return False

    setattr(wrapper, RETRY_ON_EXCEPTION_ATTR, True)
    return wrapper


def retry_on_result(fn: Callable[[any], bool]) -> Callable[[any], bool]:
    """Decorate a method to check for retry based on result.

    Methods with this decorator will only execute to check for retry if the method's outcome is not an exception.
    """
    if hasattr(fn, RETRY_ATTR):
        raise AttributeError(f"method '{fn.__name__}' is already marked for retry")
    if hasattr(fn, RETRY_ON_EXCEPTION_ATTR):
        raise AttributeError(f"method '{fn.__name__}' is already marked for retry on exception")

    setattr(fn, RETRY_ON_RESULT_ATTR, True)
    return fn


class RetryStrategyMeta(type):
    """Metaclass for collecting retryable methods in classes.

    This metaclass automatically collects methods marked for retry from both the current class and its base classes.
    It prevents manual definition of specific retry attributes and organizes methods into categories based on their
    retry strategy: general retry, retry on exception, and retry on result.
    """

    def __new__(
        cls: type[RetryStrategyMeta],
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, any],
    ) -> RetryStrategyMeta:
        if RETRY_METHODS_ATTR in namespace:
            raise AttributeError(f"manual definition of the '{RETRY_METHODS_ATTR}' attribute is not allowed")
        if RETRY_ON_EXCEPTION_METHODS_ATTR in namespace:
            raise AttributeError(
                f"manual definition of the '{RETRY_ON_EXCEPTION_METHODS_ATTR}' attribute is not allowed"
            )
        if RETRY_ON_RESULT_METHODS_ATTR in namespace:
            raise AttributeError(f"manual definition of the '{RETRY_ON_RESULT_METHODS_ATTR}' attribute is not allowed")

        retry_methods: dict[str, Callable] = {}
        retry_on_exception_methods: dict[str, Callable] = {}
        retry_on_result_methods: dict[str, Callable] = {}

        # Collect retryable methods from base/parent classes.
        for base in bases:
            if methods := getattr(base, RETRY_METHODS_ATTR, None):
                retry_methods.update(methods)
            if methods := getattr(base, RETRY_ON_EXCEPTION_METHODS_ATTR, None):
                retry_on_exception_methods.update(methods)
            if methods := getattr(base, RETRY_ON_RESULT_METHODS_ATTR, None):
                retry_on_result_methods.update(methods)

        # Collect retryable methods from the current class.
        for attr, value in namespace.items():
            if not callable(value):
                continue

            if getattr(value, RETRY_ATTR, False):
                retry_methods[attr] = value
            if getattr(value, RETRY_ON_EXCEPTION_ATTR, False):
                retry_on_exception_methods[attr] = value
            if getattr(value, RETRY_ON_RESULT_ATTR, False):
                retry_on_result_methods[attr] = value

        namespace[RETRY_METHODS_ATTR] = retry_methods
        namespace[RETRY_ON_EXCEPTION_METHODS_ATTR] = retry_on_exception_methods
        namespace[RETRY_ON_RESULT_METHODS_ATTR] = retry_on_result_methods

        # Create the class using the updated namespace.
        return super().__new__(cls, name, bases, namespace)


class RetryStrategyBase(metaclass=RetryStrategyMeta):
    """Base class for defining retry strategies.

    This class uses the `RetryStrategyMeta` metaclass to automatically collect retryable methods and provides
    properties to manage retry behavior and configuration. It serves as a foundation for both synchronous and
    asynchronous retry strategies.
    """

    def __init__(self, *, attempts: int = 0, delay: int = 0) -> None:
        self.attempts = attempts
        self.delay = delay

    @property
    def _retry(self) -> retry_base:
        retry_methods = getattr(self, RETRY_METHODS_ATTR, {})
        retry_on_exception_methods = getattr(self, RETRY_ON_EXCEPTION_METHODS_ATTR, {})
        retry_on_result_methods = getattr(self, RETRY_ON_RESULT_METHODS_ATTR, {})

        retry = retry_never

        # Priority: retry_methods > retry_on_exception_methods > retry_on_result_methods.
        for method in retry_methods.values():
            retry = retry_any(retry, partial(method, self))
        for method in retry_on_exception_methods.values():
            retry = retry | retry_if_exception(partial(method, self))
        for method in retry_on_result_methods.values():
            retry = retry | retry_if_result(partial(method, self))

        return retry

    @property
    def _retrying_kwargs(self) -> dict[str, any]:
        return {
            "stop": stop_after_attempt(self.attempts),
            "wait": wait_fixed(self.delay),
            # By default, it retries on any exception.
            "retry": retry_if_exception_type() if self._retry is retry_never else self._retry,
            # Define the `before` method if you want to execute something before each retry.
            "before": getattr(self, "before", before_nothing),
            # Define the `after` method if you want to execute something after each retry.
            "after": getattr(self, "after", after_nothing),
            # Define the `error_callback` method if you want to execute something when a final `RetryError` occurs.
            "retry_error_callback": getattr(self, "error_callback", None),
        }

    def raise_retry_error(self, retry_state: RetryState) -> None:
        """Raise a `RetryError` based on the given retry state.

        This method is particularly useful for reraising errors within the `error_callback` method.
        It extracts the outcome from the provided retry state and raises a `RetryError`, ensuring that
        the original exception context is retained for improved traceability.
        """
        error = RetryError(retry_state.outcome)
        raise error from retry_state.outcome.exception()


WrappedFnR = TypeVar("WrappedFnR")


class RetryStrategy(RetryStrategyBase):
    """Synchronous retry strategy class.

    Provides a mechanism to retry synchronous functions based on the retry configuration.
    """

    @cached_property
    def retrying(self) -> Retrying:
        return Retrying(**self._retrying_kwargs)

    def retry(self, fn: Callable[..., WrappedFnR], *args: any, **kwargs: any) -> WrappedFnR:
        return self.retrying(fn, *args, **kwargs)


class AsyncRetryStrategy(RetryStrategyBase):
    """Asynchronous retry strategy class.

    Provides a mechanism to retry asynchronous functions based on the retry configuration.
    """

    @cached_property
    def retrying(self) -> AsyncRetrying:
        return AsyncRetrying(**self._retrying_kwargs)

    async def retry(self, fn: Callable[..., WrappedFnR], *args: any, **kwargs: any) -> WrappedFnR:
        return await self.retrying(fn, *args, **kwargs)


if __name__ == "__main__":

    class CustomRetryStrategy(RetryStrategy):
        @retry
        def retry_on_xxx(self, retry_state: RetryState) -> bool:
            print("retry_on_xxx")
            return False

        @retry_on_exception
        def retry_on_value_error(self, exception: BaseException) -> bool:
            print("retry_on_value_error")
            return isinstance(exception, ValueError)

        @retry_on_result
        def retry_on_number(self, result: any) -> bool:
            print("retry_on_number")
            return isinstance(result, int)

        @retry
        def retry_on_yyy(self, retry_state: RetryState) -> bool:
            print("retry_on_yyy")
            return False

        def before(self, retry_state: RetryState) -> None:
            print(self, "before")

        def after(self, retry_state: RetryState) -> None:
            print(self, "after")

        def error_callback(self, retry_state: RetryState) -> None:
            print(self, "error")
            self.raise_retry_error(retry_state)

    class CustomRetryStrategyChild(CustomRetryStrategy):
        @retry_on_exception(exc_types=TypeError)
        def retry_on_type_error(self, exception: BaseException) -> bool:
            print("retry_on_type_error")
            return True

    def fn() -> None:
        print("main start")
        raise TypeError("some type error")
        print("main end")

    retry_strategy = CustomRetryStrategyChild(attempts=3, delay=1)
    retry_strategy.retry(fn)
