from __future__ import annotations

import logging
from typing import Any

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from clients.broker.base import BrokerMessage, BrokerMessageBuilder
from clients.broker.sqs import SQSClientBase, SQSMessageBuilder


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


class TestSQSClientBase:
    def test_log_client_error(self, caplog: pytest.LogCaptureFixture) -> None:
        error_response = {
            "Error": {
                "Code": "NoSuchBucket",
                "Message": "The specified bucket does not exist",
                "BucketName": "sample-bucket",
            }
        }
        operation_name = "ListBuckets"

        with caplog.at_level(logging.ERROR):
            SQSClientBase().log_client_error(ClientError(error_response, operation_name))

        assert len(caplog.records) == 1
        assert "ClientError" in caplog.text
        assert error_response["Error"]["Code"] in caplog.text
        assert error_response["Error"]["Message"] in caplog.text

    def test_log_boto_core_error(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.ERROR):
            SQSClientBase().log_boto_core_error(BotoCoreError())

        assert len(caplog.records) == 1
        assert "BotoCoreError" in caplog.text

    def test_log_success(self, caplog: pytest.LogCaptureFixture) -> None:
        message = BrokerMessage(metadata={"key": "value"}, body="body")

        with caplog.at_level(logging.INFO):
            SQSClientBase().log_success(message)

        assert len(caplog.records) == 1
        assert "success" in caplog.text
