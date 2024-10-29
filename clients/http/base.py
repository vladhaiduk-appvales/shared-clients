from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import httpx

from clients.broker import AsyncBrokerClient, BrokerClient, BrokerMessageBuilder
from consts import UNSET, Unset, setattr_if_not_unset
from loggers import http_clients_logger
from retry import AsyncRetryStrategy, RetryState, RetryStrategy, retry_on_exception, retry_on_result

from .request import EnhancedRequest
from .response import EnhancedResponse

if TYPE_CHECKING:
    from types import TracebackType

    from .types_ import (
        CertType,
        ContentBodyType,
        CookiesType,
        DetailsType,
        HeadersType,
        JsonBodyType,
        MethodType,
        ParamsType,
        ProxyType,
        TimeoutType,
        UrlType,
    )


# TODO: Make an async version of it.
class HttpRetryStrategy(RetryStrategy):
    def __init__(
        self,
        *,
        attempts: int = 0,
        delay: int = 0,
        statuses_to_retry: set[Literal["info", "redirect", "client_error", "server_error"]] | None = None,
    ) -> None:
        super().__init__(attempts=attempts, delay=delay)
        self.statuses_to_retry = statuses_to_retry or set()

    @retry_on_exception(exc_types=(httpx.ConnectError, httpx.ConnectTimeout))
    def retry_on_connection_error(self, error: Exception) -> bool:
        http_clients_logger.info(
            f"Marking HTTP request for retry due to connection error: {type(error).__name__} - {error}"
        )
        return True

    @retry_on_result
    def retry_on_status(self, result: EnhancedResponse) -> bool:
        if result.is_success or not self.statuses_to_retry:
            return False

        if (
            ("info" in self.statuses_to_retry and result.is_info)
            or ("redirect" in self.statuses_to_retry and result.is_redirect)
            or ("client_error" in self.statuses_to_retry and result.is_client_error)
            or ("server_error" in self.statuses_to_retry and result.is_server_error)
        ):
            http_clients_logger.info(f"Marking HTTP request for retry due to status code: {result.status_code}")
            return True

        return False

    def before(self, retry_state: RetryState) -> None:
        request = retry_state.kwargs.get("request") or retry_state.args[0]
        details = retry_state.kwargs["details"]

        http_clients_logger.info(
            f"Retrying HTTP request [{details['request_label']}] ({retry_state.attempt_number}/{self.attempts}): "
            f"{request.method} {request.url}"
        )

    def error_callback(self, retry_state: RetryState) -> None:
        request = retry_state.kwargs.get("request") or retry_state.args[0]
        details = retry_state.kwargs["details"]

        http_clients_logger.info(
            f"All retry attempts ({retry_state.attempt_number}/{self.attempts}) failed for HTTP request "
            f"[{details['request_label']}]: {request.method} {request.url}"
        )

        self.raise_retry_error(retry_state)


@dataclass
class HttpRequestLogConfig:
    request_name: bool = True
    request_tag: bool = True
    request_method: bool = True
    request_url: bool = True
    request_headers: bool = False
    request_body: bool = False


@dataclass
class HttpResponseLogConfig:
    request_name: bool = True
    request_tag: bool = True
    request_method: bool = True
    request_url: bool = True

    response_status_code: bool = True
    response_headers: bool = False
    response_body: bool = False
    response_elapsed_time: bool = True


class BrokerHttpMessageBuilder(BrokerMessageBuilder):
    def filter(self, request: EnhancedRequest, response: EnhancedResponse, details: DetailsType) -> bool:
        return True

    @abstractmethod
    def build_metadata(
        self, request: EnhancedRequest, response: EnhancedResponse, details: DetailsType
    ) -> dict[str, any] | None:
        pass

    @abstractmethod
    def build_body(self, request: EnhancedRequest, response: EnhancedResponse, details: DetailsType) -> str:
        pass


