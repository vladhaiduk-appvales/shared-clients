import logging

import httpx
import pytest

from clients.http.base import AsyncHttpRetryStrategy, HttpRetryStrategy
from clients.http.request import EnhancedRequest, Request
from clients.http.response import EnhancedResponse, Response
from retry.base import AsyncRetryStrategy, RetryError, RetryState, RetryStrategy


class TestHttpRetryStrategy:
    @pytest.fixture
    def sample_retry_state(self) -> RetryState:
        return RetryState(
            None,
            None,
            (EnhancedRequest(Request("GET", "http://example.com")),),
            {"details": {"request_label": "REQUEST-TEST"}},
        )

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
