from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class BrokerMessage:
    metadata: dict[str, Any] | None
    body: str


class BrokerMessageBuilder(ABC):
    """Abstract base class for building broker messages.

    This class provides a blueprint for creating a `BrokerMessage` by defining a structure
    for metadata and message body construction. It ensures a consistent approach to building
    messages while allowing flexibility for specific implementations.
    """

    def build(self, *args: Any, **kwargs: Any) -> BrokerMessage | None:
        metadata = self.build_metadata(*args, **kwargs)
        body = self.build_body(*args, **kwargs)
        return BrokerMessage(metadata=metadata, body=body) if self.filter(*args, **kwargs) else None

    def filter(self, *args: Any, **kwargs: Any) -> bool:
        """Determine whether a `BrokerMessage` should be built.

        This method acts as a conditional filter that decides if the message building process should proceed.
        By default, it returns `True`, allowing all messages to be built. Subclasses can override this method
        to implement custom filtering logic based on the provided arguments.
        """
        return True

    @abstractmethod
    def build_metadata(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def build_body(self, *args: Any, **kwargs: Any) -> str:
        pass


class BrokerClientBase:
    """Base class for broker clients.

    This class describes common attributes and methods for broker clients.
    It serves as a foundation for both synchronous and asynchronous broker clients.
    """

    def __init__(self, queue_url: str) -> None:
        self.queue_url = queue_url


class BrokerClient(BrokerClientBase, ABC):
    """Abstract base class for synchronous broker clients."""

    @abstractmethod
    def connect(self) -> Any:
        pass

    @abstractmethod
    def disconnect(self) -> Any:
        pass

    @abstractmethod
    def send_message(self, message: BrokerMessage) -> Any:
        pass


class AsyncBrokerClient(BrokerClientBase, ABC):
    """Abstract base class for asynchronous broker clients."""

    @abstractmethod
    async def connect(self) -> Any:
        pass

    @abstractmethod
    async def disconnect(self) -> Any:
        pass

    @abstractmethod
    async def send_message(self, message: BrokerMessage) -> Any:
        pass
