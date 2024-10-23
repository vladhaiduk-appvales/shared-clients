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


if __name__ == "__main__":

    class Dumb:
        def __init__(self, name: str) -> None:
            self.name = name

    dumb_1 = Dumb("first")
    dumb_2 = Dumb("second")

    print(dumb_1 is dumb_2)  # False

    class DumbSingleton(metaclass=SingletonMeta):
        def __init__(self, name: str) -> None:
            self.name = name

    s_dumb_1 = DumbSingleton("first")
    s_dumb_2 = DumbSingleton("second")

    print(s_dumb_1 is s_dumb_2)  # True

    class DumbOptionalSingleton(metaclass=OptionalSingletonMeta):
        def __init__(self, name: str) -> None:
            self.name = name

    os_dumb_1 = DumbOptionalSingleton("first")
    os_dumb_2 = DumbOptionalSingleton("second")

    os_dumb_3 = DumbOptionalSingleton("third", singleton=True)
    os_dumb_4 = DumbOptionalSingleton("fourth", singleton=True)

    print(os_dumb_1 is os_dumb_2)  # False
    print(os_dumb_3 is os_dumb_4)  # True
    print(os_dumb_1.name, os_dumb_2.name, os_dumb_3.name, os_dumb_4.name)  # first second third third

    os_dumb_5 = DumbOptionalSingleton("fifth")

    print(os_dumb_5.name)  # fifth
