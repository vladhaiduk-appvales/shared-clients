from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from clients.broker.base import AsyncBrokerClient, BrokerClient, BrokerMessageBuilder
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
    @pytest.fixture(autouse=True)
    def reset_class_attributes(self) -> Generator[None, None, None]:
        yield

        HttpClient.base_url = ""
        HttpClient.base_params = None
        HttpClient.base_headers = None
        HttpClient.cookies = None
        HttpClient.auth = None
        HttpClient.proxy = None
        HttpClient.cert = None
        HttpClient.timeout = 5.0

        HttpClient.retry_strategy = None
        HttpClient.request_log_config = HttpRequestLogConfig()
        HttpClient.response_log_config = HttpResponseLogConfig()
        HttpClient.broker_client = None
        HttpClient.broker_message_builder = None

        HttpClient._global_client = None

    @pytest.fixture
    def mock_httpx_client(self, mocker: MockerFixture) -> MockerFixture:
        return mocker.patch("httpx.Client")

    def test_inherits_http_client_base(self) -> None:
        assert issubclass(HttpClient, HttpClientBase)

    def test_default_class_attributes(self) -> None:
        assert HttpClient.base_url == ""
        assert HttpClient.base_params is None
        assert HttpClient.base_headers is None
        assert HttpClient.cookies is None
        assert HttpClient.auth is None
        assert HttpClient.proxy is None
        assert HttpClient.cert is None
        assert HttpClient.timeout == 5.0

        assert HttpClient.retry_strategy is None
        assert HttpClient.request_log_config == HttpRequestLogConfig()
        assert HttpClient.response_log_config == HttpResponseLogConfig()
        assert HttpClient.broker_client is None
        assert HttpClient.broker_message_builder is None

        assert HttpClient._global_client is None

    def test_configure_sets_only_specified_class_attributes(self) -> None:
        HttpClient.configure(
            base_params={"class_param": "value"},
            base_headers={"class_header": "value"},
            cookies={"class_cookie": "value"},
        )

        assert HttpClient.base_url == ""
        assert HttpClient.base_params == {"class_param": "value"}
        assert HttpClient.base_headers == {"class_header": "value"}
        assert HttpClient.cookies == {"class_cookie": "value"}
        assert HttpClient.auth is None
        assert HttpClient.proxy is None
        assert HttpClient.cert is None
        assert HttpClient.timeout == 5.0

        assert HttpClient.retry_strategy is None
        assert HttpClient.request_log_config == HttpRequestLogConfig()
        assert HttpClient.response_log_config == HttpResponseLogConfig()
        assert HttpClient.broker_client is None
        assert HttpClient.broker_message_builder is None

        assert HttpClient._global_client is None

    def test_init_sets_only_specified_instance_attributes(self) -> None:
        client = HttpClient(
            base_params={"instance_param": "value"},
            base_headers={"instance_header": "value"},
            cookies={"instance_cookie": "value"},
        )

        assert client.base_url == ""
        assert client.base_params == {"instance_param": "value"}
        assert client.base_headers == {"instance_header": "value"}
        assert client.cookies == {"instance_cookie": "value"}
        assert client.auth is None
        assert client.proxy is None
        assert client.cert is None
        assert client.timeout == 5.0

        assert client.retry_strategy is None
        assert client.request_log_config == HttpRequestLogConfig()
        assert client.response_log_config == HttpResponseLogConfig()
        assert client.broker_client is None
        assert client.broker_message_builder is None

        assert client._global_client is None
        assert client._local_client is None

    def test_open_global_unopened_sets_global_client(self, mock_httpx_client: MagicMock) -> None:
        HttpClient.open_global()

        assert HttpClient._global_client is not None
        mock_httpx_client.assert_called_once_with(
            base_url=HttpClient.base_url,
            params=HttpClient.base_params,
            headers=HttpClient.base_headers,
            cookies=HttpClient.cookies,
            auth=HttpClient.auth,
            proxy=HttpClient.proxy,
            cert=HttpClient.cert,
            timeout=HttpClient.timeout,
        )

    def test_open_global_opened_does_not_set_global_client(self, mock_httpx_client: MagicMock) -> None:
        HttpClient.open_global()
        HttpClient.open_global()

        assert HttpClient._global_client is not None
        mock_httpx_client.assert_called_once_with(
            base_url=HttpClient.base_url,
            params=HttpClient.base_params,
            headers=HttpClient.base_headers,
            cookies=HttpClient.cookies,
            auth=HttpClient.auth,
            proxy=HttpClient.proxy,
            cert=HttpClient.cert,
            timeout=HttpClient.timeout,
        )

    def test_close_global_opened_closes_global_client(self, mock_httpx_client: MagicMock) -> None:
        HttpClient.open_global()
        HttpClient.close_global()

        assert HttpClient._global_client is not None
        mock_httpx_client.return_value.close.assert_called_once()

    def test_close_global_unopened_does_not_close_global_client(self, mock_httpx_client: MagicMock) -> None:
        HttpClient.close_global()

        assert HttpClient._global_client is None
        mock_httpx_client.return_value.close.assert_not_called()

    def test_open_unopened_sets_local_client(self, mock_httpx_client: MagicMock) -> None:
        client = HttpClient()
        client.open()

        assert client._local_client is not None
        mock_httpx_client.assert_called_once_with(
            base_url=client.base_url,
            params=client.base_params,
            headers=client.base_headers,
            cookies=client.cookies,
            auth=client.auth,
            proxy=client.proxy,
            cert=client.cert,
            timeout=client.timeout,
        )

    def test_open_opened_does_not_set_local_client(self, mock_httpx_client: MagicMock) -> None:
        client = HttpClient()
        client.open()
        client.open()

        assert client._local_client is not None
        mock_httpx_client.assert_called_once_with(
            base_url=client.base_url,
            params=client.base_params,
            headers=client.base_headers,
            cookies=client.cookies,
            auth=client.auth,
            proxy=client.proxy,
            cert=client.cert,
            timeout=client.timeout,
        )

    def test_close_opened_closes_local_client(self, mock_httpx_client: MagicMock) -> None:
        client = HttpClient()
        client.open()
        client.close()

        assert client._local_client is not None
        mock_httpx_client.return_value.close.assert_called_once()

    def test_close_unopened_does_not_close_local_client(self, mock_httpx_client: MagicMock) -> None:
        client = HttpClient()
        client.close()

        assert client._local_client is None
        mock_httpx_client.return_value.close.assert_not_called()

    def test_client_property_returns_global_client(self) -> None:
        client = HttpClient()
        HttpClient.open_global()

        assert client._client is HttpClient._global_client

    def test_client_property_returns_local_client(self) -> None:
        client = HttpClient()
        client.open()

        assert client._client is client._local_client

    def test_client_property_returns_local_client_over_global_client(self) -> None:
        client = HttpClient()
        HttpClient.open_global()
        client.open()

        assert client._client is client._local_client

    def test_client_property_opens_local_client_and_returns_it(self, mock_httpx_client: MagicMock) -> None:
        client = HttpClient()

        assert client._client is client._local_client
        mock_httpx_client.assert_called_once_with(
            base_url=client.base_url,
            params=client.base_params,
            headers=client.base_headers,
            cookies=client.cookies,
            auth=client.auth,
            proxy=client.proxy,
            cert=client.cert,
            timeout=client.timeout,
        )

    def test_enter_opens_local_client_and_returns_self(self, mock_httpx_client: MagicMock) -> None:
        client = HttpClient()

        assert client.__enter__() is client
        assert client._local_client is not None

        mock_httpx_client.assert_called_once_with(
            base_url=client.base_url,
            params=client.base_params,
            headers=client.base_headers,
            cookies=client.cookies,
            auth=client.auth,
            proxy=client.proxy,
            cert=client.cert,
            timeout=client.timeout,
        )
        mock_httpx_client.return_value.__enter__.assert_called_once()

    def test_exit_closes_local_client(self, mock_httpx_client: MagicMock) -> None:
        client = HttpClient()
        client.__enter__()
        client.__exit__(None, None, None)

        assert client._local_client is not None

        mock_httpx_client.return_value.__exit__.assert_called_once()
        mock_httpx_client.return_value.close.assert_called_once()

    def test_send_request_sends_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_client: MagicMock
    ) -> None:
        spy_request_log = mocker.spy(HttpClient, "request_log")
        spy_response_log = mocker.spy(HttpClient, "response_log")

        original_request = Request("GET", "http://example.com")
        request = EnhancedRequest(original_request)
        details = {
            "request_name": "REQUEST",
            "request_tag": "TEST",
            "request_label": "REQUEST-TEST",
        }

        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with HttpClient() as client:
            response = client._send_request(request, details=details)

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        mock_httpx_client.return_value.send.assert_called_once_with(original_request, auth=None)
        spy_request_log.assert_called_once_with(client, request, details)
        spy_response_log.assert_called_once_with(client, response, details)

    def test_request_sends_request_and_returns_response(self, mock_httpx_client: MagicMock) -> None:
        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with HttpClient() as client:
            response = client.request("GET", "http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

    def test_request_with_retry_strategy_retries_send_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_client: MagicMock
    ) -> None:
        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with HttpClient(retry_strategy=HttpRetryStrategy(attempts=3)) as client:
            spy_retry_strategy_retry = mocker.spy(client.retry_strategy, "retry")
            response = client.request("GET", "http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_retry_strategy_retry.assert_called_once()

    def test_request_with_broker_client_sends_message_to_broker_and_returns_response(
        self, mock_httpx_client: MagicMock
    ) -> None:
        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        mock_broker_client = MagicMock(spec=BrokerClient)
        mock_broker_message_builder = MagicMock(spec=BrokerHttpMessageBuilder)
        mock_broker_message_builder.build.return_value = "message"

        with HttpClient(broker_client=mock_broker_client, broker_message_builder=mock_broker_message_builder) as client:
            response = client.request("GET", "http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        mock_broker_message_builder.build.assert_called_once()
        mock_broker_client.send_message.assert_called_once_with(message="message")

    def test_get_sends_get_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(HttpClient, "request")

        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with HttpClient() as client:
            response = client.get("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "GET",
            "http://example.com",
            name=None,
            tag=None,
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
        spy_request = mocker.spy(HttpClient, "request")

        original_request = Request("POST", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with HttpClient() as client:
            response = client.post("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "POST",
            "http://example.com",
            name=None,
            tag=None,
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
        spy_request = mocker.spy(HttpClient, "request")

        original_request = Request("PUT", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with HttpClient() as client:
            response = client.put("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "PUT",
            "http://example.com",
            name=None,
            tag=None,
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
        spy_request = mocker.spy(HttpClient, "request")

        original_request = Request("PATCH", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with HttpClient() as client:
            response = client.patch("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "PATCH",
            "http://example.com",
            name=None,
            tag=None,
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
        spy_request = mocker.spy(HttpClient, "request")

        original_request = Request("DELETE", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_client.return_value.send.return_value = original_response

        with HttpClient() as client:
            response = client.delete("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "DELETE",
            "http://example.com",
            name=None,
            tag=None,
            params=None,
            headers=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )


class TestAsyncHttpClient:
    @pytest.fixture(autouse=True)
    def reset_class_attributes(self) -> Generator[None, None, None]:
        yield

        AsyncHttpClient.base_url = ""
        AsyncHttpClient.base_params = None
        AsyncHttpClient.base_headers = None
        AsyncHttpClient.cookies = None
        AsyncHttpClient.auth = None
        AsyncHttpClient.proxy = None
        AsyncHttpClient.cert = None
        AsyncHttpClient.timeout = 5.0

        AsyncHttpClient.retry_strategy = None
        AsyncHttpClient.request_log_config = HttpRequestLogConfig()
        AsyncHttpClient.response_log_config = HttpResponseLogConfig()
        AsyncHttpClient.broker_client = None
        AsyncHttpClient.broker_message_builder = None

        AsyncHttpClient._global_client = None

    @pytest.fixture
    def mock_httpx_async_client(self, mocker: MockerFixture) -> MockerFixture:
        return mocker.patch("httpx.AsyncClient", return_value=AsyncMock(spec=httpx.AsyncClient))

    def test_inherits_http_client_base(self) -> None:
        assert issubclass(AsyncHttpClient, HttpClientBase)

    def test_default_class_attributes(self) -> None:
        assert AsyncHttpClient.base_url == ""
        assert AsyncHttpClient.base_params is None
        assert AsyncHttpClient.base_headers is None
        assert AsyncHttpClient.cookies is None
        assert AsyncHttpClient.auth is None
        assert AsyncHttpClient.proxy is None
        assert AsyncHttpClient.cert is None
        assert AsyncHttpClient.timeout == 5.0

        assert AsyncHttpClient.retry_strategy is None
        assert AsyncHttpClient.request_log_config == HttpRequestLogConfig()
        assert AsyncHttpClient.response_log_config == HttpResponseLogConfig()
        assert AsyncHttpClient.broker_client is None
        assert AsyncHttpClient.broker_message_builder is None

        assert AsyncHttpClient._global_client is None

    def test_configure_sets_only_specified_class_attributes(self) -> None:
        AsyncHttpClient.configure(
            base_params={"class_param": "value"},
            base_headers={"class_header": "value"},
            cookies={"class_cookie": "value"},
        )

        assert AsyncHttpClient.base_url == ""
        assert AsyncHttpClient.base_params == {"class_param": "value"}
        assert AsyncHttpClient.base_headers == {"class_header": "value"}
        assert AsyncHttpClient.cookies == {"class_cookie": "value"}
        assert AsyncHttpClient.auth is None
        assert AsyncHttpClient.proxy is None
        assert AsyncHttpClient.cert is None
        assert AsyncHttpClient.timeout == 5.0

        assert AsyncHttpClient.retry_strategy is None
        assert AsyncHttpClient.request_log_config == HttpRequestLogConfig()
        assert AsyncHttpClient.response_log_config == HttpResponseLogConfig()
        assert AsyncHttpClient.broker_client is None
        assert AsyncHttpClient.broker_message_builder is None

        assert AsyncHttpClient._global_client is None

    def test_init_sets_only_specified_instance_attributes(self) -> None:
        client = AsyncHttpClient(
            base_params={"instance_param": "value"},
            base_headers={"instance_header": "value"},
            cookies={"instance_cookie": "value"},
        )

        assert client.base_url == ""
        assert client.base_params == {"instance_param": "value"}
        assert client.base_headers == {"instance_header": "value"}
        assert client.cookies == {"instance_cookie": "value"}
        assert client.auth is None
        assert client.proxy is None
        assert client.cert is None
        assert client.timeout == 5.0

        assert client.retry_strategy is None
        assert client.request_log_config == HttpRequestLogConfig()
        assert client.response_log_config == HttpResponseLogConfig()
        assert client.broker_client is None
        assert client.broker_message_builder is None

        assert client._global_client is None
        assert client._local_client is None

    def test_open_global_unopened_sets_global_client(self, mock_httpx_async_client: MagicMock) -> None:
        AsyncHttpClient.open_global()

        assert AsyncHttpClient._global_client is not None
        mock_httpx_async_client.assert_called_once_with(
            base_url=AsyncHttpClient.base_url,
            params=AsyncHttpClient.base_params,
            headers=AsyncHttpClient.base_headers,
            cookies=AsyncHttpClient.cookies,
            auth=AsyncHttpClient.auth,
            proxy=AsyncHttpClient.proxy,
            cert=AsyncHttpClient.cert,
            timeout=AsyncHttpClient.timeout,
        )

    def test_open_global_opened_does_not_set_global_client(self, mock_httpx_async_client: MagicMock) -> None:
        AsyncHttpClient.open_global()
        AsyncHttpClient.open_global()

        assert AsyncHttpClient._global_client is not None
        mock_httpx_async_client.assert_called_once_with(
            base_url=AsyncHttpClient.base_url,
            params=AsyncHttpClient.base_params,
            headers=AsyncHttpClient.base_headers,
            cookies=AsyncHttpClient.cookies,
            auth=AsyncHttpClient.auth,
            proxy=AsyncHttpClient.proxy,
            cert=AsyncHttpClient.cert,
            timeout=AsyncHttpClient.timeout,
        )

    @pytest.mark.asyncio
    async def test_close_global_opened_closes_global_client(self, mock_httpx_async_client: MagicMock) -> None:
        AsyncHttpClient.open_global()
        await AsyncHttpClient.close_global()

        assert AsyncHttpClient._global_client is not None
        mock_httpx_async_client.return_value.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_global_unopened_does_not_close_global_client(self, mock_httpx_async_client: MagicMock) -> None:
        await AsyncHttpClient.close_global()

        assert AsyncHttpClient._global_client is None
        mock_httpx_async_client.return_value.aclose.assert_not_called()

    def test_open_unopened_sets_local_client(self, mock_httpx_async_client: MagicMock) -> None:
        client = AsyncHttpClient()
        client.open()

        assert client._local_client is not None
        mock_httpx_async_client.assert_called_once_with(
            base_url=client.base_url,
            params=client.base_params,
            headers=client.base_headers,
            cookies=client.cookies,
            auth=client.auth,
            proxy=client.proxy,
            cert=client.cert,
            timeout=client.timeout,
        )

    def test_open_opened_does_not_set_local_client(self, mock_httpx_async_client: MagicMock) -> None:
        client = AsyncHttpClient()
        client.open()
        client.open()

        assert client._local_client is not None
        mock_httpx_async_client.assert_called_once_with(
            base_url=client.base_url,
            params=client.base_params,
            headers=client.base_headers,
            cookies=client.cookies,
            auth=client.auth,
            proxy=client.proxy,
            cert=client.cert,
            timeout=client.timeout,
        )

    @pytest.mark.asyncio
    async def test_close_opened_closes_local_client(self, mock_httpx_async_client: MagicMock) -> None:
        client = AsyncHttpClient()
        client.open()
        await client.close()

        assert client._local_client is not None
        mock_httpx_async_client.return_value.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_unopened_does_not_close_local_client(self, mock_httpx_async_client: MagicMock) -> None:
        client = AsyncHttpClient()
        await client.close()

        assert client._local_client is None
        mock_httpx_async_client.return_value.aclose.assert_not_called()

    def test_client_property_returns_global_client(self) -> None:
        client = AsyncHttpClient()
        AsyncHttpClient.open_global()

        assert client._client is AsyncHttpClient._global_client

    def test_client_property_returns_local_client(self) -> None:
        client = AsyncHttpClient()
        client.open()

        assert client._client is client._local_client

    def test_client_property_returns_local_client_over_global_client(self) -> None:
        client = AsyncHttpClient()
        AsyncHttpClient.open_global()
        client.open()

        assert client._client is client._local_client

    def test_client_property_opens_local_client_and_returns_it(self, mock_httpx_async_client: MagicMock) -> None:
        client = AsyncHttpClient()

        assert client._client is client._local_client
        mock_httpx_async_client.assert_called_once_with(
            base_url=client.base_url,
            params=client.base_params,
            headers=client.base_headers,
            cookies=client.cookies,
            auth=client.auth,
            proxy=client.proxy,
            cert=client.cert,
            timeout=client.timeout,
        )

    @pytest.mark.asyncio
    async def test_aenter_opens_local_client_and_returns_self(self, mock_httpx_async_client: MagicMock) -> None:
        client = AsyncHttpClient()

        assert await client.__aenter__() is client
        assert client._local_client is not None

        mock_httpx_async_client.assert_called_once_with(
            base_url=client.base_url,
            params=client.base_params,
            headers=client.base_headers,
            cookies=client.cookies,
            auth=client.auth,
            proxy=client.proxy,
            cert=client.cert,
            timeout=client.timeout,
        )
        mock_httpx_async_client.return_value.__aenter__.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_closes_local_client(self, mock_httpx_async_client: MagicMock) -> None:
        client = AsyncHttpClient()
        await client.__aenter__()
        await client.__aexit__(None, None, None)

        assert client._local_client is not None

        mock_httpx_async_client.return_value.__aexit__.assert_called_once()
        mock_httpx_async_client.return_value.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_request_sends_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_async_client: MagicMock
    ) -> None:
        spy_request_log = mocker.spy(AsyncHttpClient, "request_log")
        spy_response_log = mocker.spy(AsyncHttpClient, "response_log")

        original_request = Request("GET", "http://example.com")
        request = EnhancedRequest(original_request)
        details = {
            "request_name": "REQUEST",
            "request_tag": "TEST",
            "request_label": "REQUEST-TEST",
        }

        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncHttpClient() as client:
            response = await client._send_request(request, details=details)

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        mock_httpx_async_client.return_value.send.assert_called_once_with(original_request, auth=None)
        spy_request_log.assert_called_once_with(client, request, details)
        spy_response_log.assert_called_once_with(client, response, details)

    @pytest.mark.asyncio
    async def test_request_sends_request_and_returns_response(self, mock_httpx_async_client: MagicMock) -> None:
        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncHttpClient() as client:
            response = await client.request("GET", "http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

    @pytest.mark.asyncio
    async def test_request_with_retry_strategy_retries_send_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_async_client: MagicMock
    ) -> None:
        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncHttpClient(retry_strategy=AsyncHttpRetryStrategy(attempts=3)) as client:
            spy_retry_strategy_retry = mocker.spy(client.retry_strategy, "retry")
            response = await client.request("GET", "http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_retry_strategy_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_with_broker_client_sends_message_to_broker_and_returns_response(
        self, mock_httpx_async_client: MagicMock
    ) -> None:
        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        mock_broker_client = AsyncMock(spec=AsyncBrokerClient)
        mock_broker_message_builder = AsyncMock(spec=BrokerHttpMessageBuilder)
        mock_broker_message_builder.build.return_value = "message"

        async with AsyncHttpClient(
            broker_client=mock_broker_client, broker_message_builder=mock_broker_message_builder
        ) as client:
            response = await client.request("GET", "http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        mock_broker_message_builder.build.assert_called_once()
        mock_broker_client.send_message.assert_called_once_with(message="message")

    @pytest.mark.asyncio
    async def test_get_sends_get_request_and_returns_response(
        self, mocker: MockerFixture, mock_httpx_async_client: MagicMock
    ) -> None:
        spy_request = mocker.spy(AsyncHttpClient, "request")

        original_request = Request("GET", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncHttpClient() as client:
            response = await client.get("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "GET",
            "http://example.com",
            name=None,
            tag=None,
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
        spy_request = mocker.spy(AsyncHttpClient, "request")

        original_request = Request("POST", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncHttpClient() as client:
            response = await client.post("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "POST",
            "http://example.com",
            name=None,
            tag=None,
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
        spy_request = mocker.spy(AsyncHttpClient, "request")

        original_request = Request("PUT", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncHttpClient() as client:
            response = await client.put("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "PUT",
            "http://example.com",
            name=None,
            tag=None,
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
        spy_request = mocker.spy(AsyncHttpClient, "request")

        original_request = Request("PATCH", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncHttpClient() as client:
            response = await client.patch("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "PATCH",
            "http://example.com",
            name=None,
            tag=None,
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
        spy_request = mocker.spy(AsyncHttpClient, "request")

        original_request = Request("DELETE", "http://example.com")
        original_response = Response(200, request=original_request)
        original_response.elapsed = dt.timedelta(seconds=1)
        mock_httpx_async_client.return_value.send.return_value = original_response

        async with AsyncHttpClient() as client:
            response = await client.delete("http://example.com")

        assert isinstance(response, EnhancedResponse)
        assert response.origin is original_response

        spy_request.assert_called_once_with(
            client,
            "DELETE",
            "http://example.com",
            name=None,
            tag=None,
            params=None,
            headers=None,
            auth=UNSET,
            timeout=UNSET,
            retry_strategy=UNSET,
            details=None,
        )
