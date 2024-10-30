from patterns.singleton import OptionalSingletonMeta, SingletonMeta


class SingletonObject(metaclass=SingletonMeta):
    def __init__(self, value: any) -> None:
        self.value = value


class TestSingletonMeta:
    def test_singleton_behaviour(self) -> None:
        instance1 = SingletonObject(1)
        instance2 = SingletonObject(2)

        assert instance1 is instance2
        assert instance1.value == 1
        assert instance2.value == 1


class OptionalSingletonObject(metaclass=OptionalSingletonMeta):
    def __init__(self, value: any) -> None:
        self.value = value


class TestOptionalSingletonMeta:
    def test_default_behaviour(self) -> None:
        instance1 = OptionalSingletonObject(1)
        instance2 = OptionalSingletonObject(2)

        assert instance1 is not instance2
        assert instance1.value == 1
        assert instance2.value == 2

    def test_singleton_behaviour(self) -> None:
        instance1 = OptionalSingletonObject(1, singleton=True)
        instance2 = OptionalSingletonObject(2, singleton=True)

        assert instance1 is instance2
        assert instance1.value == 1
        assert instance2.value == 1
