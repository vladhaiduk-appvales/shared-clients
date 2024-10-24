import datetime as dt

import httpx

Response = httpx.Response


class EnhancedResponse:
    """Enhanced HTTPX Response Wrapper.

    A wrapper around the httpx.Response object that exposes essential properties and methods,
    while providing additional functionality for enhanced usability.

    """

    def __init__(self, response: Response) -> None:
        self._response = response

    @property
    def origin(self) -> Response:
        return self._response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._response.headers)

    @property
    def cookies(self) -> dict[str, str]:
        return dict(self._response.cookies)

    @property
    def request(self) -> httpx.Request:
        return self._response.request

    @property
    def elapsed(self) -> dt.timedelta:
        return self._response.elapsed

    @property
    def content(self) -> bytes:
        return self._response.content

    @property
    def text(self) -> str:
        return self._response.text

    def json(self, **kwargs: any) -> any:
        return self._response.json(**kwargs)

    def raise_for_status(self) -> None:
        self._response.raise_for_status()
