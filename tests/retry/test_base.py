from __future__ import annotations

from typing import Callable

import pytest

from retry.base import RetryStrategyMeta, retry, retry_on_exception, retry_on_result


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


class TestRetryStrategyMeta:
    @pytest.fixture
    def parent_retry_methods(self) -> dict[str, Callable]:
        return {
            "parent_retry_method": retry(lambda _self, _arg: True),
            "parent_retry_on_exception_method": retry_on_exception(lambda _self, _arg: True),
            "parent_retry_on_result_method": retry_on_result(lambda _self, _arg: True),
        }

    @pytest.fixture
    def parent_retry_strategy(self, parent_retry_methods: dict[str, Callable]) -> type:
        return RetryStrategyMeta("ParentRetryStrategy", (object,), parent_retry_methods)

    @pytest.fixture
    def retry_methods(self) -> dict[str, Callable]:
        return {
            "retry_method": retry(lambda _self, _arg: True),
            "retry_on_exception_method": retry_on_exception(lambda _self, _arg: True),
            "retry_on_result_method": retry_on_result(lambda _self, _arg: True),
        }

    @pytest.mark.parametrize(
        "methods_attr",
        [
            "__retry_methods__",
            "__retry_on_exception_methods__",
            "__retry_on_result_methods__",
        ],
    )
    def test_namespace_with_predefined_retry_methods_raises_attribute_error(self, methods_attr: str) -> None:
        with pytest.raises(AttributeError, match=methods_attr):
            RetryStrategyMeta("RetryStrategy", (object,), {methods_attr: {}})

    def test_namespace_without_retry_methods_returns_updated_class(self) -> None:
        cls = RetryStrategyMeta("RetryStrategy", (object,), {})

        assert cls.__retry_methods__ == {}
        assert cls.__retry_on_exception_methods__ == {}
        assert cls.__retry_on_result_methods__ == {}

    def test_parent_with_retry_methods_returns_updated_class(
        self, parent_retry_strategy: type, parent_retry_methods: dict[str, Callable]
    ) -> None:
        cls = RetryStrategyMeta("RetryStrategy", (parent_retry_strategy,), {})

        assert cls.__retry_methods__ == {"parent_retry_method": parent_retry_methods["parent_retry_method"]}
        assert cls.__retry_on_exception_methods__ == {
            "parent_retry_on_exception_method": parent_retry_methods["parent_retry_on_exception_method"]
        }
        assert cls.__retry_on_result_methods__ == {
            "parent_retry_on_result_method": parent_retry_methods["parent_retry_on_result_method"]
        }

    def test_namespace_with_retry_methods_returns_updated_class(self, retry_methods: dict[str, Callable]) -> None:
        cls = RetryStrategyMeta("RetryStrategy", (object,), retry_methods)

        assert cls.__retry_methods__ == {"retry_method": retry_methods["retry_method"]}
        assert cls.__retry_on_exception_methods__ == {
            "retry_on_exception_method": retry_methods["retry_on_exception_method"]
        }
        assert cls.__retry_on_result_methods__ == {"retry_on_result_method": retry_methods["retry_on_result_method"]}

    def test_parent_and_namespace_with_retry_methods_returns_updated_class(
        self, parent_retry_strategy: type, parent_retry_methods: dict[str, Callable], retry_methods: dict[str, Callable]
    ) -> None:
        cls = RetryStrategyMeta("RetryStrategy", (parent_retry_strategy,), retry_methods)

        assert cls.__retry_methods__ == {
            "parent_retry_method": parent_retry_methods["parent_retry_method"],
            "retry_method": retry_methods["retry_method"],
        }
        assert cls.__retry_on_exception_methods__ == {
            "parent_retry_on_exception_method": parent_retry_methods["parent_retry_on_exception_method"],
            "retry_on_exception_method": retry_methods["retry_on_exception_method"],
        }
        assert cls.__retry_on_result_methods__ == {
            "parent_retry_on_result_method": parent_retry_methods["parent_retry_on_result_method"],
            "retry_on_result_method": retry_methods["retry_on_result_method"],
        }
