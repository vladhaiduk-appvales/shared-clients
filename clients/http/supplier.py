from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ddtrace import tracer

from clients.broker import SQSMessageBuilder
from utils.text import compress_and_encode, mask_card_number, mask_series_code
from utils.unset import UNSET, Unset, setattr_if_not_unset

from .base import AsyncHttpClient, BrokerHttpMessageBuilder, HttpClient, HttpRequestLogConfig, HttpResponseLogConfig

if TYPE_CHECKING:
    import httpx

    from clients.broker import AsyncBrokerClient, BrokerClient
    from retry import AsyncRetryStrategy, RetryStrategy

    from .request import EnhancedRequest
    from .response import EnhancedResponse
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


@dataclass
class SupplierRequestLogConfig(HttpRequestLogConfig):
    """Configuration for logging supplier-specific HTTP request details.

    This dataclass extends `HttpRequestLogConfig` to include additional logging
    configuration specific to supplier requests.
    """

    supplier_code: bool = True


@dataclass
class SupplierResponseLogConfig(HttpResponseLogConfig):
    """Configuration for logging supplier-specific HTTP response details.

    This dataclass extends `HttpResponseLogConfig` to include additional logging
    configuration specific to supplier responses.
    """

    supplier_code: bool = True


class SQSSupplierMessageBuilder(BrokerHttpMessageBuilder, SQSMessageBuilder):
    """A specific implementation of the `SQSMessageBuilder` for the raw-supplier-message-storage service.

    This class combines the functionalities of `BrokerHttpMessageBuilder` and `SQSMessageBuilder`
    to create and filter messages specifically for the raw-supplier-message-storage service.
    It allows filtering based on request names and tags and builds message metadata and body
    for storage in an SQS queue.
    """

    def __init__(
        self,
        *,
        allowed_request_names: set[str | None] | None = None,
        disallowed_request_tags: set[str | None] | None = None,
    ) -> None:
        self.allowed_request_names = allowed_request_names or set()
        self.disallowed_request_tags = disallowed_request_tags or set()

    def filter(self, request: EnhancedRequest, response: EnhancedResponse, details: DetailsType) -> bool:
        return (
            details["request_name"] in self.allowed_request_names
            and details["request_tag"] not in self.disallowed_request_tags
        )

    def build_metadata(
        self, request: EnhancedRequest, response: EnhancedResponse, details: DetailsType
    ) -> dict[str, any] | None:
        request_label = details["request_label"]
        supplier_label = details["supplier_label"]
        trace_id = details["trace_id"]
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        attributes = {
            "MessageType": self.string_attr(request_label),
            "SupplierCode": self.string_attr(supplier_label),
            "TraceId": self.string_attr(trace_id),
            "TimeStamp": self.string_attr(timestamp),
        }

        if tenant_id := details.get("tenant_id"):
            attributes["TenantId"] = self.string_attr(tenant_id)

        if tenant_name := details.get("tenant_name"):
            attributes["TenantName"] = self.string_attr(tenant_name)

        if order_id := details.get("order_id"):
            attributes["OrderId"] = self.string_attr(order_id)

        if booking_ref := details.get("booking_ref"):
            attributes["BookingRef"] = self.string_attr(booking_ref)

        return attributes

    def build_body(self, request: EnhancedRequest, response: EnhancedResponse, details: DetailsType) -> str:
        return json.dumps(
            {
                "request": compress_and_encode(mask_card_number(mask_series_code(request.text))),
                "response": compress_and_encode(response.content),
            }
        )


class SupplierClientBase:
    """Base class for HTTP supplier clients.

    This class describes common attributes and methods for HTTP supplier clients.
    It serves as a foundation for both synchronous and asynchronous HTTP supplier clients.
    """

    def request_log(self, request: EnhancedRequest, details: DetailsType) -> tuple[str, dict[str, any]]:
        message, extra = super().request_log(request, details)
        header, body = message.split(":", maxsplit=1)

        if self.request_log_config.supplier_code:
            extra["supplier_code"] = details["supplier_code"]

        return f"{header} to [{details['supplier_label']}] supplier:{body}", extra

    def response_log(self, response: EnhancedResponse, details: DetailsType) -> tuple[str, dict[str, any]]:
        message, extra = super().response_log(response, details)
        header, body = message.split(":", maxsplit=1)

        if self.request_log_config.supplier_code:
            extra["supplier_code"] = details["supplier_code"]

        return f"{header} from [{details['supplier_label']}] supplier:{body}", extra

    """A wrapper around the HTTPX `Client`, designed to streamline and extend its functionality to meet our needs.

    This client provides an intuitive and extended interface for executing synchronous HTTP requests while maintaining
    the core capabilities of the HTTPX `Client`. It is not a complete wrapper around HTTPX that would allow for
    replacing HTTPX with another library. Instead, it simply extends the HTTPX `Client` with the features we need.
    """


