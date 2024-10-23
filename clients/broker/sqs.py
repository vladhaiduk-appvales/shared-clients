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

    def string_attr(self, value: any) -> dict[str, any]:
        return {"DataType": "String", "StringValue": str(value)}

    def string_list_attr(self, values: list[any]) -> dict[str, any]:
        return {"DataType": "String", "StringListValues": [str(value) for value in values]}

    def binary_attr(self, value: bytes) -> dict[str, any]:
        return {"DataType": "Binary", "BinaryValue": value}

    def binary_list_attr(self, values: list[bytes]) -> dict[str, any]:
        return {"DataType": "Binary", "BinaryListValues": values}


# It's necessary to prevent conflicts with the inheritance of BrokerClient and the use of OptionalSingletonMeta.
class SQSClientMeta(OptionalSingletonMeta, ABCMeta):
    pass


class SQSClient(BrokerClient, metaclass=SQSClientMeta):
    def __init__(
        self, queue_url: str, region_name: str, *, log_attributes: bool = False, log_body: bool = False
    ) -> None:
        super().__init__(queue_url)

        self.region_name = region_name
        self.log_attributes = log_attributes
        self.log_body = log_body

        self._client = boto3.client(
            "sqs",
            region_name=self.region_name,
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
        except ClientError as error:
            error_code = error.response["Error"]["Code"]
            error_message = error.response["Error"]["Message"]
            broker_clients_logger.error(
                f"Failed to send SQS message due to ClientError: {error_code} - {error_message}",
                exc_info=True,
                extra={"error": {"code": error_code, "message": error_message}},
            )
            return None
        except BotoCoreError:
            broker_clients_logger.error("Failed to send SQS message due to BotoCoreError", exc_info=True)
            return None
        else:
            extra = {}

            if self.log_attributes:
                extra["attributes"] = message.metadata
            if self.log_body:
                extra["body"] = message.body

            broker_clients_logger.info("Sent SQS message successfully", extra=extra)
            return response


if __name__ == "__main__":
    client_1 = SQSClient("url", "region", singleton=True)
    client_2 = SQSClient(singleton=True)

    print(client_1 is client_2)  # False
    print(client_1.queue_url, client_2.queue_url)  # url url
