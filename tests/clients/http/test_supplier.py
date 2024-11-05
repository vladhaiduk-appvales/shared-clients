from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import pytest

from clients.http.base import HttpClientBase
from clients.http.request import EnhancedRequest, Request
from clients.http.response import EnhancedResponse, Response
from clients.http.supplier import SupplierClientBase, SupplierRequestLogConfig, SupplierResponseLogConfig

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
