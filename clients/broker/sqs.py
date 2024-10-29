from __future__ import annotations

from abc import ABCMeta

import aioboto3
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from loggers import broker_clients_logger
from patterns import OptionalSingletonMeta

from .base import AsyncBrokerClient, BrokerClient, BrokerMessage, BrokerMessageBuilder


class SQSMessageBuilder(BrokerMessageBuilder):
    def number_attr(self, value: int) -> dict[str, any]:
        return {"DataType": "Number", "StringValue": str(value)}

    def string_attr(self, value: any) -> dict[str, any]:
        return {"DataType": "String", "StringValue": str(value)}

    def string_list_attr(self, values: list[any]) -> dict[str, any]:
        return {"DataType": "String", "StringListValues": [str(value) for value in values]}

    def binary_attr(self, value: bytes) -> dict[str, any]:
        return {"DataType": "Binary", "BinaryValue": value}

    def binary_list_attr(self, values: list[bytes]) -> dict[str, any]:
        return {"DataType": "Binary", "BinaryListValues": values}


class SQSClientBase:
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


# It's necessary to prevent conflicts with the inheritance of BrokerClient and the use of OptionalSingletonMeta.
class SQSClientMeta(OptionalSingletonMeta, ABCMeta):
    pass


class SQSClient(SQSClientBase, BrokerClient, metaclass=SQSClientMeta):
    def __init__(
        self,
        queue_url: str,
        region_name: str,
        *,
        log_attributes: bool = False,
        log_body: bool = False,
    ) -> None:
        BrokerClient.__init__(self, queue_url)
        SQSClientBase.__init__(self, log_attributes=log_attributes, log_body=log_body)

        self.region_name = region_name
        self._client = None

    def connect(self) -> None:
        if not self._client:
            self._client = boto3.client(
                "sqs",
                region_name=self.region_name,
                # TODO: Remove this in prod.
                endpoint_url="http://localhost:4566",
            )

    def disconnect(self) -> None:
        if self._client:
            self._client.close()

    def send_message(self, message: BrokerMessage) -> any:
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
    def __init__(
        self, queue_url: str, region_name: str, *, log_attributes: bool = False, log_body: bool = False
    ) -> None:
        AsyncBrokerClient.__init__(self, queue_url)
        SQSClientBase.__init__(self, log_attributes=log_attributes, log_body=log_body)

        self.region_name = region_name
        self._client = None

    async def connect(self) -> None:
        if not self._client:
            session = aioboto3.Session()
            # Since aioboto3 enforces the use of the async context manager, we need to call `__aenter__`.
            self._client = await session.client(
                "sqs",
                region_name=self.region_name,
                # TODO: Remove this in prod.
                endpoint_url="http://localhost:4566",
            ).__aenter__()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.__aexit__(None, None, None)

    async def send_message(self, message: BrokerMessage) -> any:
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


if __name__ == "__main__":
    client_1 = SQSClient("url", "region", singleton=True)
    client_2 = SQSClient(singleton=True)

    print(client_1 is client_2)  # False
    print(client_1.queue_url, client_2.queue_url)  # url url
