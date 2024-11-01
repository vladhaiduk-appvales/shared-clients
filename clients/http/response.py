import datetime as dt
from typing import Any

import httpx
import xmltodict

Response = httpx.Response


class EnhancedResponse:
    """Enhanced HTTPX `Response` Wrapper.

    This class wraps an `httpx.Response` object, providing easy access to its essential properties
    and methods, with additional functionality for improved usability in handling HTTP responses.
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
    def is_info(self) -> bool:
        return self._response.is_informational

    @property
    def is_success(self) -> bool:
        return self._response.is_success

    @property
    def is_redirect(self) -> bool:
        return self._response.is_redirect

    @property
    def is_client_error(self) -> bool:
        return self._response.is_client_error

    @property
    def is_server_error(self) -> bool:
        return self._response.is_server_error

    @property
    def is_error(self) -> bool:
        return self._response.is_error

    @property
    def content(self) -> bytes:
        return self._response.content

    @property
    def text(self) -> str:
        return self._response.text

    def json(self, **kwargs: Any) -> Any:
        return self._response.json(**kwargs)

    def xml(self, **kwargs: Any) -> dict[str, Any]:
        return dict(xmltodict.parse(self.content, **kwargs))

    def raise_for_status(self) -> None:
        self._response.raise_for_status()


if __name__ == "__main__":
    xml_content = b"""
    <audience>
        <id what="attribute">456</id>
        <name>John Doe</name>
        <email>johndoe@example.com</email>
        <phone>+1234567890</phone>
        <addresses>
            <address>
                <street>123 Elm Street</street>
                <city>Springfield</city>
                <state>IL</state>
                <zip>62701</zip>
            </address>
            <address>
                <street>456 Oak Avenue</street>
                <city>Metropolis</city>
                <state>NY</state>
                <zip>10001</zip>
            </address>
        </addresses>
    </audience>
    """
    response = Response(200, content=xml_content, headers={"Content-Type": "application/xml"})
    enhanced_response = EnhancedResponse(response)

    print(enhanced_response.xml())
