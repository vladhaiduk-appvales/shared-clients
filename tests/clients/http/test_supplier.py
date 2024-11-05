from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from ddtrace import tracer

from clients.broker.sqs import SQSMessageBuilder
from clients.http.base import AsyncHttpClient, BrokerHttpMessageBuilder, HttpClient, HttpClientBase
from clients.http.request import EnhancedRequest, Request
from clients.http.response import EnhancedResponse, Response
from clients.http.supplier import (
    AsyncSupplierClient,
    SQSSupplierMessageBuilder,
    SupplierClient,
    SupplierClientBase,
    SupplierRequestLogConfig,
    SupplierResponseLogConfig,
)
from utils.unset import UNSET

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

    from clients.http.types_ import DetailsType


@pytest.fixture
def sample_request() -> EnhancedRequest:
    return EnhancedRequest(Request("GET", "http://example.com"))


@pytest.fixture
def sample_response(sample_request: EnhancedRequest) -> EnhancedResponse:
    response = Response(200, request=sample_request.origin)
    response._elapsed = dt.timedelta(seconds=1)
    return EnhancedResponse(response)


@pytest.fixture
def sample_details() -> DetailsType:
    return {
        "request_name": "REQUEST",
        "request_tag": "TEST",
        "request_label": "REQUEST-TEST",
        "supplier_code": "SUPPLIER",
        "supplier_label": "SUPPLIER-LABEL",
    }


class TestSQSSupplierMessageBuilder:
    def test_inherits_broker_http_message_builder(self) -> None:
        assert issubclass(SQSSupplierMessageBuilder, BrokerHttpMessageBuilder)

    def test_inherits_sqs_message_builder(self) -> None:
        assert issubclass(SQSSupplierMessageBuilder, SQSMessageBuilder)

    @pytest.mark.parametrize(
        ("allowed_request_names", "disallowed_request_tags", "expected"),
        [
            (None, None, False),
            ({"REQUEST"}, None, True),
            ({"UNKNOWN"}, None, False),
            ({"REQUEST"}, {"TEST"}, False),
            ({"REQUEST"}, {"UNKNOWN"}, True),
        ],
    )
    def test_filter(
        self,
        allowed_request_names: set[str] | None,
        disallowed_request_tags: str[str] | None,
        expected: bool,
        sample_request: EnhancedRequest,
        sample_response: EnhancedResponse,
        sample_details: DetailsType,
    ) -> None:
        result = SQSSupplierMessageBuilder(
            allowed_request_names=allowed_request_names, disallowed_request_tags=disallowed_request_tags
        ).filter(sample_request, sample_response, sample_details)
        assert result is expected

    @pytest.mark.parametrize(
        ("details", "expected_static_attrs"),
        [
            (
                {
                    "request_label": "REQUEST-TEST",
                    "supplier_label": "SUPPLIER-LABEL",
                    "trace_id": "123",
                },
                {
                    "MessageType": {"DataType": "String", "StringValue": "REQUEST-TEST"},
                    "SupplierCode": {"DataType": "String", "StringValue": "SUPPLIER-LABEL"},
                    "TraceId": {"DataType": "String", "StringValue": "123"},
                },
            ),
            (
                {
                    "request_label": "REQUEST-TEST",
                    "supplier_label": "SUPPLIER-LABEL",
                    "trace_id": "123",
                    "tenant_id": "456",
                    "tenant_name": "TENANT",
                    "order_id": "789",
                    "booking_ref": "000",
                },
                {
                    "MessageType": {"DataType": "String", "StringValue": "REQUEST-TEST"},
                    "SupplierCode": {"DataType": "String", "StringValue": "SUPPLIER-LABEL"},
                    "TraceId": {"DataType": "String", "StringValue": "123"},
                    "TenantId": {"DataType": "String", "StringValue": "456"},
                    "TenantName": {"DataType": "String", "StringValue": "TENANT"},
                    "OrderId": {"DataType": "String", "StringValue": "789"},
                    "BookingRef": {"DataType": "String", "StringValue": "000"},
                },
            ),
        ],
    )
    def test_build_metadata(
        self,
        details: DetailsType,
        expected_static_attrs: dict[str, any],
        sample_request: EnhancedRequest,
        sample_response: EnhancedResponse,
    ) -> None:
        result = SQSSupplierMessageBuilder().build_metadata(sample_request, sample_response, details)

        for attr, value in expected_static_attrs.items():
            assert result[attr] == value

        assert result["TimeStamp"]["DataType"] == "String"

        try:
            dt.datetime.fromisoformat(result["TimeStamp"]["StringValue"])
        except Exception:
            pytest.fail("Invalid TimeStamp")

    def test_build_body(
        self, sample_request: EnhancedRequest, sample_response: EnhancedResponse, sample_details: DetailsType
    ) -> None:
        result = SQSSupplierMessageBuilder().build_body(sample_request, sample_response, sample_details)
        assert result == '{"request": "eJwDAAAAAAE=", "response": "eJwDAAAAAAE="}'


