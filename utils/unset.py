from __future__ import annotations


class Unset:
    pass


UNSET = Unset()


def setattr_if_not_unset(obj: object, name: str, value: any | Unset) -> None:
    if value is not UNSET:
        setattr(obj, name, value)
