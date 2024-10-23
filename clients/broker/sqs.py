from __future__ import annotations

from abc import ABCMeta

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from loggers import broker_clients_logger
from patterns import OptionalSingletonMeta

from .base import BrokerClient, BrokerMessage, BrokerMessageBuilder


class SQSMessageBuilder(BrokerMessageBuilder):
    def number_attr(self, value: int) -> dict[str, any]:
        return {"DataType": "Number", "StringValue": str(value)}

    def string_attr(self, value: str) -> dict[str, any]:
        return {"DataType": "String", "StringValue": value}

    def string_list_attr(self, values: list[str]) -> dict[str, any]:
        return {"DataType": "String", "StringListValues": values}

    def binary_attr(self, value: bytes) -> dict[str, any]:
        return {"DataType": "Binary", "BinaryValue": value}

    def binary_list_attr(self, values: list[bytes]) -> dict[str, any]:
        return {"DataType": "Binary", "BinaryListValues": values}


# It's necessary to prevent conflicts with the inheritance of BrokerClient and the use of OptionalSingletonMeta.
class SQSClientMeta(OptionalSingletonMeta, ABCMeta):
    pass


class SQSClient(BrokerClient, metaclass=SQSClientMeta):
    def __init__(self, queue_url: str, region_name: str) -> None:
        super().__init__(queue_url)
        self._client = boto3.client(
            "sqs",
            region_name=region_name,
            # TODO: Remove this in prod.
            endpoint_url="http://localhost:4566",
        )

    def send_message(self, message: BrokerMessage) -> any:
        try:
            response = self._client.send_message(
                QueueUrl=self.queue_url,
                MessageAttributes=message.metadata,
                MessageBody=message.body,
            )
        except (BotoCoreError, ClientError) as error:
            # TODO: Improve logs.
            broker_clients_logger.error("Failed to send SQS message", exc_info=error)
            return None
        else:
            broker_clients_logger.info("Successfully sent SQS message")
            return response


if __name__ == "__main__":
    client_1 = SQSClient("url", "region", singleton=True)
    client_2 = SQSClient(singleton=True)

    print(client_1 is client_2)  # False
    print(client_1.queue_url, client_2.queue_url)  # url url
