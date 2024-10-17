from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Literal, Union

import httpx

if TYPE_CHECKING:
    from types import TracebackType

PrimitiveValue = Union[int, float, bool, str, None]

ParamsType = Mapping[str, Union[PrimitiveValue, Sequence[PrimitiveValue]]]
HeadersType = Mapping[str, str]

ContentBodyType = str
# Represents only variations of the JSON type that the client currently needs.
JsonBodyType = Union[Mapping[str, any], Sequence[dict[str, any]]]


class HttpClient:
    _global_client: httpx.Client | None = None

    def __init__(self) -> None:
        self._local_client: httpx.Client | None = None

    @classmethod
    def open_global(cls) -> None:
        if not cls._global_client:
            cls._global_client = httpx.Client()

    @classmethod
    def close_global(cls) -> None:
        if cls._global_client:
            cls._global_client.close()

    def open(self) -> None:
        if not self._local_client:
            self._local_client = httpx.Client()

    def close(self) -> None:
        if self._local_client:
            self._local_client.close()

    @property
    def _client(self) -> httpx.Client:
        if not self._local_client and not self._global_client:
            self.open()
        return self._local_client or self._global_client

    def __enter__(self) -> httpx.Client:
        self.open()
        self._local_client.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        self._local_client.__exit__(exc_type, exc_value, traceback)
        self.close()

    def request(
        self,
        # Currently, not all HTTP methods are supported by the client.
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
        url: str,
        *,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
    ) -> httpx.Response:
        return self._client.request(method, url, params=params, headers=headers, content=content, json=json)

    def get(
        self,
        url: str,
        *,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
    ) -> httpx.Response:
        return self.request("GET", url, params=params, headers=headers)

    def post(
        self,
        url: str,
        *,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
    ) -> httpx.Response:
        return self.request("POST", url, params=params, headers=headers, content=content, json=json)

    def put(
        self,
        url: str,
        *,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
    ) -> httpx.Response:
        return self.request("PUT", url, params=params, headers=headers, content=content, json=json)

    def patch(
        self,
        url: str,
        *,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
    ) -> httpx.Response:
        return self.request("PATCH", url, params=params, headers=headers, content=content, json=json)

    def delete(
        self,
        url: str,
        *,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
    ) -> httpx.Response:
        return self.request("DELETE", url, params=params, headers=headers)