class SampleSupplierClient(SupplierClientBase):
    def __init__(
        self,
        request_log_config: SupplierRequestLogConfig | None = None,
        response_log_config: SupplierResponseLogConfig | None = None,
    ) -> None:
        self.request_log_config = request_log_config or SupplierRequestLogConfig()
        self.response_log_config = response_log_config or SupplierResponseLogConfig()


class TestSupplierClientBase:
    def test_inherits_http_client_base(self) -> None:
        assert issubclass(SupplierClientBase, HttpClientBase)

    @pytest.mark.parametrize(
        ("log_config", "expected_extra"),
        [
            (
                None,
                {
                    "request": {
                        "name": "REQUEST",
                        "tag": "TEST",
                        "method": "GET",
                        "url": "http://example.com",
                    },
                    "supplier_code": "SUPPLIER",
                },
            ),
            (
                SupplierRequestLogConfig(
                    request_name=True,
                    request_tag=True,
                    request_method=True,
                    request_url=True,
                    request_headers=True,
                    request_body=True,
                    supplier_code=True,
                ),
                {
                    "request": {
                        "name": "REQUEST",
                        "tag": "TEST",
                        "method": "GET",
                        "url": "http://example.com",
                        "headers": {"host": "example.com"},
                        "body": "",
                    },
                    "supplier_code": "SUPPLIER",
                },
            ),
            (
                SupplierRequestLogConfig(
                    request_name=False,
                    request_tag=False,
                    request_method=False,
                    request_url=False,
                    request_headers=False,
                    request_body=False,
                    supplier_code=False,
                ),
                {},
            ),
        ],
    )
    def test_request_log(
        self,
        log_config: SupplierRequestLogConfig | None,
        expected_extra: dict,
        sample_request: EnhancedRequest,
        sample_details: DetailsType,
    ) -> None:
        message, extra = SampleSupplierClient(request_log_config=log_config).request_log(sample_request, sample_details)

        assert "Sending HTTP request" in message
        assert "REQUEST-TEST" in message
        assert "SUPPLIER-LABEL" in message
        assert "GET http://example.com" in message

        assert extra == expected_extra

    @pytest.mark.parametrize(
        ("log_config", "expected_extra"),
        [
            (
                None,
                {
                    "request": {
                        "name": "REQUEST",
                        "tag": "TEST",
                        "method": "GET",
                        "url": "http://example.com",
                    },
                    "response": {
                        "status_code": 200,
                        "elapsed_time": 1.0,
                    },
                    "supplier_code": "SUPPLIER",
                },
            ),
            (
                SupplierResponseLogConfig(
                    request_name=True,
                    request_tag=True,
                    request_method=True,
                    request_url=True,
                    response_status_code=True,
                    response_headers=True,
                    response_body=True,
                    response_elapsed_time=True,
                    supplier_code=True,
                ),
                {
                    "request": {
                        "name": "REQUEST",
                        "tag": "TEST",
                        "method": "GET",
                        "url": "http://example.com",
                    },
                    "response": {
                        "status_code": 200,
                        "headers": {},
                        "body": "",
                        "elapsed_time": 1.0,
                    },
                    "supplier_code": "SUPPLIER",
                },
            ),
            (
                SupplierResponseLogConfig(
                    request_name=False,
                    request_tag=False,
                    request_method=False,
                    request_url=False,
                    response_status_code=False,
                    response_headers=False,
                    response_body=False,
                    response_elapsed_time=False,
                    supplier_code=False,
                ),
                {},
            ),
        ],
    )
    def test_response_log(
        self,
        log_config: SupplierResponseLogConfig | None,
        expected_extra: dict,
        sample_response: EnhancedResponse,
        sample_details: DetailsType,
    ) -> None:
        message, extra = SampleSupplierClient(response_log_config=log_config).response_log(
            sample_response, sample_details
        )

        assert "HTTP response received" in message
        assert "REQUEST-TEST" in message
        assert "SUPPLIER-LABEL" in message
        assert "GET http://example.com" in message
        assert "200" in message

        assert extra == expected_extra


