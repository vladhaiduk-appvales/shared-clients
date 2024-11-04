from __future__ import annotations

from abc import ABCMeta
from typing import Any

import aioboto3
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from loggers import broker_clients_logger
from patterns import OptionalSingletonMeta

from .base import AsyncBrokerClient, BrokerClient, BrokerMessage, BrokerMessageBuilder


class SQSMessageBuilder(BrokerMessageBuilder):
    """Abstract class for building SQS messages.

    This class extends the `BrokerMessageBuilder` to provide utility methods specifically for building SQS messages.
    It includes methods for creating message attributes with various data types, such as numbers, strings,
    and binary data.
    """

    def number_attr(self, value: int) -> dict[str, Any]:
        return {"DataType": "Number", "StringValue": str(value)}

    def string_attr(self, value: Any) -> dict[str, Any]:
        return {"DataType": "String", "StringValue": str(value)}

    def string_list_attr(self, values: list[Any]) -> dict[str, Any]:
        return {"DataType": "String", "StringListValues": [str(value) for value in values]}

    def binary_attr(self, value: bytes) -> dict[str, Any]:
        return {"DataType": "Binary", "BinaryValue": value}

    def binary_list_attr(self, values: list[bytes]) -> dict[str, Any]:
        return {"DataType": "Binary", "BinaryListValues": values}


class SQSClientBase:
    """Base class for SQS clients.

    This class describes common attributes and methods for SQS clients.
    It serves as a foundation for both synchronous and asynchronous SQS clients.
    """

    def __init__(self, *, log_attributes: bool = False, log_body: bool = False) -> None:
        self.log_attributes = log_attributes
        self.log_body = log_body

    def log_client_error(self, error: ClientError) -> None:
        error_code = error.response["Error"]["Code"]
        error_message = error.response["Error"]["Message"]
        broker_clients_logger.error(
            f"Failed to send SQS message due to ClientError: {error_code} - {error_message}",
            exc_info=error,
            extra={"error": {"code": error_code, "message": error_message}},
        )

    def log_boto_core_error(self, error: BotoCoreError) -> None:
        broker_clients_logger.error("Failed to send SQS message due to BotoCoreError", exc_info=error)

    def log_success(self, message: BrokerMessage) -> None:
        extra = {}

        if self.log_attributes:
            extra["attributes"] = message.metadata
        if self.log_body:
            extra["body"] = message.body

        broker_clients_logger.info("Sent SQS message successfully", extra=extra)


class SQSClientMeta(OptionalSingletonMeta, ABCMeta):
    """Meta class for SQS clients.

    This class combines `OptionalSingletonMeta` and `ABCMeta` to prevent conflicts
    with the inheritance of `BrokerClient` and the use of `OptionalSingletonMeta`.
    """


class SQSClient(SQSClientBase, BrokerClient, metaclass=SQSClientMeta):
    """Synchronous SQS client."""

    def __init__(
        self,
        queue_url: str,
        region_name: str,
        *,
        endpoint_url: str | None = None,
        log_attributes: bool = False,
        log_body: bool = False,
    ) -> None:
        BrokerClient.__init__(self, queue_url)
        SQSClientBase.__init__(self, log_attributes=log_attributes, log_body=log_body)

        self.region_name = region_name
        self.endpoint_url = endpoint_url
        self._client = None

    def connect(self) -> None:
        if self._client is None:
            self._client = boto3.client("sqs", region_name=self.region_name, endpoint_url=self.endpoint_url)

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()

    def send_message(self, message: BrokerMessage) -> Any:
        try:
            response = self._client.send_message(
                QueueUrl=self.queue_url,
                MessageAttributes=message.metadata,
                MessageBody=message.body,
            )
        except ClientError as error:
            self.log_client_error(error)
            return None
        except BotoCoreError as error:
            self.log_boto_core_error(error)
            return None
        else:
            self.log_success(message)
            return response


class AsyncSQSClient(SQSClientBase, AsyncBrokerClient, metaclass=SQSClientMeta):
    """Asynchronous SQS client."""

    def __init__(
        self,
        queue_url: str,
        region_name: str,
        *,
        endpoint_url: str | None = None,
        log_attributes: bool = False,
        log_body: bool = False,
    ) -> None:
        AsyncBrokerClient.__init__(self, queue_url)
        SQSClientBase.__init__(self, log_attributes=log_attributes, log_body=log_body)

        self.region_name = region_name
        self.endpoint_url = endpoint_url
        self._client = None

    async def connect(self) -> None:
        if self._client is None:
            session = aioboto3.Session()
            # Since aioboto3 enforces the use of the async context manager, we need to call `__aenter__`.
            self._client = await session.client(
                "sqs",
                region_name=self.region_name,
                endpoint_url=self.endpoint_url,
            ).__aenter__()

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)

    async def send_message(self, message: BrokerMessage) -> Any:
        try:
            response = await self._client.send_message(
                QueueUrl=self.queue_url,
                MessageAttributes=message.metadata,
                MessageBody=message.body,
            )
        except ClientError as error:
            self.log_client_error(error)
            return None
        except BotoCoreError as error:
            self.log_boto_core_error(error)
            return None
        else:
            self.log_success(message)
            return response
