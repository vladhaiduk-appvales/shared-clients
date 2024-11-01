from __future__ import annotations

from typing import Any


class Unset:
    pass


UNSET = Unset()


def setattr_if_not_unset(obj: object, name: str, value: Any | Unset) -> None:
    if value is not UNSET:
        setattr(obj, name, value)
