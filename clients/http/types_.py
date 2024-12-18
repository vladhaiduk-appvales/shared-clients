from collections.abc import Mapping, Sequence
from typing import Any, Literal, Union

import httpx

# Currently, not all HTTP methods are supported by the client.
MethodType = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
UrlType = str

PrimitiveValue = httpx._types.PrimitiveData

ParamsType = Mapping[str, Union[PrimitiveValue, Sequence[PrimitiveValue]]]
HeadersType = Mapping[str, str]
CookiesType = Mapping[str, str]

ContentBodyType = str
# Represents only variations of the JSON type that the client currently needs.
JsonBodyType = Union[Mapping[str, Any], Sequence[dict[str, Any]]]

ProxyType = str
CertType = httpx._types.CertTypes
TimeoutType = float

DetailsType = Mapping[str, Any]
