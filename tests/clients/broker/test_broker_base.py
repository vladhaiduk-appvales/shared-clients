from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

import pytest

from clients.broker.base import AsyncBrokerClient, BrokerClient, BrokerClientBase, BrokerMessage, BrokerMessageBuilder

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class SampleBrokerMessageBuilder(BrokerMessageBuilder):
    def build_metadata(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        return {"key": "value"}

    def build_body(self, *args: Any, **kwargs: Any) -> str:
        return "body"


class TestBrokerMessageBuilder:
    def test_is_abstract(self) -> None:
        assert issubclass(BrokerMessageBuilder, ABC)

    def test_has_abstract_methods(self) -> None:
        assert len(BrokerMessageBuilder.__abstractmethods__) == 2
        assert "build_metadata" in BrokerMessageBuilder.__abstractmethods__
        assert "build_body" in BrokerMessageBuilder.__abstractmethods__

    @pytest.mark.parametrize(
        ("filter_result", "expected"),
        [
            (True, BrokerMessage(metadata={"key": "value"}, body="body")),
            (False, None),
        ],
    )
    def test_build(self, filter_result: bool, expected: BrokerMessage | None, mocker: MockerFixture) -> None:
        instance = SampleBrokerMessageBuilder()

        mock_filter = mocker.patch.object(instance, "filter")
        spy_build_metadata = mocker.spy(instance, "build_metadata")
        spy_build_body = mocker.spy(instance, "build_body")

        mock_filter.return_value = filter_result

        arg1 = "arg1"
        kwarg1 = "kwarg1"

        result = instance.build(arg1, kwarg1=kwarg1)

        assert result == expected

        mock_filter.assert_called_once_with(arg1, kwarg1=kwarg1)
        spy_build_metadata.assert_called_once_with(arg1, kwarg1=kwarg1)
        spy_build_body.assert_called_once_with(arg1, kwarg1=kwarg1)

    def test_filter_default_returns_true(self) -> None:
        instance = SampleBrokerMessageBuilder()
        assert instance.filter() is True


class TestBrokerClient:
    def test_is_abstract(self) -> None:
        assert issubclass(BrokerClient, ABC)

    def test_inherits_broker_client_base(self) -> None:
        assert issubclass(BrokerClient, ABC)

    def test_has_abstract_methods(self) -> None:
        assert len(BrokerClient.__abstractmethods__) == 3
        assert "connect" in BrokerClient.__abstractmethods__
        assert "disconnect" in BrokerClient.__abstractmethods__
        assert "send_message" in BrokerClient.__abstractmethods__


class TestAsyncBrokerClient:
    def test_is_abstract(self) -> None:
        assert issubclass(AsyncBrokerClient, ABC)

    def test_inherits_broker_client_base(self) -> None:
        assert issubclass(AsyncBrokerClient, BrokerClientBase)

    def test_has_abstract_methods(self) -> None:
        assert len(AsyncBrokerClient.__abstractmethods__) == 3
        assert "connect" in AsyncBrokerClient.__abstractmethods__
        assert "disconnect" in AsyncBrokerClient.__abstractmethods__
        assert "send_message" in AsyncBrokerClient.__abstractmethods__
