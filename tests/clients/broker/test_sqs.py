from __future__ import annotations

from typing import Any

import pytest

from clients.broker.base import BrokerMessageBuilder
from clients.broker.sqs import SQSMessageBuilder


class SampleSQSMessageBuilder(SQSMessageBuilder):
    def build_metadata(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        return {"key": "value"}

    def build_body(self, *args: Any, **kwargs: Any) -> str:
        return "body"


class TestSQSMessageBuilder:
    def test_inherits_broker_message_builder(self) -> None:
        assert issubclass(SQSMessageBuilder, BrokerMessageBuilder)

    def test_number_attr(self) -> None:
        instance = SampleSQSMessageBuilder()
        assert instance.number_attr(1) == {"DataType": "Number", "StringValue": "1"}

    @pytest.mark.parametrize(
        ("input_value", "expected_value"),
        [
            ("value", "value"),
            (1, "1"),
        ],
    )
    def test_string_attr(self, input_value: Any, expected_value: str) -> None:
        instance = SampleSQSMessageBuilder()
        assert instance.string_attr(input_value) == {"DataType": "String", "StringValue": expected_value}

    @pytest.mark.parametrize(
        ("input_values", "expected_values"),
        [
            (["value1", "value2"], ["value1", "value2"]),
            ([1, 2], ["1", "2"]),
        ],
    )
    def test_string_list_attr(self, input_values: list[Any], expected_values: list[str]) -> None:
        instance = SampleSQSMessageBuilder()
        assert instance.string_list_attr(input_values) == {"DataType": "String", "StringListValues": expected_values}

    def test_binary_attr(self) -> None:
        instance = SampleSQSMessageBuilder()
        assert instance.binary_attr(b"value") == {"DataType": "Binary", "BinaryValue": b"value"}

    def test_binary_list_attr(self) -> None:
        instance = SampleSQSMessageBuilder()
        assert instance.binary_list_attr([b"value1", b"value2"]) == {
            "DataType": "Binary",
            "BinaryListValues": [b"value1", b"value2"],
        }
