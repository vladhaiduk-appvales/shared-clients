import pytest

from clients.http.request import EnhancedRequest, Request


class TestEnhancedRequest:
    @pytest.fixture
    def sample_request(self) -> str:
        return Request("GET", "https://httpbin.org/get")

    @pytest.fixture
    def sample_enhanced_request(self, sample_request: Request) -> EnhancedRequest:
        return EnhancedRequest(sample_request)

    def test_origin_property(self, sample_request: Request, sample_enhanced_request: EnhancedRequest) -> None:
        assert sample_enhanced_request.origin == sample_request

    def test_method_property(self, sample_request: Request, sample_enhanced_request: EnhancedRequest) -> None:
        assert sample_enhanced_request.method == str(sample_request.method)

    def test_url_property(self, sample_request: Request, sample_enhanced_request: EnhancedRequest) -> None:
        assert sample_enhanced_request.url == str(sample_request.url)

    def test_headers_property(self, sample_request: Request, sample_enhanced_request: EnhancedRequest) -> None:
        assert sample_enhanced_request.headers == dict(sample_request.headers)

    def test_content_property(self, sample_request: Request, sample_enhanced_request: EnhancedRequest) -> None:
        assert sample_enhanced_request.content == sample_request.content

    def test_text_property(self, sample_request: Request, sample_enhanced_request: EnhancedRequest) -> None:
        assert sample_enhanced_request.text == sample_request.content.decode()
