import datetime as dt

import pytest
from pytest_mock import MockerFixture

from clients.http.request import Request
from clients.http.response import EnhancedResponse, Response


class TestEnhancedResponse:
    @pytest.fixture
    def sample_response(self) -> Response:
        response = Response(200, request=Request("GET", "http://example.com"))
        response._elapsed = dt.timedelta(seconds=1)
        return response

    @pytest.fixture
    def sample_enhanced_response(self, sample_response: Response) -> EnhancedResponse:
        return EnhancedResponse(sample_response)

    def test_origin_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.origin == sample_response

    def test_status_code_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.status_code == sample_response.status_code

    def test_headers_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.headers == dict(sample_response.headers)

    def test_cookies_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.cookies == dict(sample_response.cookies)

    def test_request_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.request == sample_response.request

    def test_elapsed_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.elapsed == sample_response.elapsed

    def test_is_info_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.is_info == sample_response.is_informational

    def test_is_success_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.is_success == sample_response.is_success

    def test_is_redirect_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.is_redirect == sample_response.is_redirect

    def test_is_client_error_property(
        self, sample_response: Response, sample_enhanced_response: EnhancedResponse
    ) -> None:
        assert sample_enhanced_response.is_client_error == sample_response.is_client_error

    def test_is_server_error_property(
        self, sample_response: Response, sample_enhanced_response: EnhancedResponse
    ) -> None:
        assert sample_enhanced_response.is_server_error == sample_response.is_server_error

    def test_is_error_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.is_error == sample_response.is_error

    def test_content_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.content == sample_response.content

    def test_text_property(self, sample_response: Response, sample_enhanced_response: EnhancedResponse) -> None:
        assert sample_enhanced_response.text == sample_response.text

    def test_json(
        self, mocker: MockerFixture, sample_response: Response, sample_enhanced_response: EnhancedResponse
    ) -> None:
        mock_sample_response_json = mocker.patch.object(sample_response, "json")
        sample_enhanced_response.json()
        mock_sample_response_json.assert_called_once()

    def test_xml(self, mocker: MockerFixture, sample_enhanced_response: EnhancedResponse) -> None:
        mock_xmltodict_parse = mocker.patch("xmltodict.parse")
        sample_enhanced_response.xml()
        mock_xmltodict_parse.assert_called_once_with(sample_enhanced_response.content)

    def test_raise_for_status(
        self, mocker: MockerFixture, sample_response: Response, sample_enhanced_response: EnhancedResponse
    ) -> None:
        mock_sample_response_raise_for_status = mocker.patch.object(sample_response, "raise_for_status")
        sample_enhanced_response.raise_for_status()
        mock_sample_response_raise_for_status.assert_called()