class SupplierClient(SupplierClientBase, HttpClient):
    """Synchronous HTTP client for supplier services.

    This class extends `HttpClient` to provide a synchronous HTTP client specifically
    configured for supplier services.
    """

    service_name: str | None = None
    supplier_code: str | None = None

    # We redefine all class-level attributes to stop them from taking values from the parent class.
    base_url: UrlType = ""
    base_params: ParamsType | None = None
    base_headers: ParamsType | None = None
    cookies: CookiesType | None = None
    auth: httpx.Auth | None = None
    proxy: ProxyType | None = None
    cert: CertType | None = None
    timeout: TimeoutType | None = 5.0

    retry_strategy: RetryStrategy | None = None
    request_log_config: SupplierRequestLogConfig = SupplierRequestLogConfig()
    response_log_config: SupplierResponseLogConfig = SupplierResponseLogConfig()
    broker_client: BrokerClient | None = None
    broker_message_builder: BrokerHttpMessageBuilder | None = None

    _global_client: httpx.Client | None = None

    def __init__(
        self,
        *,
        service_name: str | None | Unset = UNSET,
        supplier_code: str | None | Unset = UNSET,
        base_url: UrlType | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        auth: httpx.Auth | None | Unset = UNSET,
        proxy: ProxyType | None | Unset = UNSET,
        cert: CertType | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        request_log_config: SupplierRequestLogConfig | None | Unset = UNSET,
        response_log_config: SupplierResponseLogConfig | Unset = UNSET,
        broker_client: BrokerClient | None | Unset = UNSET,
        broker_message_builder: BrokerHttpMessageBuilder | None | Unset = UNSET,
    ) -> None:
        """Configure local settings for the HTTP client."""
        setattr_if_not_unset(self, "service_name", service_name)
        setattr_if_not_unset(self, "supplier_code", supplier_code)

        super().__init__(
            base_url=base_url,
            base_params=base_params,
            base_headers=base_headers,
            cookies=cookies,
            auth=auth,
            proxy=proxy,
            cert=cert,
            timeout=timeout,
            retry_strategy=retry_strategy,
            request_log_config=request_log_config,
            response_log_config=response_log_config,
            broker_client=broker_client,
            broker_message_builder=broker_message_builder,
        )

    @classmethod
    def configure(
        cls,
        *,
        service_name: str | None | Unset = UNSET,
        supplier_code: str | None | Unset = UNSET,
        base_url: UrlType | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        auth: httpx.Auth | None | Unset = UNSET,
        proxy: ProxyType | None | Unset = UNSET,
        cert: CertType | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        request_log_config: SupplierRequestLogConfig | None | Unset = UNSET,
        response_log_config: SupplierResponseLogConfig | Unset = UNSET,
        broker_client: BrokerClient | None | Unset = UNSET,
        broker_message_builder: BrokerHttpMessageBuilder | None | Unset = UNSET,
    ) -> None:
        """Configure global settings for the HTTP client."""
        setattr_if_not_unset(cls, "service_name", service_name)
        setattr_if_not_unset(cls, "supplier_code", supplier_code)

        return super().configure(
            base_url=base_url,
            base_params=base_params,
            base_headers=base_headers,
            cookies=cookies,
            auth=auth,
            proxy=proxy,
            cert=cert,
            timeout=timeout,
            retry_strategy=retry_strategy,
            request_log_config=request_log_config,
            response_log_config=response_log_config,
            broker_client=broker_client,
            broker_message_builder=broker_message_builder,
        )

    def request(
        self,
        method: MethodType,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        supplier_code: str | None | Unset = UNSET,
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
        supplier_code = supplier_code if supplier_code is not UNSET else self.supplier_code

        if "supplier_code" not in details:
            details["supplier_code"] = supplier_code
        if "supplier_label" not in details:
            details["supplier_label"] = supplier_code or "UNKNOWN"

        if "trace_id" not in details:
            with tracer.trace("SupplierClient.request", service=self.service_name) as span:
                details["trace_id"] = span.trace_id

        return super().request(
            method,
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

    def get(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        supplier_code: str | None | Unset = UNSET,
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
            supplier_code=supplier_code,
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
        supplier_code: str | None | Unset = UNSET,
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
            supplier_code=supplier_code,
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
        supplier_code: str | None | Unset = UNSET,
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
            supplier_code=supplier_code,
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
        supplier_code: str | None | Unset = UNSET,
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
            supplier_code=supplier_code,
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
        supplier_code: str | None | Unset = UNSET,
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
            supplier_code=supplier_code,
            params=params,
            headers=headers,
            auth=auth,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )


class AsyncSupplierClient(SupplierClientBase, AsyncHttpClient):
    """Asynchronous HTTP client for supplier services.

    This class extends `AsyncHttpClient` to provide a asynchronous HTTP client specifically
    configured for supplier services.
    """

    service_name: str | None = None
    supplier_code: str | None = None

    # We redefine all class-level attributes to stop them from taking values from the parent class.
    base_url: UrlType = ""
    base_params: ParamsType | None = None
    base_headers: ParamsType | None = None
    cookies: CookiesType | None = None
    auth: httpx.Auth | None = None
    proxy: ProxyType | None = None
    cert: CertType | None = None
    timeout: TimeoutType | None = 5.0

    retry_strategy: AsyncRetryStrategy | None = None
    request_log_config: SupplierRequestLogConfig = SupplierRequestLogConfig()
    response_log_config: SupplierResponseLogConfig = SupplierResponseLogConfig()
    broker_client: AsyncBrokerClient | None = None
    broker_message_builder: BrokerHttpMessageBuilder | None = None

    _global_client: httpx.AsyncClient | None = None

    def __init__(
        self,
        *,
        service_name: str | None | Unset = UNSET,
        supplier_code: str | None | Unset = UNSET,
        base_url: UrlType | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        auth: httpx.Auth | None | Unset = UNSET,
        proxy: ProxyType | None | Unset = UNSET,
        cert: CertType | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: AsyncRetryStrategy | None | Unset = UNSET,
        request_log_config: SupplierRequestLogConfig | None | Unset = UNSET,
        response_log_config: SupplierResponseLogConfig | Unset = UNSET,
        broker_client: AsyncBrokerClient | None | Unset = UNSET,
        broker_message_builder: BrokerHttpMessageBuilder | None | Unset = UNSET,
    ) -> None:
        """Configure local settings for the HTTP client."""
        setattr_if_not_unset(self, "service_name", service_name)
        setattr_if_not_unset(self, "supplier_code", supplier_code)

        super().__init__(
            base_url=base_url,
            base_params=base_params,
            base_headers=base_headers,
            cookies=cookies,
            auth=auth,
            proxy=proxy,
            cert=cert,
            timeout=timeout,
            retry_strategy=retry_strategy,
            request_log_config=request_log_config,
            response_log_config=response_log_config,
            broker_client=broker_client,
            broker_message_builder=broker_message_builder,
        )

    @classmethod
    def configure(
        cls,
        *,
        service_name: str | None | Unset = UNSET,
        supplier_code: str | None | Unset = UNSET,
        base_url: UrlType | Unset = UNSET,
        base_params: ParamsType | None | Unset = UNSET,
        base_headers: HeadersType | None | Unset = UNSET,
        cookies: CookiesType | None | Unset = UNSET,
        auth: httpx.Auth | None | Unset = UNSET,
        proxy: ProxyType | None | Unset = UNSET,
        cert: CertType | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: AsyncRetryStrategy | None | Unset = UNSET,
        request_log_config: SupplierRequestLogConfig | None | Unset = UNSET,
        response_log_config: SupplierResponseLogConfig | Unset = UNSET,
        broker_client: AsyncBrokerClient | None | Unset = UNSET,
        broker_message_builder: BrokerHttpMessageBuilder | None | Unset = UNSET,
    ) -> None:
        """Configure global settings for the HTTP client."""
        setattr_if_not_unset(cls, "service_name", service_name)
        setattr_if_not_unset(cls, "supplier_code", supplier_code)

        return super().configure(
            base_url=base_url,
            base_params=base_params,
            base_headers=base_headers,
            cookies=cookies,
            auth=auth,
            proxy=proxy,
            cert=cert,
            timeout=timeout,
            retry_strategy=retry_strategy,
            request_log_config=request_log_config,
            response_log_config=response_log_config,
            broker_client=broker_client,
            broker_message_builder=broker_message_builder,
        )

    async def request(
        self,
        method: MethodType,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        supplier_code: str | None | Unset = UNSET,
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
        supplier_code = supplier_code if supplier_code is not UNSET else self.supplier_code

        if "supplier_code" not in details:
            details["supplier_code"] = supplier_code
        if "supplier_label" not in details:
            details["supplier_label"] = supplier_code or "UNKNOWN"

        if "trace_id" not in details:
            with tracer.trace("SupplierClient.request", service=self.service_name) as span:
                details["trace_id"] = span.trace_id

        return await super().request(
            method,
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

    async def get(
        self,
        url: UrlType,
        *,
        name: str | None = None,
        tag: str | None = None,
        supplier_code: str | None | Unset = UNSET,
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
            supplier_code=supplier_code,
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
        supplier_code: str | None | Unset = UNSET,
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
            supplier_code=supplier_code,
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
        supplier_code: str | None | Unset = UNSET,
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
            supplier_code=supplier_code,
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
        supplier_code: str | None | Unset = UNSET,
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
            supplier_code=supplier_code,
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
        supplier_code: str | None | Unset = UNSET,
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
            supplier_code=supplier_code,
            params=params,
            headers=headers,
            auth=auth,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )
