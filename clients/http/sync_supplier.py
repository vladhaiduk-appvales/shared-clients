from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from consts import UNSET, Unset

from .sync import HttpRequestLogConfig, HttpResponseLogConfig, SyncHttpClient

if TYPE_CHECKING:
    import httpx

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


@dataclass
class SupplierRequestLogConfig(HttpRequestLogConfig):
    supplier_code: bool = True


@dataclass
class SupplierResponseLogConfig(HttpResponseLogConfig):
    supplier_code: bool = True


class SyncSupplierClient(SyncHttpClient):
    supplier_code: str | None = None

    request_log_config: SupplierRequestLogConfig = SupplierRequestLogConfig()
    response_log_config: SupplierResponseLogConfig = SupplierResponseLogConfig()

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
    ) -> None:
        if supplier_code is not UNSET:
            self.supplier_code = supplier_code

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
    ) -> None:
        if supplier_code is not UNSET:
            cls.supplier_code = supplier_code

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
        )

    def request_log(self, *, request_name: str, request: httpx.Request) -> tuple[str, dict[str, any]]:
        message, extra = super().request_log(request_name=request_name, request=request)

        header, body = message.split(":", maxsplit=1)
        supplier_code = self.supplier_code or "unknown"

        if self.request_log_config.supplier_code:
            extra["supplier_code"] = supplier_code

        return f"{header} to [{supplier_code}] supplier:{body}", extra

    def response_log(self, *, request_name: str, response: httpx.Response) -> tuple[str, dict[str, any]]:
        message, extra = super().response_log(request_name=request_name, response=response)

        header, body = message.split(":", maxsplit=1)
        supplier_code = self.supplier_code or "unknown"

        if self.request_log_config.supplier_code:
            extra["supplier_code"] = supplier_code

        return f"{header} from [{supplier_code}] supplier:{body}", extra

    def request(
        self,
        method: MethodType,
        url: UrlType,
        *,
        supplier_code: str | None | Unset = UNSET,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
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
        )

    def get(
        self,
        url: UrlType,
        *,
        supplier_code: str | None | Unset = UNSET,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
        return super().get(
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
        supplier_code: str | None | Unset = UNSET,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
        return super().post(
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
        supplier_code: str | None | Unset = UNSET,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
        return super().put(
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
        supplier_code: str | None | Unset = UNSET,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        content: ContentBodyType | None = None,
        json: JsonBodyType | None = None,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
        return super().patch(
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
        supplier_code: str | None | Unset = UNSET,
        name: str | None = None,
        params: ParamsType | None = None,
        headers: HeadersType | None = None,
        auth: httpx.Auth | None | Unset = UNSET,
        timeout: TimeoutType | None | Unset = UNSET,
        retry_strategy: RetryStrategy | None | Unset = UNSET,
    ) -> httpx.Response:
        return super().delete(
            url,
            name=name,
            params=params,
            headers=headers,
            auth=auth,
            timeout=timeout,
            retry_strategy=retry_strategy,
        )
