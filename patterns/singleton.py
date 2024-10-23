from __future__ import annotations

from typing import ClassVar, TypeVar

T = TypeVar("T", bound="SingletonMeta")


class SingletonMeta(type):
    _instances: ClassVar[dict[type[T], T]] = {}

    def __call__(cls, *args: any, **kwargs: any) -> T:
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class OptionalSingletonMeta(SingletonMeta):
    def __call__(cls, *args: any, **kwargs: any) -> T:
        singleton = kwargs.pop("singleton", False)

        if singleton:
            # Use SingletonMeta's __call__ method to ensure singleton behavior.
            return super().__call__(*args, **kwargs)

        # Use type's __call__ method to create a new instance every time.
        return super(SingletonMeta, cls).__call__(*args, **kwargs)


# Just 3 examples of how to they work.
class Dumb:
    def __init__(self, name: str) -> None:
        self.name = name


dumb_1 = Dumb("first")
dumb_2 = Dumb("second")

print(dumb_1 is dumb_2)  # False


class SingletonDumb(metaclass=SingletonMeta):
    def __init__(self, name: str) -> None:
        self.name = name


s_dumb_1 = SingletonDumb("first")
s_dumb_2 = SingletonDumb("second")

print(s_dumb_1 is s_dumb_2)  # True


class OptionalSingletonDumb(metaclass=OptionalSingletonMeta):
    def __init__(self, name: str) -> None:
        self.name = name


os_dumb_1 = OptionalSingletonDumb("first")
os_dumb_2 = OptionalSingletonDumb("second")

os_dumb_3 = OptionalSingletonDumb("third", singleton=True)
os_dumb_4 = OptionalSingletonDumb("fourth", singleton=True)

print(os_dumb_1 is os_dumb_2)  # False
print(os_dumb_3 is os_dumb_4)  # True
print(os_dumb_1.name, os_dumb_2.name, os_dumb_3.name, os_dumb_4.name)  # first second third third

os_dumb_5 = OptionalSingletonDumb("fifth")

print(os_dumb_5.name)
