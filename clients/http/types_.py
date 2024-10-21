from collections.abc import Mapping, Sequence
from typing import Optional, Union

UrlType = str

PrimitiveValue = Union[int, float, bool, str, None]

ParamsType = Mapping[str, Union[PrimitiveValue, Sequence[PrimitiveValue]]]
HeadersType = Mapping[str, str]
CookiesType = Mapping[str, str]

ContentBodyType = str
# Represents only variations of the JSON type that the client currently needs.
JsonBodyType = Union[Mapping[str, any], Sequence[dict[str, any]]]

ProxyType = str
CertType = Union[
    # certfile
    str,
    # (certfile, keyfile)
    tuple[str, Optional[str]],
    # (certfile, keyfile, password)
    tuple[str, Optional[str], Optional[str]],
]
TimeoutType = float
