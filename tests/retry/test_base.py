from __future__ import annotations

from typing import Callable

import pytest

from retry.base import retry, retry_on_exception, retry_on_result


class TestRetryDecorators:
    @pytest.fixture
    def sample_fn(self) -> Callable:
        return lambda _self, _arg: True

    def test_retry_adds_retry_flag(self, sample_fn: Callable) -> None:
        decorated_fn = retry(sample_fn)
        assert hasattr(decorated_fn, "__retry__")

    @pytest.mark.parametrize(
        ("retry_decorator", "error_keywords"),
        [
            (retry_on_exception, "retry on exception"),
            (retry_on_result, "retry on result"),
        ],
    )
    def test_retry_already_flagged_raises_attribute_error(
        self, retry_decorator: Callable, error_keywords: str, sample_fn: Callable
    ) -> None:
        with pytest.raises(AttributeError, match=error_keywords):
            retry(retry_decorator(sample_fn))

    def test_retry_on_exception_adds_retry_flag(self, sample_fn: Callable) -> None:
        decorated_fn = retry_on_exception(sample_fn)
        assert hasattr(decorated_fn, "__retry_on_exception__")

    @pytest.mark.parametrize(
        ("retry_decorator", "error_keywords"),
        [
            (retry, "retry"),
            (retry_on_result, "retry on result"),
        ],
    )
    def test_retry_on_exception_already_flagged_raises_attribute_error(
        self, retry_decorator: Callable, error_keywords: str, sample_fn: Callable
    ) -> None:
        with pytest.raises(AttributeError, match=error_keywords):
            retry_on_exception(retry_decorator(sample_fn))

    @pytest.mark.parametrize(
        ("exc_types", "input_exc", "expected"),
        [
            (ValueError, ValueError(), True),
            ((ValueError, TypeError), TypeError(), True),
            (ValueError, RuntimeError(), False),
            ((ValueError, TypeError), RuntimeError(), False),
        ],
    )
    def test_retry_on_exception_with_exc_types_ignores_other_exceptions(
        self,
        exc_types: type[BaseException] | tuple[type[BaseException], ...],
        input_exc: BaseException,
        expected: bool,
        sample_fn: Callable,
    ) -> None:
        decorated_fn = retry_on_exception(exc_types=exc_types)(sample_fn)
        assert decorated_fn(object(), input_exc) is expected

    def test_retry_on_result_adds_retry_flag(self, sample_fn: Callable) -> None:
        decorated_fn = retry_on_result(sample_fn)
        assert hasattr(decorated_fn, "__retry_on_result__")

    @pytest.mark.parametrize(
        ("retry_decorator", "error_keywords"),
        [
            (retry, "retry"),
            (retry_on_exception, "retry on exception"),
        ],
    )
    def test_retry_on_result_already_flagged_raises_attribute_error(
        self, retry_decorator: Callable, error_keywords: str, sample_fn: Callable
    ) -> None:
        with pytest.raises(AttributeError, match=error_keywords):
            retry_on_result(retry_decorator(sample_fn))
