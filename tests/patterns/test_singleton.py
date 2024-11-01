from typing import Any

from patterns.singleton import OptionalSingletonMeta, SingletonMeta


class SampleSingleton(metaclass=SingletonMeta):
    def __init__(self, value: Any) -> None:
        self.value = value


class TestSingletonMeta:
    def test_singleton_behaviour(self) -> None:
        instance1 = SampleSingleton(1)
        instance2 = SampleSingleton(2)

        assert instance1 is instance2
        assert instance1.value == 1
        assert instance2.value == 1


class SampleOptionalSingleton(metaclass=OptionalSingletonMeta):
    def __init__(self, value: Any) -> None:
        self.value = value


class TestOptionalSingletonMeta:
    def test_default_behaviour(self) -> None:
        instance1 = SampleOptionalSingleton(1)
        instance2 = SampleOptionalSingleton(2)

        assert instance1 is not instance2
        assert instance1.value == 1
        assert instance2.value == 2

    def test_singleton_behaviour(self) -> None:
        instance1 = SampleOptionalSingleton(1, singleton=True)
        instance2 = SampleOptionalSingleton(2, singleton=True)

        assert instance1 is instance2
        assert instance1.value == 1
        assert instance2.value == 1
