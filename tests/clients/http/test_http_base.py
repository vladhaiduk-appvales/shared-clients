from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from clients.broker.base import BrokerMessageBuilder
from clients.http.base import (
    AsyncHttpClient,
    AsyncHttpRetryStrategy,
    BrokerHttpMessageBuilder,
    HttpClient,
    HttpClientBase,
    HttpRequestLogConfig,
    HttpResponseLogConfig,
    HttpRetryStrategy,
)
from clients.http.request import EnhancedRequest, Request
from clients.http.response import EnhancedResponse, Response
from retry.base import AsyncRetryStrategy, RetryError, RetryState, RetryStrategy

if TYPE_CHECKING:
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
    }


class TestHttpRetryStrategy:
    @pytest.fixture
    def sample_retry_state(self, sample_request: EnhancedRequest, sample_details: DetailsType) -> RetryState:
        return RetryState(None, None, (sample_request,), {"details": sample_details})

    def test_inherits_retry_strategy(self) -> None:
        assert issubclass(HttpRetryStrategy, RetryStrategy)

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (httpx.ConnectError("connection error"), True),
            (httpx.ConnectTimeout("connection timeout"), True),
            (httpx.RequestError("request error"), False),
        ],
    )
    def test_retry_on_connection_error(
        self, error: Exception, expected: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO):
            result = HttpRetryStrategy().retry_on_connection_error(error)

        assert result is expected
        if expected:
            assert "connection error" in caplog.text

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (httpx.TimeoutException("timeout error"), True),
            (httpx.ConnectTimeout("connection timeout"), True),
            (httpx.ReadTimeout("read timeout"), True),
            (httpx.WriteTimeout("write timeout"), True),
            (httpx.PoolTimeout("pool timeout"), True),
            (httpx.RequestError("request error"), False),
        ],
    )
    def test_retry_on_timeout_error(self, error: Exception, expected: bool, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            result = HttpRetryStrategy(on_timeouts=True).retry_on_timeout_error(error)

        assert result is expected
        if expected:
            assert "timeout error" in caplog.text

        assert HttpRetryStrategy(on_timeouts=False).retry_on_timeout_error(error) is False

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (httpx.NetworkError("network error"), True),
            (httpx.ConnectError("connection error"), True),
            (httpx.ReadError("read error"), True),
            (httpx.WriteError("write error"), True),
            (httpx.CloseError("close error"), True),
            (httpx.RequestError("request error"), False),
        ],
    )
    def test_retry_on_network_error(self, error: Exception, expected: bool, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            result = HttpRetryStrategy(on_network_errors=True).retry_on_network_error(error)

        assert result is expected
        if expected:
            assert "network error" in caplog.text

        assert HttpRetryStrategy(on_network_errors=False).retry_on_network_error(error) is False

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (httpx.ProtocolError("protocol error"), True),
            (httpx.LocalProtocolError("local protocol error"), True),
            (httpx.RemoteProtocolError("remote protocol error"), True),
            (httpx.RequestError("request error"), False),
        ],
    )
    def test_retry_on_protocol_error(self, error: Exception, expected: bool, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            result = HttpRetryStrategy(on_protocol_errors=True).retry_on_protocol_error(error)

        assert result is expected
        if expected:
            assert "protocol error" in caplog.text

        assert HttpRetryStrategy(on_protocol_errors=False).retry_on_protocol_error(error) is False

    @pytest.mark.parametrize(
        ("status_group", "status_code", "expected"),
        [
            ("info", 100, True),
            ("info", 200, False),
            ("info", 300, False),
            ("redirect", 300, True),
            ("redirect", 200, False),
            ("redirect", 400, False),
            ("client_error", 400, True),
            ("client_error", 200, False),
            ("client_error", 500, False),
            ("server_error", 500, True),
            ("server_error", 200, False),
            ("server_error", 100, False),
        ],
    )
    def test_retry_on_status(
        self, status_group: str, status_code: int, expected: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO):
            result = HttpRetryStrategy(on_statuses={status_group}).retry_on_status(
                EnhancedResponse(Response(status_code=status_code))
            )

        assert result is expected
        if expected:
            assert "status code" in caplog.text
            assert str(status_code) in caplog.text

    def test_before_logs_retry_attempt(self, caplog: pytest.LogCaptureFixture, sample_retry_state: RetryState) -> None:
        with caplog.at_level(logging.INFO):
            HttpRetryStrategy(attempts=3).before(sample_retry_state)

        assert "Retrying HTTP request" in caplog.text
        assert "REQUEST-TEST" in caplog.text
        assert "1/3" in caplog.text
        assert "GET http://example.com" in caplog.text

    def test_error_callback_logs_failure(
        self, caplog: pytest.LogCaptureFixture, sample_retry_state: RetryState
    ) -> None:
        with pytest.raises(RetryError), caplog.at_level(logging.ERROR):
            HttpRetryStrategy(attempts=3).error_callback(sample_retry_state)

        assert "All retry attempts" in caplog.text
        assert "1/3" in caplog.text
        assert "failed for HTTP request" in caplog.text
        assert "REQUEST-TEST" in caplog.text
        assert "GET http://example.com" in caplog.text


class TestAsyncHttpRetryStrategy:
    @pytest.fixture
    def sample_retry_state(self) -> RetryState:
        return RetryState(
            None,
            None,
            (EnhancedRequest(Request("GET", "http://example.com")),),
            {"details": {"request_label": "REQUEST-TEST"}},
        )

    def test_inherits_async_retry_strategy(self) -> None:
        assert issubclass(AsyncHttpRetryStrategy, AsyncRetryStrategy)

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (httpx.ConnectError("connection error"), True),
            (httpx.ConnectTimeout("connection timeout"), True),
            (httpx.RequestError("request error"), False),
        ],
    )
    def test_retry_on_connection_error(
        self, error: Exception, expected: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO):
            result = AsyncHttpRetryStrategy().retry_on_connection_error(error)

        assert result is expected
        if expected:
            assert "connection error" in caplog.text

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (httpx.TimeoutException("timeout error"), True),
            (httpx.ConnectTimeout("connection timeout"), True),
            (httpx.ReadTimeout("read timeout"), True),
            (httpx.WriteTimeout("write timeout"), True),
            (httpx.PoolTimeout("pool timeout"), True),
            (httpx.RequestError("request error"), False),
        ],
    )
    def test_retry_on_timeout_error(self, error: Exception, expected: bool, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            result = AsyncHttpRetryStrategy(on_timeouts=True).retry_on_timeout_error(error)

        assert result is expected
        if expected:
            assert "timeout error" in caplog.text

        assert AsyncHttpRetryStrategy(on_timeouts=False).retry_on_timeout_error(error) is False

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (httpx.NetworkError("network error"), True),
            (httpx.ConnectError("connection error"), True),
            (httpx.ReadError("read error"), True),
            (httpx.WriteError("write error"), True),
            (httpx.CloseError("close error"), True),
            (httpx.RequestError("request error"), False),
        ],
    )
    def test_retry_on_network_error(self, error: Exception, expected: bool, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            result = AsyncHttpRetryStrategy(on_network_errors=True).retry_on_network_error(error)

        assert result is expected
        if expected:
            assert "network error" in caplog.text

        assert AsyncHttpRetryStrategy(on_network_errors=False).retry_on_network_error(error) is False

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (httpx.ProtocolError("protocol error"), True),
            (httpx.LocalProtocolError("local protocol error"), True),
            (httpx.RemoteProtocolError("remote protocol error"), True),
            (httpx.RequestError("request error"), False),
        ],
    )
    def test_retry_on_protocol_error(self, error: Exception, expected: bool, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            result = AsyncHttpRetryStrategy(on_protocol_errors=True).retry_on_protocol_error(error)

        assert result is expected
        if expected:
            assert "protocol error" in caplog.text

        assert AsyncHttpRetryStrategy(on_protocol_errors=False).retry_on_protocol_error(error) is False

    @pytest.mark.parametrize(
        ("status_group", "status_code", "expected"),
        [
            ("info", 100, True),
            ("info", 200, False),
            ("info", 300, False),
            ("redirect", 300, True),
            ("redirect", 200, False),
            ("redirect", 400, False),
            ("client_error", 400, True),
            ("client_error", 200, False),
            ("client_error", 500, False),
            ("server_error", 500, True),
            ("server_error", 200, False),
            ("server_error", 100, False),
        ],
    )
    def test_retry_on_status(
        self, status_group: str, status_code: int, expected: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO):
            result = AsyncHttpRetryStrategy(on_statuses={status_group}).retry_on_status(
                EnhancedResponse(Response(status_code=status_code))
            )

        assert result is expected
        if expected:
            assert "status code" in caplog.text
            assert str(status_code) in caplog.text

    def test_before_logs_retry_attempt(self, caplog: pytest.LogCaptureFixture, sample_retry_state: RetryState) -> None:
        with caplog.at_level(logging.INFO):
            AsyncHttpRetryStrategy(attempts=3).before(sample_retry_state)

        assert "Retrying HTTP request" in caplog.text
        assert "REQUEST-TEST" in caplog.text
        assert "1/3" in caplog.text
        assert "GET http://example.com" in caplog.text

    def test_error_callback_logs_failure(
        self, caplog: pytest.LogCaptureFixture, sample_retry_state: RetryState
    ) -> None:
        with pytest.raises(RetryError), caplog.at_level(logging.ERROR):
            AsyncHttpRetryStrategy(attempts=3).error_callback(sample_retry_state)

        assert "All retry attempts" in caplog.text
        assert "1/3" in caplog.text
        assert "failed for HTTP request" in caplog.text
        assert "REQUEST-TEST" in caplog.text
        assert "GET http://example.com" in caplog.text


class SampleBrokerHttpMessageBuilder(BrokerHttpMessageBuilder):
    def build_metadata(
        self, request: EnhancedRequest, response: EnhancedResponse, details: DetailsType
    ) -> dict[str, Any] | None:
        return {"key": "value"}

    def build_body(self, request: EnhancedRequest, response: EnhancedResponse, details: DetailsType) -> str:
        return "body"


class TestBrokerHttpMessageBuilder:
    def test_inherits_broker_message_builder(self) -> None:
        assert issubclass(BrokerHttpMessageBuilder, BrokerMessageBuilder)

    def test_has_abstract_methods(self) -> None:
        assert len(BrokerHttpMessageBuilder.__abstractmethods__) == 2
        assert "build_metadata" in BrokerHttpMessageBuilder.__abstractmethods__
        assert "build_body" in BrokerHttpMessageBuilder.__abstractmethods__

    def test_filter_default_returns_true(
        self, sample_request: EnhancedRequest, sample_response: EnhancedResponse, sample_details: DetailsType
    ) -> None:
        instance = SampleBrokerHttpMessageBuilder()
        assert instance.filter(sample_request, sample_response, sample_details) is True


class SampleHttpClient(HttpClientBase):
    def __init__(
        self,
        request_log_config: HttpRequestLogConfig | None = None,
        response_log_config: HttpResponseLogConfig | None = None,
    ) -> None:
        self.request_log_config = request_log_config or HttpRequestLogConfig()
        self.response_log_config = response_log_config or HttpResponseLogConfig()


class TestHttpClientBase:
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
                    }
                },
            ),
            (
                HttpRequestLogConfig(
                    request_name=True,
                    request_tag=True,
                    request_method=True,
                    request_url=True,
                    request_headers=True,
                    request_body=True,
                ),
                {
                    "request": {
                        "name": "REQUEST",
                        "tag": "TEST",
                        "method": "GET",
                        "url": "http://example.com",
                        "headers": {"host": "example.com"},
                        "body": "",
                    }
                },
            ),
            (
                HttpRequestLogConfig(
                    request_name=False,
                    request_tag=False,
                    request_method=False,
                    request_url=False,
                    request_headers=False,
                    request_body=False,
                ),
                {},
            ),
        ],
    )
    def test_request_log(
        self,
        log_config: HttpRequestLogConfig | None,
        expected_extra: dict,
        sample_request: EnhancedRequest,
        sample_details: DetailsType,
    ) -> None:
        message, extra = SampleHttpClient(request_log_config=log_config).request_log(sample_request, sample_details)

        assert "Sending HTTP request" in message
        assert "REQUEST-TEST" in message
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
                },
            ),
            (
                HttpResponseLogConfig(
                    request_name=True,
                    request_tag=True,
                    request_method=True,
                    request_url=True,
                    response_status_code=True,
                    response_headers=True,
                    response_body=True,
                    response_elapsed_time=True,
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
                },
            ),
            (
                HttpResponseLogConfig(
                    request_name=False,
                    request_tag=False,
                    request_method=False,
                    request_url=False,
                    response_status_code=False,
                    response_headers=False,
                    response_body=False,
                    response_elapsed_time=False,
                ),
                {},
            ),
        ],
    )
    def test_response_log(
        self,
        log_config: HttpResponseLogConfig | None,
        expected_extra: dict,
        sample_response: EnhancedResponse,
        sample_details: DetailsType,
    ) -> None:
        message, extra = SampleHttpClient(response_log_config=log_config).response_log(sample_response, sample_details)

        assert "HTTP response received" in message
        assert "REQUEST-TEST" in message
        assert "GET http://example.com" in message
        assert "200" in message

        assert extra == expected_extra


class TestHttpClient:
    def test_inherits_http_client_base(self) -> None:
        assert issubclass(HttpClient, HttpClientBase)


class TestAsyncHttpClient:
    def test_inherits_http_client_base(self) -> None:
        assert issubclass(AsyncHttpClient, HttpClientBase)
