from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import pytest

from retry.base import (
    AsyncRetrying,
    AsyncRetryStrategy,
    RetryError,
    Retrying,
    RetryState,
    RetryStrategy,
    RetryStrategyBase,
    RetryStrategyMeta,
    after_nothing,
    before_nothing,
    retry,
    retry_if_exception_type,
    retry_never,
    retry_on_exception,
    retry_on_result,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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
            (ValueError, ValueError("value error"), True),
            ((ValueError, TypeError), TypeError("type error"), True),
            (ValueError, RuntimeError("runtime error"), False),
            ((ValueError, TypeError), RuntimeError("runtime error"), False),
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

    def test_is_metaclass(self) -> None:
        assert issubclass(RetryStrategyMeta, type)

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


class RetryStrategyObject(RetryStrategyBase):
    @retry
    def retry_method(self, retry_state: RetryState) -> bool:
        return True

    @retry_on_exception
    def retry_on_exception_method(self, error: BaseException) -> bool:
        return True

    @retry_on_result
    def retry_on_result_method(self, result: Any) -> bool:
        return True

    def before(self, retry_state: RetryState) -> None:
        pass

    def after(self, retry_state: RetryState) -> None:
        pass

    def error_callback(self, retry_state: RetryState) -> None:
        pass


class TestRetryStrategyBase:
    @pytest.fixture
    def sample_retry_state(self) -> RetryState:
        return RetryState(None, None, (), {})

    def test_uses_retry_strategy_meta_metaclass(self) -> None:
        assert isinstance(RetryStrategyBase, RetryStrategyMeta)

    def test_retry_property_returns_default_strategy(self) -> None:
        base_instance = RetryStrategyBase()
        assert base_instance._retry == retry_never

    def test_retry_property_returns_custom_strategy(self) -> None:
        instance = RetryStrategyObject()
        assert instance._retry.retries.count != retry_never

    def test_retrying_kwargs_property_returns_default_kwargs(self) -> None:
        base_instance = RetryStrategyBase()

        assert base_instance._retrying_kwargs["stop"].max_attempt_number == 0
        assert base_instance._retrying_kwargs["wait"].wait_fixed == 0
        assert isinstance(base_instance._retrying_kwargs["retry"], retry_if_exception_type)
        assert base_instance._retrying_kwargs["before"] == before_nothing
        assert base_instance._retrying_kwargs["after"] == after_nothing
        assert base_instance._retrying_kwargs["retry_error_callback"] is None

    def test_retrying_kwargs_property_returns_custom_kwargs(self) -> None:
        instance = RetryStrategyObject(attempts=3, delay=1)

        assert instance._retrying_kwargs["stop"].max_attempt_number == 3
        assert instance._retrying_kwargs["wait"].wait_fixed == 1
        assert not isinstance(instance._retrying_kwargs["retry"], retry_if_exception_type)
        assert instance._retrying_kwargs["before"] == instance.before
        assert instance._retrying_kwargs["after"] == instance.after
        assert instance._retrying_kwargs["retry_error_callback"] == instance.error_callback

    def test_raise_retry_error_with_exception_raises_error_with_context(self, sample_retry_state: RetryState) -> None:
        base_instance = RetryStrategyBase()

        exception = ValueError("value error")
        sample_retry_state.set_exception((type(exception), exception, None))

        with pytest.raises(RetryError) as error:
            base_instance.raise_retry_error(sample_retry_state)

        assert error.value.__cause__ is exception
        assert error.value.last_attempt.exception() is exception

    def test_raise_retry_error_with_result_raises_error_without_context(self, sample_retry_state: RetryState) -> None:
        base_instance = RetryStrategyBase()

        result = object()
        sample_retry_state.set_result(result)

        with pytest.raises(RetryError) as error:
            base_instance.raise_retry_error(sample_retry_state)

        assert error.value.__cause__ is None
        assert error.value.last_attempt.exception() is None
        assert error.value.last_attempt.result() is result


class TestRetryStrategy:
    def test_inherits_retry_strategy_base(self) -> None:
        assert issubclass(RetryStrategy, RetryStrategyBase)

    def test_retrying_property_returns_retrying_instance(self) -> None:
        instance = RetryStrategy(attempts=3, delay=1)

        assert isinstance(instance.retrying, Retrying)
        assert instance.retrying.stop.max_attempt_number == 3
        assert instance.retrying.wait.wait_fixed == 1
        assert isinstance(instance.retrying.retry, retry_if_exception_type)
        assert instance.retrying.before == before_nothing
        assert instance.retrying.after == after_nothing
        assert instance.retrying.retry_error_callback is None

    def test_retrying_property_returns_cached_retrying_instance(self) -> None:
        instance = RetryStrategy(attempts=3, delay=1)
        assert instance.retrying is instance.retrying

    def test_retry_calls_retrying_instance(self, mocker: MockerFixture) -> None:
        instance = RetryStrategy(attempts=3, delay=1)
        spy_retrying = mocker.spy(instance, "retrying")

        def fn(a: int, b: int) -> int:
            return a + b

        arg1 = 1
        arg2 = 2

        result = instance.retry(fn, arg1, arg2)

        assert result == 3
        spy_retrying.assert_called_once_with(fn, arg1, arg2)


class TestAsyncRetryStrategy:
    def test_inherits_retry_strategy_base(self) -> None:
        assert issubclass(AsyncRetryStrategy, RetryStrategyBase)

    def test_retrying_property_returns_retrying_instance(self) -> None:
        instance = AsyncRetryStrategy(attempts=3, delay=1)

        assert isinstance(instance.retrying, AsyncRetrying)
        assert instance.retrying.stop.max_attempt_number == 3
        assert instance.retrying.wait.wait_fixed == 1
        assert isinstance(instance.retrying.retry, retry_if_exception_type)
        assert instance.retrying.before == before_nothing
        assert instance.retrying.after == after_nothing
        assert instance.retrying.retry_error_callback is None

    def test_retrying_property_returns_cached_retrying_instance(self) -> None:
        instance = AsyncRetryStrategy(attempts=3, delay=1)
        assert instance.retrying is instance.retrying

    @pytest.mark.asyncio
    async def test_retry_calls_retrying_instance(self, mocker: MockerFixture) -> None:
        instance = AsyncRetryStrategy(attempts=3, delay=1)
        spy_retrying = mocker.spy(instance, "retrying")

        async def fn(a: int, b: int) -> int:
            return a + b

        arg1 = 1
        arg2 = 2

        result = await instance.retry(fn, arg1, arg2)

        assert result == 3
        spy_retrying.assert_called_once_with(fn, arg1, arg2)
