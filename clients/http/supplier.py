from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from clients.broker import SQSMessageBuilder
from consts import UNSET, Unset, setattr_if_not_unset
from utils.text import compress_and_encode, mask_card_number, mask_series_code

from .base import BrokerHttpMessageBuilder, HttpRequestLogConfig, HttpResponseLogConfig, SyncHttpClient

if TYPE_CHECKING:
    import httpx

    from clients.broker import BrokerClient
    from retry import RetryStrategy

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
    supplier_code: bool = True


@dataclass
class SupplierResponseLogConfig(HttpResponseLogConfig):
    supplier_code: bool = True


class SQSSupplierMessageBuilder(BrokerHttpMessageBuilder, SQSMessageBuilder):
    """A specific implementation of the SQSMessageBuilder for the raw-supplier-message-storage service."""

    def build_metadata(
        self, _request: httpx.Request, _response: httpx.Response, details: DetailsType
    ) -> dict[str, any] | None:
        request_name = details["request_name"]
        supplier_code = details["supplier_code"]
        # TODO: I need to inject the trace_id into the details.
        trace_id = details.get("trace_id")
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        attributes = {
            "MessageType": self.string_attr(request_name),
            "SupplierCode": self.string_attr(supplier_code),
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

    def build_body(self, request: httpx.Request, response: httpx.Response, _details: DetailsType) -> str:
        request_text = request.content.decode()
        request_text = mask_card_number(mask_series_code(request_text))

        return json.dumps(
            {
                "request": compress_and_encode(request_text),
                "response": compress_and_encode(response.content),
            }
        )


class SyncSupplierClient(SyncHttpClient):
    supplier_code: str | None = None

    # We redefine all class-level attributes to stop them from taking values from the parent class.
    base_url: UrlType | None = None
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
        supplier_code: str | None | Unset = UNSET,
        base_url: UrlType | None | Unset = UNSET,
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
        supplier_code: str | None | Unset = UNSET,
        base_url: UrlType | None | Unset = UNSET,
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

    def request_log(self, request: httpx.Request, details: DetailsType) -> tuple[str, dict[str, any]]:
        message, extra = super().request_log(request=request, details=details)
        header, body = message.split(":", maxsplit=1)

        supplier_code = details["supplier_code"]

        if self.request_log_config.supplier_code:
            extra["supplier_code"] = supplier_code

        return f"{header} to [{supplier_code}] supplier:{body}", extra

    def response_log(self, response: httpx.Response, details: DetailsType) -> tuple[str, dict[str, any]]:
        message, extra = super().response_log(response=response, details=details)
        header, body = message.split(":", maxsplit=1)

        supplier_code = details["supplier_code"]

        if self.request_log_config.supplier_code:
            extra["supplier_code"] = supplier_code

        return f"{header} from [{supplier_code}] supplier:{body}", extra

    def request(
        self,
        method: MethodType,
        url: UrlType,
        *,
        name: str | None = None,
        supplier_code: str | None | Unset = UNSET,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> httpx.Response:
        details = details or {}

        if "supplier_code" not in details:
            details["supplier_code"] = supplier_code if supplier_code is not UNSET else self.supplier_code or "UNKNOWN"

        return super().request(
            method,
            url,
            name=name,
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
        supplier_code: str | None | Unset = UNSET,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> httpx.Response:
        return self.request(
            "GET",
            url,
            name=name,
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
        supplier_code: str | None | Unset = UNSET,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> httpx.Response:
        return self.request(
            "POST",
            url,
            name=name,
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
        supplier_code: str | None | Unset = UNSET,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> httpx.Response:
        return self.request(
            "PUT",
            url,
            name=name,
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
        supplier_code: str | None | Unset = UNSET,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> httpx.Response:
        return self.request(
            "PATCH",
            url,
            name=name,
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
        supplier_code: str | None | Unset = UNSET,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
        details: DetailsType | None = None,
    ) -> httpx.Response:
        return self.request(
            "DELETE",
            url,
            name=name,
            supplier_code=supplier_code,
            params=params,
            headers=headers,
            auth=auth,
            timeout=timeout,
            retry_strategy=retry_strategy,
            details=details,
        )