class TestSupplierClient:
    @pytest.fixture(autouse=True)
    def reset_class_attributes(self) -> Generator[None, None, None]:
        yield

        SupplierClient.service_name = None
        SupplierClient.supplier_code = None

        SupplierClient.base_url = ""
        SupplierClient.base_params = None
        SupplierClient.base_headers = None
        SupplierClient.cookies = None
        SupplierClient.auth = None
        SupplierClient.proxy = None
        SupplierClient.cert = None
        SupplierClient.timeout = 5.0

        SupplierClient.retry_strategy = None
        SupplierClient.request_log_config = SupplierRequestLogConfig()
        SupplierClient.response_log_config = SupplierResponseLogConfig()
        SupplierClient.broker_client = None
        SupplierClient.broker_message_builder = None

        SupplierClient._global_client = None

    @pytest.fixture
    def mock_httpx_client(self, mocker: MockerFixture) -> MockerFixture:
        return mocker.patch("httpx.Client")

    def test_inherits_supplier_client_base(self) -> None:
        assert issubclass(SupplierClient, SupplierClientBase)

    def test_inherits_http_client(self) -> None:
        assert issubclass(SupplierClient, HttpClient)

    def test_configure_sets_only_specified_class_attributes(self) -> None:
        SupplierClient.configure(
            base_params={"class_param": "value"},
            base_headers={"class_header": "value"},
            cookies={"class_cookie": "value"},
        )

        assert SupplierClient.service_name is None
        assert SupplierClient.supplier_code is None

        assert SupplierClient.base_url == ""
        assert SupplierClient.base_params == {"class_param": "value"}
        assert SupplierClient.base_headers == {"class_header": "value"}
        assert SupplierClient.cookies == {"class_cookie": "value"}
        assert SupplierClient.auth is None
        assert SupplierClient.proxy is None
        assert SupplierClient.cert is None
        assert SupplierClient.timeout == 5.0

        assert SupplierClient.retry_strategy is None
        assert SupplierClient.request_log_config == SupplierRequestLogConfig()
        assert SupplierClient.response_log_config == SupplierResponseLogConfig()
        assert SupplierClient.broker_client is None
        assert SupplierClient.broker_message_builder is None

        assert SupplierClient._global_client is None

    def test_init_sets_only_specified_instance_attributes(self) -> None:
        client = SupplierClient(
            base_params={"instance_param": "value"},
            base_headers={"instance_header": "value"},
            cookies={"instance_cookie": "value"},
        )

        assert client.service_name is None
        assert client.supplier_code is None

        assert client.base_url == ""
        assert client.base_params == {"instance_param": "value"}
        assert client.base_headers == {"instance_header": "value"}
        assert client.cookies == {"instance_cookie": "value"}
        assert client.auth is None
        assert client.proxy is None
        assert client.cert is None
        assert client.timeout == 5.0

        assert client.retry_strategy is None
        assert client.request_log_config == SupplierRequestLogConfig()
        assert client.response_log_config == SupplierResponseLogConfig()
        assert client.broker_client is None
        assert client.broker_message_builder is None

        assert client._global_client is None
        assert client._local_client is None

    def test_request_sends_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_client: MagicMock
    ) -> None:
        spy_tracer_trace = mocker.spy(tracer, "trace")

        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with SupplierClient() as client:
            response = client.request("GET", "http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_tracer_trace.assert_called_once()

    def test_get_sends_get_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(SupplierClient, "request")

        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with SupplierClient() as client:
            response = client.get("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "GET",
            "http://example.com",
            name=None,
            tag=None,
            supplier_code=UNSET,
            params=None,
            headers=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )

    def test_post_sends_post_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(SupplierClient, "request")

        original_request = Request("POST", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with SupplierClient() as client:
            response = client.post("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "POST",
            "http://example.com",
            name=None,
            tag=None,
            supplier_code=UNSET,
            params=None,
            headers=None,
            content=None,
            json=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )

    def test_put_sends_put_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(SupplierClient, "request")

        original_request = Request("PUT", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with SupplierClient() as client:
            response = client.put("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "PUT",
            "http://example.com",
            name=None,
            tag=None,
            supplier_code=UNSET,
            params=None,
            headers=None,
            content=None,
            json=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )

    def test_patch_sends_patch_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(SupplierClient, "request")

        original_request = Request("PATCH", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with SupplierClient() as client:
            response = client.patch("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "PATCH",
            "http://example.com",
            name=None,
            tag=None,
            supplier_code=UNSET,
            params=None,
            headers=None,
            content=None,
            json=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )

    def test_delete_sends_delete_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(SupplierClient, "request")

        original_request = Request("DELETE", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with SupplierClient() as client:
            response = client.delete("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "DELETE",
            "http://example.com",
            name=None,
            tag=None,
            supplier_code=UNSET,
            params=None,
            headers=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )


class TestAsyncSupplierClient:
    @pytest.fixture(autouse=True)
    def reset_class_attributes(self) -> Generator[None, None, None]:
        yield

        AsyncSupplierClient.base_url = ""
        AsyncSupplierClient.base_params = None
        AsyncSupplierClient.base_headers = None
        AsyncSupplierClient.cookies = None
        AsyncSupplierClient.auth = None
        AsyncSupplierClient.proxy = None
        AsyncSupplierClient.cert = None
        AsyncSupplierClient.timeout = 5.0

        AsyncSupplierClient.retry_strategy = None
        AsyncSupplierClient.request_log_config = SupplierRequestLogConfig()
        AsyncSupplierClient.response_log_config = SupplierResponseLogConfig()
        AsyncSupplierClient.broker_client = None
        AsyncSupplierClient.broker_message_builder = None

        AsyncSupplierClient._global_client = None

    @pytest.fixture
    def mock_httpx_async_client(self, mocker: MockerFixture) -> MockerFixture:
        return mocker.patch("httpx.AsyncClient", return_value=AsyncMock(spec=httpx.AsyncClient))

    def test_inherits_supplier_client_base(self) -> None:
        assert issubclass(AsyncSupplierClient, SupplierClientBase)

    def test_inherits_async_http_client(self) -> None:
        assert issubclass(AsyncSupplierClient, AsyncHttpClient)

    def test_configure_sets_only_specified_class_attributes(self) -> None:
        AsyncSupplierClient.configure(
            base_params={"class_param": "value"},
            base_headers={"class_header": "value"},
            cookies={"class_cookie": "value"},
        )

        assert AsyncSupplierClient.service_name is None
        assert AsyncSupplierClient.supplier_code is None

        assert AsyncSupplierClient.base_url == ""
        assert AsyncSupplierClient.base_params == {"class_param": "value"}
        assert AsyncSupplierClient.base_headers == {"class_header": "value"}
        assert AsyncSupplierClient.cookies == {"class_cookie": "value"}
        assert AsyncSupplierClient.auth is None
        assert AsyncSupplierClient.proxy is None
        assert AsyncSupplierClient.cert is None
        assert AsyncSupplierClient.timeout == 5.0

        assert AsyncSupplierClient.retry_strategy is None
        assert AsyncSupplierClient.request_log_config == SupplierRequestLogConfig()
        assert AsyncSupplierClient.response_log_config == SupplierResponseLogConfig()
        assert AsyncSupplierClient.broker_client is None
        assert AsyncSupplierClient.broker_message_builder is None

        assert AsyncSupplierClient._global_client is None

    def test_init_sets_only_specified_instance_attributes(self) -> None:
        client = AsyncSupplierClient(
            base_params={"instance_param": "value"},
            base_headers={"instance_header": "value"},
            cookies={"instance_cookie": "value"},
        )

        assert client.service_name is None
        assert client.supplier_code is None

        assert client.base_url == ""
        assert client.base_params == {"instance_param": "value"}
        assert client.base_headers == {"instance_header": "value"}
        assert client.cookies == {"instance_cookie": "value"}
        assert client.auth is None
        assert client.proxy is None
        assert client.cert is None
        assert client.timeout == 5.0

        assert client.retry_strategy is None
        assert client.request_log_config == SupplierRequestLogConfig()
        assert client.response_log_config == SupplierResponseLogConfig()
        assert client.broker_client is None
        assert client.broker_message_builder is None

        assert client._global_client is None
        assert client._local_client is None

    @pytest.mark.asyncio
    async def test_request_sends_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_async_client: MagicMock
    ) -> None:
        spy_tracer_trace = mocker.spy(tracer, "trace")

        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncSupplierClient() as client:
            response = await client.request("GET", "http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_tracer_trace.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_sends_get_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_async_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(AsyncSupplierClient, "request")

        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncSupplierClient() as client:
            response = await client.get("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "GET",
            "http://example.com",
            name=None,
            tag=None,
            supplier_code=UNSET,
            params=None,
            headers=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )

    @pytest.mark.asyncio
    async def test_post_sends_post_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_async_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(AsyncSupplierClient, "request")

        original_request = Request("POST", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncSupplierClient() as client:
            response = await client.post("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "POST",
            "http://example.com",
            name=None,
            tag=None,
            supplier_code=UNSET,
            params=None,
            headers=None,
            content=None,
            json=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )

    @pytest.mark.asyncio
    async def test_put_sends_put_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_async_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(AsyncSupplierClient, "request")

        original_request = Request("PUT", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncSupplierClient() as client:
            response = await client.put("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "PUT",
            "http://example.com",
            name=None,
            tag=None,
            supplier_code=UNSET,
            params=None,
            headers=None,
            content=None,
            json=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )

    @pytest.mark.asyncio
    async def test_patch_sends_patch_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_async_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(AsyncSupplierClient, "request")

        original_request = Request("PATCH", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncSupplierClient() as client:
            response = await client.patch("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "PATCH",
            "http://example.com",
            name=None,
            tag=None,
            supplier_code=UNSET,
            params=None,
            headers=None,
            content=None,
            json=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )

    @pytest.mark.asyncio
    async def test_delete_sends_delete_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_async_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(AsyncSupplierClient, "request")

        original_request = Request("DELETE", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncSupplierClient() as client:
            response = await client.delete("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "DELETE",
            "http://example.com",
            name=None,
            tag=None,
            supplier_code=UNSET,
            params=None,
            headers=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )
