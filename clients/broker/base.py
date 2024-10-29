from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class BrokerMessage:
    metadata: dict[str, any] | None
    body: str


class BrokerMessageBuilder(ABC):
    def build(self, *args: any, **kwargs: any) -> BrokerMessage | None:
        metadata = self.build_metadata(*args, **kwargs)
        body = self.build_body(*args, **kwargs)
        return BrokerMessage(metadata=metadata, body=body) if self.filter(*args, **kwargs) else None

    def filter(self, *args: any, **kwargs: any) -> bool:
        return True

    @abstractmethod
    def build_metadata(self, *args: any, **kwargs: any) -> dict[str, any] | None:
        pass

    @abstractmethod
    def build_body(self, *args: any, **kwargs: any) -> str:
        pass


class BaseBrokerClient:
    def __init__(self, queue_url: str) -> None:
        self.queue_url = queue_url


class BrokerClient(BaseBrokerClient, ABC):
    @abstractmethod
    def connect(self) -> any:
        pass

    @abstractmethod
    def disconnect(self) -> any:
        pass

    @abstractmethod
    def send_message(self, message: BrokerMessage) -> any:
        pass


class AsyncBrokerClient(BaseBrokerClient, ABC):
    @abstractmethod
    async def connect(self) -> any:
        pass

    @abstractmethod
    async def disconnect(self) -> any:
        pass

    @abstractmethod
    async def send_message(self, message: BrokerMessage) -> any:
        pass
