from utils.unset import UNSET, setattr_if_not_unset


class Obj:
    pass


class TestUnsetUtils:
    def test_setattr_if_not_unset_sets_attribute(self) -> None:
        obj = Obj()
        setattr_if_not_unset(obj, "attr", 1)

        assert obj.attr == 1

    def test_setattr_if_not_unset_does_not_set_attribute(self) -> None:
        obj = Obj()
        setattr_if_not_unset(obj, "attr", UNSET)

        assert not hasattr(obj, "attr")
