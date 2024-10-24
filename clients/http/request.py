import httpx

Request = httpx.Request


class EnhancedRequest:
    """Enhanced HTTPX Request Wrapper.

    A wrapper around the httpx.Request object that exposes essential properties and methods,
    while providing additional functionality for enhanced usability.

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
