from collections.abc import Mapping, Sequence
from typing import Union

import httpx

UrlType = str

PrimitiveValue = httpx._types.PrimitiveData

ParamsType = Mapping[str, Union[PrimitiveValue, Sequence[PrimitiveValue]]]
HeadersType = Mapping[str, str]
CookiesType = Mapping[str, str]

ContentBodyType = str
# Represents only variations of the JSON type that the client currently needs.
JsonBodyType = Union[Mapping[str, any], Sequence[dict[str, any]]]

ProxyType = str
CertType = httpx._types.CertTypes
TimeoutType = float
