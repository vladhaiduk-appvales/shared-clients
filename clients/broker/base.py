from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class BrokerMessage:
    metadata: dict[str, any] | None
    body: any | None


class BrokerMessageBuilder(ABC):
    def build(self, *args: any, **kwargs: any) -> BrokerMessage | None:
        metadata = self.build_metadata(*args, **kwargs)
        body = self.build_body(*args, **kwargs)
        return BrokerMessage(metadata=metadata, body=body) if metadata or body else None

    @abstractmethod
    def build_metadata(self, *args: any, **kwargs: any) -> dict[str, any] | None:
        pass

    @abstractmethod
    def build_body(self, *args: any, **kwargs: any) -> any | None:
        pass


class BrokerClient(ABC):
    def __init__(self, queue_url: str) -> None:
        self.queue_url = queue_url

    @abstractmethod
    def send_message(self, message: BrokerMessage) -> None:
        pass