class HttpClient:
    """A wrapper around the HTTPX Client, designed to streamline and extend its functionality to meet our needs.

    This client provides an intuitive and extended interface for executing synchronous HTTP requests while maintaining
    the core capabilities of the HTTPX Client. It is not a complete wrapper around HTTPX that would allow for replacing
    HTTPX with another library. Instead, it simply extends the HTTPX Client with the features we need.
    """

    base_url: UrlType = ""
    base_params: ParamsType | None = None
    base_headers: ParamsType | None = None
    cookies: CookiesType | None = None
    auth: httpx.Auth | None = None
    proxy: ProxyType | None = None
    cert: CertType | None = None
    timeout: TimeoutType | None = 5.0

    retry_strategy: RetryStrategy | None = None
    request_log_config: HttpRequestLogConfig = HttpRequestLogConfig()
    response_log_config: HttpResponseLogConfig = HttpResponseLogConfig()
    broker_client: BrokerClient | None = None
    broker_message_builder: BrokerHttpMessageBuilder | None = None

    _global_client: httpx.Client | None = None

    def __init__(
        self,
        *,
        base_url: UrlType | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        auth: httpx.Auth | None | Unset = UNSET,
        proxy: ProxyType | None | Unset = UNSET,
        cert: CertType | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        request_log_config: HttpRequestLogConfig | None | Unset = UNSET,
        response_log_config: HttpResponseLogConfig | Unset = UNSET,
        broker_client: BrokerClient | None | Unset = UNSET,
        broker_message_builder: BrokerHttpMessageBuilder | None | Unset = UNSET,
    ) -> None:
        # Instance-level attributes do not delete class-level attributes; they simply shadow them.
        setattr_if_not_unset(self, "base_url", base_url)
        setattr_if_not_unset(self, "base_params", base_params)
        setattr_if_not_unset(self, "base_headers", base_headers)
        setattr_if_not_unset(self, "cookies", cookies)
        setattr_if_not_unset(self, "auth", auth)
        setattr_if_not_unset(self, "proxy", proxy)
        setattr_if_not_unset(self, "cert", cert)
        setattr_if_not_unset(self, "timeout", timeout)

        setattr_if_not_unset(self, "retry_strategy", retry_strategy)
        setattr_if_not_unset(self, "request_log_config", request_log_config)
        setattr_if_not_unset(self, "response_log_config", response_log_config)
        setattr_if_not_unset(self, "broker_client", broker_client)
        setattr_if_not_unset(self, "broker_message_builder", broker_message_builder)

        self._local_client: httpx.Client | None = None

    @classmethod
    def configure(
        cls,
        *,
        base_url: UrlType | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        auth: httpx.Auth | None | Unset = UNSET,
        proxy: ProxyType | None | Unset = UNSET,
        cert: CertType | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        request_log_config: HttpRequestLogConfig | None | Unset = UNSET,
        response_log_config: HttpResponseLogConfig | Unset = UNSET,
        broker_client: BrokerClient | None | Unset = UNSET,
        broker_message_builder: BrokerHttpMessageBuilder | None | Unset = UNSET,
    ) -> None:
        setattr_if_not_unset(cls, "base_url", base_url)
        setattr_if_not_unset(cls, "base_params", base_params)
        setattr_if_not_unset(cls, "base_headers", base_headers)
        setattr_if_not_unset(cls, "cookies", cookies)
        setattr_if_not_unset(cls, "auth", auth)
        setattr_if_not_unset(cls, "proxy", proxy)
        setattr_if_not_unset(cls, "cert", cert)
        setattr_if_not_unset(cls, "timeout", timeout)

        setattr_if_not_unset(cls, "retry_strategy", retry_strategy)
        setattr_if_not_unset(cls, "request_log_config", request_log_config)
        setattr_if_not_unset(cls, "response_log_config", response_log_config)
        setattr_if_not_unset(cls, "broker_client", broker_client)
        setattr_if_not_unset(cls, "broker_message_builder", broker_message_builder)

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

    def request_log(self, request: EnhancedRequest, details: DetailsType) -> tuple[str, dict[str, any]]:
        extra = {"request": {}}

        if self.request_log_config.request_name:
            extra["request"]["name"] = details["request_name"]
        if self.request_log_config.request_tag:
            extra["request"]["tag"] = details["request_tag"]
        if self.request_log_config.request_method:
            extra["request"]["method"] = request.method
        if self.request_log_config.request_url:
            extra["request"]["url"] = request.url
        if self.request_log_config.request_headers:
            extra["request"]["headers"] = request.headers
        if self.request_log_config.request_body:
            extra["request"]["body"] = request.text

        if not extra["request"]:
            del extra["request"]

        return f"Sending HTTP request [{details['request_label']}]: {request.method} {request.url}", extra

    def response_log(self, response: EnhancedResponse, details: DetailsType) -> tuple[str, dict[str, any]]:
        extra = {"request": {}, "response": {}}

        if self.response_log_config.request_name:
            extra["request"]["name"] = details["request_name"]
        if self.response_log_config.request_tag:
            extra["request"]["tag"] = details["request_tag"]
        if self.response_log_config.request_method:
            extra["request"]["method"] = response.request.method
        if self.response_log_config.request_url:
            extra["request"]["url"] = response.request.url

        if self.response_log_config.response_status_code:
            extra["response"]["status_code"] = response.status_code
        if self.response_log_config.response_headers:
            extra["response"]["headers"] = response.headers
        if self.response_log_config.response_body:
            extra["response"]["body"] = response.text
        if self.response_log_config.response_elapsed_time:
            extra["response"]["elapsed_time"] = response.elapsed.total_seconds()

        if not extra["request"]:
            del extra["request"]
        if not extra["response"]:
            del extra["response"]

        return (
            f"HTTP response received [{details['request_label']}]: "
            f"{response.request.method} {response.request.url} -> {response.status_code}"
        ), extra

    def _send_request(
        self, request: EnhancedRequest, *, auth: httpx.Auth | None = None, details: DetailsType
    ) -> EnhancedResponse:
        request_log_message, request_log_extra = self.request_log(request, details)
        http_clients_logger.info(request_log_message, extra=request_log_extra)

        response = self._client.send(request.origin, auth=auth)
        enhanced_response = EnhancedResponse(response)

        response_log_message, response_log_extra = self.response_log(enhanced_response, details)
        http_clients_logger.info(response_log_message, extra=response_log_extra)

        return enhanced_response

    def request(
        self,
        method: MethodType,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        details = details or {}

        if "request_name" not in details:
            details["request_name"] = name
        if "request_tag" not in details:
            details["request_tag"] = tag
        if "request_label" not in details:
            prefix = name or "UNNAMED"
            details["request_label"] = f"{prefix}-{tag}" if tag else prefix

        request = self._client.build_request(
            method,
            url,
            params=params,
            headers=headers,
            content=content,
            json=json,
            timeout=timeout if timeout is not UNSET else self.timeout,
        )
        enhanced_request = EnhancedRequest(request)

        send_request_kwargs = {
            "request": enhanced_request,
            "auth": auth if auth is not UNSET else self.auth,
            "details": details,
        }

        retry_strategy = retry_strategy if retry_strategy is not UNSET else self.retry_strategy
        response = (
            retry_strategy.retry(self._send_request, **send_request_kwargs)
            if retry_strategy
            else self._send_request(**send_request_kwargs)
        )

        if self.broker_client and self.broker_message_builder:
            message = self.broker_message_builder.build(enhanced_request, response, details)
            if message:
                http_clients_logger.info(f"Sending HTTP request [{details['request_label']}] message to broker")
                self.broker_client.send_message(message=message)

        return response

    def get(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        return self.request(
            "GET",
            url,
            name=name,
            tag=tag,
            params=params,
            headers=headers,
            auth=auth,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )

    def post(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        return self.request(
            "POST",
            url,
            name=name,
            tag=tag,
            params=params,
            headers=headers,
            auth=auth,
            content=content,
            json=json,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )

    def put(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        return self.request(
            "PUT",
            url,
            name=name,
            tag=tag,
            params=params,
            headers=headers,
            auth=auth,
            content=content,
            json=json,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )

    def patch(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        return self.request(
            "PATCH",
            url,
            name=name,
            tag=tag,
            params=params,
            headers=headers,
            auth=auth,
            content=content,
            json=json,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )

    def delete(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        return self.request(
            "DELETE",
            url,
            name=name,
            tag=tag,
            params=params,
            headers=headers,
            auth=auth,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )


class AsyncHttpClient:
    """A wrapper around the HTTPX AsyncClient, designed to streamline and extend its functionality to meet our needs.

    This client provides an intuitive and extended interface for executing asynchronous HTTP requests while maintaining
    the core capabilities of the HTTPX AsyncClient. It is not a complete wrapper around HTTPX that would allow for
    replacing HTTPX with another library. Instead, it simply extends the HTTPX AsyncClient with the features we need.
    """

    base_url: UrlType = ""
    base_params: ParamsType | None = None
    base_headers: ParamsType | None = None
    cookies: CookiesType | None = None
    auth: httpx.Auth | None = None
    proxy: ProxyType | None = None
    cert: CertType | None = None
    timeout: TimeoutType | None = 5.0

    retry_strategy: AsyncRetryStrategy | None = None
    request_log_config: HttpRequestLogConfig = HttpRequestLogConfig()
    response_log_config: HttpResponseLogConfig = HttpResponseLogConfig()
    broker_client: AsyncBrokerClient | None = None
    broker_message_builder: BrokerHttpMessageBuilder | None = None

    _global_client: httpx.AsyncClient | None = None

    def __init__(
        self,
        *,
        base_url: UrlType | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        auth: httpx.Auth | None | Unset = UNSET,
        proxy: ProxyType | None | Unset = UNSET,
        cert: CertType | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: AsyncRetryStrategy | None | Unset = UNSET,
        request_log_config: HttpRequestLogConfig | None | Unset = UNSET,
        response_log_config: HttpResponseLogConfig | Unset = UNSET,
        broker_client: AsyncBrokerClient | None | Unset = UNSET,
        broker_message_builder: BrokerHttpMessageBuilder | None | Unset = UNSET,
    ) -> None:
        # Instance-level attributes do not delete class-level attributes; they simply shadow them.
        setattr_if_not_unset(self, "base_url", base_url)
        setattr_if_not_unset(self, "base_params", base_params)
        setattr_if_not_unset(self, "base_headers", base_headers)
        setattr_if_not_unset(self, "cookies", cookies)
        setattr_if_not_unset(self, "auth", auth)
        setattr_if_not_unset(self, "proxy", proxy)
        setattr_if_not_unset(self, "cert", cert)
        setattr_if_not_unset(self, "timeout", timeout)

        setattr_if_not_unset(self, "retry_strategy", retry_strategy)
        setattr_if_not_unset(self, "request_log_config", request_log_config)
        setattr_if_not_unset(self, "response_log_config", response_log_config)
        setattr_if_not_unset(self, "broker_client", broker_client)
        setattr_if_not_unset(self, "broker_message_builder", broker_message_builder)

        self._local_client: httpx.AsyncClient | None = None

    @classmethod
    def configure(
        cls,
        *,
        base_url: UrlType | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        auth: httpx.Auth | None | Unset = UNSET,
        proxy: ProxyType | None | Unset = UNSET,
        cert: CertType | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: AsyncRetryStrategy | None | Unset = UNSET,
        request_log_config: HttpRequestLogConfig | None | Unset = UNSET,
        response_log_config: HttpResponseLogConfig | Unset = UNSET,
        broker_client: AsyncBrokerClient | None | Unset = UNSET,
        broker_message_builder: BrokerHttpMessageBuilder | None | Unset = UNSET,
    ) -> None:
        setattr_if_not_unset(cls, "base_url", base_url)
        setattr_if_not_unset(cls, "base_params", base_params)
        setattr_if_not_unset(cls, "base_headers", base_headers)
        setattr_if_not_unset(cls, "cookies", cookies)
        setattr_if_not_unset(cls, "auth", auth)
        setattr_if_not_unset(cls, "proxy", proxy)
        setattr_if_not_unset(cls, "cert", cert)
        setattr_if_not_unset(cls, "timeout", timeout)

        setattr_if_not_unset(cls, "retry_strategy", retry_strategy)
        setattr_if_not_unset(cls, "request_log_config", request_log_config)
        setattr_if_not_unset(cls, "response_log_config", response_log_config)
        setattr_if_not_unset(cls, "broker_client", broker_client)
        setattr_if_not_unset(cls, "broker_message_builder", broker_message_builder)

    @classmethod
    def open_global(cls) -> None:
        if not cls._global_client:
            cls._global_client = httpx.AsyncClient(
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
    async def close_global(cls) -> None:
        if cls._global_client:
            await cls._global_client.aclose()

    def open(self) -> None:
        if not self._local_client:
            self._local_client = httpx.AsyncClient(
                base_url=self.base_url,
                params=self.base_params,
                headers=self.base_headers,
                cookies=self.cookies,
                auth=self.auth,
                proxy=self.proxy,
                cert=self.cert,
                timeout=self.timeout,
            )

    async def close(self) -> None:
        if self._local_client:
            await self._local_client.aclose()

    @property
    def _client(self) -> httpx.AsyncClient:
        if not self._local_client and not self._global_client:
            self.open()
        return self._local_client or self._global_client

    async def __aenter__(self) -> httpx.AsyncClient:
        self.open()
        await self._local_client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        await self._local_client.__aexit__(exc_type, exc_value, traceback)
        await self.close()

    def request_log(self, request: EnhancedRequest, details: DetailsType) -> tuple[str, dict[str, any]]:
        extra = {"request": {}}

        if self.request_log_config.request_name:
            extra["request"]["name"] = details["request_name"]
        if self.request_log_config.request_tag:
            extra["request"]["tag"] = details["request_tag"]
        if self.request_log_config.request_method:
            extra["request"]["method"] = request.method
        if self.request_log_config.request_url:
            extra["request"]["url"] = request.url
        if self.request_log_config.request_headers:
            extra["request"]["headers"] = request.headers
        if self.request_log_config.request_body:
            extra["request"]["body"] = request.text

        if not extra["request"]:
            del extra["request"]

        return f"Sending HTTP request [{details['request_label']}]: {request.method} {request.url}", extra

    def response_log(self, response: EnhancedResponse, details: DetailsType) -> tuple[str, dict[str, any]]:
        extra = {"request": {}, "response": {}}

        if self.response_log_config.request_name:
            extra["request"]["name"] = details["request_name"]
        if self.response_log_config.request_tag:
            extra["request"]["tag"] = details["request_tag"]
        if self.response_log_config.request_method:
            extra["request"]["method"] = response.request.method
        if self.response_log_config.request_url:
            extra["request"]["url"] = response.request.url

        if self.response_log_config.response_status_code:
            extra["response"]["status_code"] = response.status_code
        if self.response_log_config.response_headers:
            extra["response"]["headers"] = response.headers
        if self.response_log_config.response_body:
            extra["response"]["body"] = response.text
        if self.response_log_config.response_elapsed_time:
            extra["response"]["elapsed_time"] = response.elapsed.total_seconds()

        if not extra["request"]:
            del extra["request"]
        if not extra["response"]:
            del extra["response"]

        return (
            f"HTTP response received [{details['request_label']}]: "
            f"{response.request.method} {response.request.url} -> {response.status_code}"
        ), extra

    async def _send_request(
        self, request: EnhancedRequest, *, auth: httpx.Auth | None = None, details: DetailsType
    ) -> EnhancedResponse:
        request_log_message, request_log_extra = self.request_log(request, details)
        http_clients_logger.info(request_log_message, extra=request_log_extra)

        response = await self._client.send(request.origin, auth=auth)
        enhanced_response = EnhancedResponse(response)

        response_log_message, response_log_extra = self.response_log(enhanced_response, details)
        http_clients_logger.info(response_log_message, extra=response_log_extra)

        return enhanced_response

    async def request(
        self,
        method: MethodType,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: AsyncRetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        details = details or {}

        if "request_name" not in details:
            details["request_name"] = name
        if "request_tag" not in details:
            details["request_tag"] = tag
        if "request_label" not in details:
            prefix = name or "UNNAMED"
            details["request_label"] = f"{prefix}-{tag}" if tag else prefix

        request = self._client.build_request(
            method,
            url,
            params=params,
            headers=headers,
            content=content,
            json=json,
            timeout=timeout if timeout is not UNSET else self.timeout,
        )
        enhanced_request = EnhancedRequest(request)

        send_request_kwargs = {
            "request": enhanced_request,
            "auth": auth if auth is not UNSET else self.auth,
            "details": details,
        }

        retry_strategy = retry_strategy if retry_strategy is not UNSET else self.retry_strategy
        response = await (
            retry_strategy.retry(self._send_request, **send_request_kwargs)
            if retry_strategy
            else self._send_request(**send_request_kwargs)
        )

        if self.broker_client and self.broker_message_builder:
            message = self.broker_message_builder.build(enhanced_request, response, details)
            if message:
                http_clients_logger.info(f"Sending HTTP request [{details['request_label']}] message to broker")
                await self.broker_client.send_message(message=message)

        return response

    async def get(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: AsyncRetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        return await self.request(
            "GET",
            url,
            name=name,
            tag=tag,
            params=params,
            headers=headers,
            auth=auth,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )

    async def post(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: AsyncRetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        return await self.request(
            "POST",
            url,
            name=name,
            tag=tag,
            params=params,
            headers=headers,
            auth=auth,
            content=content,
            json=json,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )

    async def put(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: AsyncRetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        return await self.request(
            "PUT",
            url,
            name=name,
            tag=tag,
            params=params,
            headers=headers,
            auth=auth,
            content=content,
            json=json,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )

    async def patch(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: AsyncRetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        return await self.request(
            "PATCH",
            url,
            name=name,
            tag=tag,
            params=params,
            headers=headers,
            auth=auth,
            content=content,
            json=json,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )

    async def delete(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: AsyncRetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> EnhancedResponse:
        return await self.request(
            "DELETE",
            url,
            name=name,
            tag=tag,
            params=params,
            headers=headers,
            auth=auth,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )
