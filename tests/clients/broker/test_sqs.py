from __future__ import annotations

import logging
from abc import ABCMeta
from typing import TYPE_CHECKING, Any

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from clients.broker.base import AsyncBrokerClient, BrokerClient, BrokerMessage, BrokerMessageBuilder
from clients.broker.sqs import AsyncSQSClient, SQSClient, SQSClientBase, SQSClientMeta, SQSMessageBuilder
from loggers import broker_clients_logger
from patterns import OptionalSingletonMeta

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


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
    def test_log_client_error(self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture) -> None:
        spy_logger_error = mocker.spy(broker_clients_logger, "error")

        error_response = {
            "Error": {
                "Code": "NoSuchBucket",
                "Message": "The specified bucket does not exist",
                "BucketName": "sample-bucket",
            }
        }
        operation_name = "ListBuckets"
        client_error = ClientError(error_response, operation_name)

        with caplog.at_level(logging.ERROR):
            SQSClientBase().log_client_error(client_error)

        assert len(caplog.records) == 1
        log_record = caplog.records[0]

        assert "ClientError" in log_record.message
        assert error_response["Error"]["Code"] in log_record.message
        assert error_response["Error"]["Message"] in log_record.message

        spy_logger_error.assert_called_once_with(
            log_record.message,
            exc_info=client_error,
            extra={
                "error": {
                    "code": error_response["Error"]["Code"],
                    "message": error_response["Error"]["Message"],
                }
            },
        )

    def test_log_boto_core_error(self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture) -> None:
        spy_logger_error = mocker.spy(broker_clients_logger, "error")

        boto_core_error = BotoCoreError()

        with caplog.at_level(logging.ERROR):
            SQSClientBase().log_boto_core_error(boto_core_error)

        assert len(caplog.records) == 1
        log_record = caplog.records[0]

        assert "BotoCoreError" in log_record.message
        spy_logger_error.assert_called_once_with(log_record.message, exc_info=boto_core_error)

    def test_log_success_without_extra(self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture) -> None:
        spy_info = mocker.spy(broker_clients_logger, "info")

        message = BrokerMessage(metadata={"key": "value"}, body="body")

        with caplog.at_level(logging.INFO):
            SQSClientBase().log_success(message)

        assert len(caplog.records) == 1
        log_record = caplog.records[0]

        assert "success" in log_record.message
        spy_info.assert_called_once_with(caplog.records[0].message, extra={})

    def test_log_success_with_extra(self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture) -> None:
        spy_info = mocker.spy(broker_clients_logger, "info")

        message = BrokerMessage(metadata={"key": "value"}, body="body")

        with caplog.at_level(logging.INFO):
            SQSClientBase(log_attributes=True, log_body=True).log_success(message)

        assert len(caplog.records) == 1
        log_record = caplog.records[0]

        assert "success" in log_record.message
        spy_info.assert_called_once_with(
            caplog.records[0].message,
            extra={
                "attributes": message.metadata,
                "body": message.body,
            },
        )


class TestSQSClientMeta:
    def test_inherits_optional_singleton_meta(self) -> None:
        assert issubclass(SQSClientMeta, OptionalSingletonMeta)

    def test_inherits_abc_meta(self) -> None:
        assert issubclass(SQSClientMeta, ABCMeta)


class TestSQSClient:
    @pytest.fixture
    def sample_sqs_client(self) -> SQSClient:
        return SQSClient("queue_url", "region_name", endpoint_url="endpoint_url")

    @pytest.fixture
    def mock_boto3_client(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("boto3.client")

    def test_inherits_sqs_client_base(self) -> None:
        assert issubclass(SQSClient, SQSClientBase)

    def test_inherits_broker_client(self) -> None:
        assert issubclass(SQSClient, BrokerClient)

    def test_uses_sqs_client_meta_metaclass(self) -> None:
        assert isinstance(SQSClient, SQSClientMeta)

    def test_connect_initializes_sqs_client_on_first_call(
        self, sample_sqs_client: SQSClient, mock_boto3_client: MagicMock
    ) -> None:
        sample_sqs_client.connect()

        assert sample_sqs_client._client is not None
        mock_boto3_client.assert_called_once_with("sqs", region_name="region_name", endpoint_url="endpoint_url")

    def test_connect_does_not_reinitialize_sqs_client_on_second_call(
        self, sample_sqs_client: SQSClient, mock_boto3_client: MagicMock
    ) -> None:
        sample_sqs_client.connect()
        sample_sqs_client.connect()

        assert sample_sqs_client._client is not None
        mock_boto3_client.assert_called_once_with("sqs", region_name="region_name", endpoint_url="endpoint_url")

    def test_disconnect_closes_sqs_client_when_client_is_open(
        self, sample_sqs_client: SQSClient, mock_boto3_client: MagicMock
    ) -> None:
        sample_sqs_client.connect()
        sample_sqs_client.disconnect()

        mock_boto3_client.return_value.close.assert_called_once()

    def test_disconnect_does_not_close_sqs_client_when_client_is_not_open(
        self, sample_sqs_client: SQSClient, mock_boto3_client: MagicMock
    ) -> None:
        sample_sqs_client.disconnect()
        mock_boto3_client.return_value.close.assert_not_called()


class TestAsyncSQSClient:
    @pytest.fixture
    def sample_async_sqs_client(self) -> AsyncSQSClient:
        return AsyncSQSClient("queue_url", "region_name", endpoint_url="endpoint_url")

    @pytest.fixture
    def mock_aioboto3_session(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("aioboto3.Session")

    def test_inherits_sqs_client_base(self) -> None:
        assert issubclass(AsyncSQSClient, SQSClientBase)

    def test_inherits_async_broker_client(self) -> None:
        assert issubclass(AsyncSQSClient, AsyncBrokerClient)

    def test_uses_sqs_client_meta_metaclass(self) -> None:
        assert isinstance(AsyncSQSClient, SQSClientMeta)

    @pytest.mark.asyncio
    async def test_connect_initializes_async_sqs_client_on_first_call(
        self, sample_async_sqs_client: AsyncSQSClient, mock_aioboto3_session: MagicMock
    ) -> None:
        await sample_async_sqs_client.connect()

        assert sample_async_sqs_client._client is not None
        mock_aioboto3_session.return_value.client.assert_called_once_with(
            "sqs", region_name="region_name", endpoint_url="endpoint_url"
        )

    @pytest.mark.asyncio
    async def test_connect_does_not_reinitialize_async_sqs_client_on_second_call(
        self, sample_async_sqs_client: AsyncSQSClient, mock_aioboto3_session: MagicMock
    ) -> None:
        await sample_async_sqs_client.connect()
        await sample_async_sqs_client.connect()

        assert sample_async_sqs_client._client is not None
        mock_aioboto3_session.return_value.client.assert_called_once_with(
            "sqs", region_name="region_name", endpoint_url="endpoint_url"
        )

    @pytest.mark.asyncio
    async def test_disconnect_closes_async_sqs_client_when_client_is_open(
        self, sample_async_sqs_client: AsyncSQSClient, mock_aioboto3_session: MagicMock
    ) -> None:
        await sample_async_sqs_client.connect()
        await sample_async_sqs_client.disconnect()

        assert len(mock_aioboto3_session.return_value.client.return_value.mock_calls) == 2
        assert "__aexit__" in mock_aioboto3_session.return_value.client.return_value.mock_calls[1][0]

    @pytest.mark.asyncio
    async def test_disconnect_does_not_close_async_sqs_client_when_client_is_not_open(
        self, sample_async_sqs_client: AsyncSQSClient, mock_aioboto3_session: MagicMock
    ) -> None:
        await sample_async_sqs_client.disconnect()
        assert len(mock_aioboto3_session.return_value.client.return_value.mock_calls) == 0
