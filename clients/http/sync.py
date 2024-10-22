from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from consts import UNSET, Unset
from loggers import http_clients_logger

if TYPE_CHECKING:
    from types import TracebackType

    from retry import RetryStrategy

    from .types_ import (
        CertType,
        ContentBodyType,
        CookiesType,
        HeadersType,
        JsonBodyType,
        MethodType,
        ParamsType,
        ProxyType,
        TimeoutType,
        UrlType,
    )


class SyncHttpClient:
    """A wrapper around the HTTPX Client, designed to streamline and extend its functionality to meet our needs.

    This client provides an intuitive and extended interface for executing synchronous HTTP requests while maintaining
    the core capabilities of the HTTPX Client. It is not a complete wrapper around HTTPX that would allow for replacing
    HTTPX with another library. Instead, it simply extends the HTTPX Client with the features we need.
    """

    base_url: UrlType | None = None
    base_params: ParamsType | None = None
    base_headers: ParamsType | None = None
    cookies: CookiesType | None = None
    auth: httpx.Auth | None = None
    proxy: ProxyType | None = None
    cert: CertType | None = None
    timeout: TimeoutType | None = 5.0
    retry_strategy: RetryStrategy | None = None

    _global_client: httpx.Client | None = None

    def __init__(
        self,
        *,
        base_url: UrlType | None | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        auth: httpx.Auth | None | Unset = UNSET,
        proxy: ProxyType | None | Unset = UNSET,
        cert: CertType | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
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
        if auth is not UNSET:
            self.auth = auth
        if proxy is not UNSET:
            self.proxy = proxy
        if cert is not UNSET:
            self.cert = cert
        if timeout is not UNSET:
            self.timeout = timeout
        if retry_strategy is not UNSET:
            self.retry_strategy = retry_strategy

        self._local_client: httpx.Client | None = None

    @classmethod
    def configure(
        cls,
        *,
        base_url: UrlType | None | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        auth: httpx.Auth | None | Unset = UNSET,
        proxy: ProxyType | None | Unset = UNSET,
        cert: CertType | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> SyncHttpClient:
        if base_url is not UNSET:
            cls.base_url = base_url
        if base_params is not UNSET:
            cls.base_params = base_params
        if base_headers is not UNSET:
            cls.base_headers = base_headers
        if cookies is not UNSET:
            cls.cookies = cookies
        if auth is not UNSET:
            cls.auth = auth
        if proxy is not UNSET:
            cls.proxy = proxy
        if cert is not UNSET:
            cls.cert = cert
        if timeout is not UNSET:
            cls.timeout = timeout
        if retry_strategy is not UNSET:
            cls.retry_strategy = retry_strategy

    @classmethod
    def open_global(cls) -> None:
        if not cls._global_client:
            cls._global_client = httpx.Client(
                base_url=cls.base_url,
                params=cls.base_params,
                headers=cls.base_headers,
                cookies=cls.cookies,
                auth=cls.auth,
                proxy=cls.proxy,
                cert=cls.cert,
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
                auth=self.auth,
                proxy=self.proxy,
                cert=self.cert,
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

    def request_log(self, *, request_name: str, request: httpx.Request) -> tuple[str, dict[str, any] | None]:
        return f"Sending HTTP request [{request_name}]: {request.method} {request.url}", {
            "request": {
                "name": request_name,
                "method": request.method,
                "url": request.url,
                "headers": request.headers,
                "body": request.content.decode(),
            },
        }

    def response_log(self, *, request_name: str, response: httpx.Response) -> tuple[str, dict[str, any] | None]:
        return (
            f"HTTP response received [{request_name}]: "
            f"{response.request.method} {response.request.url} -> {response.status_code}"
        ), {
            "request": {
                "name": request_name,
                "method": response.request.method,
                "url": response.request.url,
            },
            "response": {
                "status_code": response.status_code,
                "headers": response.headers,
                "body": response.text,
                "elapsed_time": response.elapsed.total_seconds(),
            },
        }

    def _send_request(
        self,
        method: MethodType,
        url: UrlType,
        *,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        # Currently, cleint does not support form data and file uploads.
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
    ) -> httpx.Response:
        request_name = name or "unnamed"
        request = self._client.build_request(
            method,
            url,
            params=params,
            headers=headers,
            content=content,
            json=json,
            timeout=timeout if timeout is not UNSET else self.timeout,
        )

        request_log_message, request_log_extra = self.request_log(request_name=request_name, request=request)
        http_clients_logger.info(request_log_message, extra=request_log_extra)

        response = self._client.send(request, auth=auth if auth is not UNSET else self.auth)

        response_log_message, response_log_extra = self.response_log(request_name=request_name, response=response)
        http_clients_logger.info(response_log_message, extra=response_log_extra)

        return response

    def request(
        self,
        method: MethodType,
        url: UrlType,
        *,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
        request_kwargs = {
            "method": method,
            "url": url,
            "name": name,
            "params": params,
            "headers": headers,
            "auth": auth,
            "content": content,
            "json": json,
            "timeout": timeout,
        }
        retry_strategy = retry_strategy if retry_strategy is not UNSET else self.retry_strategy
        return (
            retry_strategy.retry(self._send_request, **request_kwargs)
            if retry_strategy
            else self._send_request(**request_kwargs)
        )

    def get(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
        return self.request(
            "GET",
            url,
            name=name,
            params=params,
            headers=headers,
            auth=auth,
            timeout=timeout,
            retry_strategy=retry_strategy,
        )

    def post(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
        return self.request(
            "POST",
            url,
            name=name,
            params=params,
            headers=headers,
            auth=auth,
            content=content,
            json=json,
            timeout=timeout,
            retry_strategy=retry_strategy,
        )

    def put(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
        return self.request(
            "PUT",
            url,
            name=name,
            params=params,
            headers=headers,
            auth=auth,
            content=content,
            json=json,
            timeout=timeout,
            retry_strategy=retry_strategy,
        )

    def patch(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
        return self.request(
            "PATCH",
            url,
            name=name,
            params=params,
            headers=headers,
            auth=auth,
            content=content,
            json=json,
            timeout=timeout,
            retry_strategy=retry_strategy,
        )

    def delete(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
        return self.request(
            "DELETE",
            url,
            name=name,
            params=params,
            headers=headers,
            auth=auth,
            timeout=timeout,
            retry_strategy=retry_strategy,
        )
