from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import pytest

from clients.broker.sqs import SQSMessageBuilder
from clients.http.base import BrokerHttpMessageBuilder, HttpClientBase
from clients.http.request import EnhancedRequest, Request
from clients.http.response import EnhancedResponse, Response
from clients.http.supplier import (
    SQSSupplierMessageBuilder,
    SupplierClientBase,
    SupplierRequestLogConfig,
    SupplierResponseLogConfig,
)

if TYPE_CHECKING:
    from clients.http.types_ import DetailsType


@pytest.fixture
def sample_request() -> EnhancedRequest:
    return EnhancedRequest(Request("GET", "http://example.com"))


@pytest.fixture
def sample_response(sample_request: EnhancedRequest) -> EnhancedResponse:
    response = Response(200, request=sample_request._request)
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
