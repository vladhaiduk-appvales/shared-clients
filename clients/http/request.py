import httpx

Request = httpx.Request


class EnhancedRequest:
    """Enhanced HTTPX `Request` Wrapper.

    This class wraps an `httpx.Request` object, providing easy access to its essential properties
    and methods, with additional functionality for improved usability in handling HTTP requests.
    """

    def __init__(self, request: Request) -> None:
        self._request = request

    @property
    def origin(self) -> Request:
        return self._request

    @property
    def method(self) -> str:
        return str(self._request.method)

    @property
    def url(self) -> str:
        return str(self._request.url)

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._request.headers)

    @property
    def content(self) -> bytes:
        return self._request.content

    @property
    def text(self) -> str:
        return self._request.content.decode()
