from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import httpx

from consts import UNSET, Unset

if TYPE_CHECKING:
    from types import TracebackType

    from .types_ import ContentBodyType, CookiesType, HeadersType, JsonBodyType, ParamsType


class SyncHttpClient:
    base_url: str | None = None
    base_params: ParamsType | None = None
    base_headers: ParamsType | None = None
    cookies: CookiesType | None = None
    timeout: float | None = 5.0

    _global_client: httpx.Client | None = None

    def __init__(
        self,
        *,
        base_url: str | None | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        timeout: float | None | Unset = UNSET,
    ) -> None:
        # Instance-level attributes do not delete class-level attributes; they simply shadow them.
        if base_url is not UNSET:
            self.base_url = base_url
        if base_params is not UNSET:
            self.base_params = base_params
        if base_headers is not UNSET:
            self.base_headers = base_headers
        if cookies is not UNSET:
            self.cookies = cookies
        if timeout is not UNSET:
            self.timeout = timeout

        self._local_client: httpx.Client | None = None

    @classmethod
    def configure(
        cls,
        *,
        base_url: str | None | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        timeout: float | None | Unset = UNSET,
    ) -> SyncHttpClient:
        if base_url is not UNSET:
            cls.base_url = base_url
        if base_params is not UNSET:
            cls.base_params = base_params
        if base_headers is not UNSET:
            cls.base_headers = base_headers
        if cookies is not UNSET:
            cls.cookies = cookies
        if timeout is not UNSET:
            cls.timeout = timeout

    @classmethod
    def open_global(cls) -> None:
        if not cls._global_client:
            cls._global_client = httpx.Client(
                base_url=cls.base_url,
                params=cls.base_params,
                headers=cls.base_headers,
                cookies=cls.cookies,
                timeout=cls.timeout,
            )

    @classmethod
    def close_global(cls) -> None:
        if cls._global_client:
            cls._global_client.close()

    def open(self) -> None:
        if not self._local_client:
            self._local_client = httpx.Client(
                base_url=self.base_url,
                params=self.base_params,
                headers=self.base_headers,
                cookies=self.cookies,
                timeout=self.timeout,
            )

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
        # Currently, cleint does not support form data and file uploads.
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: float | None | Unset = UNSET,
    ) -> httpx.Response:
        return self._client.request(
            method,
            url,
            params=params,
            headers=headers,
            content=content,
            json=json,
            timeout=timeout if timeout is not UNSET else self.timeout,
        )

    def get(
        self,
        url: str,
        *,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        timeout: float | None | Unset = UNSET,
    ) -> httpx.Response:
        return self.request("GET", url, params=params, headers=headers, timeout=timeout)

    def post(
        self,
        url: str,
        *,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: float | None | Unset = UNSET,
    ) -> httpx.Response:
        return self.request("POST", url, params=params, headers=headers, content=content, json=json, timeout=timeout)

    def put(
        self,
        url: str,
        *,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: float | None | Unset = UNSET,
    ) -> httpx.Response:
        return self.request("PUT", url, params=params, headers=headers, content=content, json=json, timeout=timeout)

    def patch(
        self,
        url: str,
        *,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: float | None | Unset = UNSET,
    ) -> httpx.Response:
        return self.request("PATCH", url, params=params, headers=headers, content=content, json=json, timeout=timeout)

    def delete(
        self,
        url: str,
        *,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        timeout: float | None | Unset = UNSET,
    ) -> httpx.Response:
        return self.request("DELETE", url, params=params, headers=headers, timeout=timeout)