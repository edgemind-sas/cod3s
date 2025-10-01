from typing import List, Optional, TypeVar

import pydantic

import cod3s.core as core


class SimpleObject(core.ObjCOD3S):
    var1: Optional[str] = pydantic.Field("a")
    var2: Optional[str] = pydantic.Field("b")


class SimpleModel(pydantic.BaseModel):
    x: str
    y: str


class SimpleClass:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def serialize(self):
        return {"x": self.x, "y": self.y}


SimpleClassType = TypeVar("SimpleClass")


class ObjectWithList(SimpleObject):
    simple_object_list: List[SimpleObject] = pydantic.Field([])


class ObjectWithDict(SimpleObject):
    simple_object_dict: dict[str, SimpleObject] = pydantic.Field({})


class ObjectWithCod3sModel(SimpleObject):
    simple_object_cod3s: SimpleObject = pydantic.Field()


class ObjectWithSimpleModel(SimpleObject):
    simple_object_model: SimpleModel = pydantic.Field()


class ObjectWithSimpleClass(SimpleObject):
    simple_object_class: SimpleClassType = pydantic.Field()


class TestModelDump:
    def test_list(self):
        obj1 = SimpleObject(var1="a", var2="b")
        obj2 = SimpleObject(var1="c", var2="d")
        complex_object = ObjectWithList(
            var1="e", var2="f", simple_object_list=[obj1, obj2]
        )
        dump = complex_object.model_dump()
        assert dump == {
            "cls": "ObjectWithList",
            "simple_object_list": [
                {"cls": "SimpleObject", "var1": "a", "var2": "b"},
                {"cls": "SimpleObject", "var1": "c", "var2": "d"},
            ],
            "var1": "e",
            "var2": "f",
        }

    def test_list_none(self):
        obj1 = SimpleObject(var1="a", var2=None)
        obj2 = SimpleObject(var1="c", var2=None)
        complex_object = ObjectWithList(
            var1=None, var2="f", simple_object_list=[obj1, obj2]
        )
        dump = complex_object.model_dump()
        assert dump == {
            "cls": "ObjectWithList",
            "simple_object_list": [
                {"cls": "SimpleObject", "var1": "a", "var2": None},
                {"cls": "SimpleObject", "var1": "c", "var2": None},
            ],
            "var1": None,
            "var2": "f",
        }

    def test_list_exclude_var1(self):
        obj1 = SimpleObject(var1="a", var2="b")
        obj2 = SimpleObject(var1="c", var2="d")
        complex_object = ObjectWithList(
            var1="e", var2="f", simple_object_list=[obj1, obj2]
        )
        dump = complex_object.model_dump(exclude={"var1"})
        assert dump == {
            "cls": "ObjectWithList",
            "simple_object_list": [
                {"cls": "SimpleObject", "var1": "a", "var2": "b"},
                {"cls": "SimpleObject", "var1": "c", "var2": "d"},
            ],
            "var2": "f",
        }

    def test_list_exclude_var2_and_list(self):
        obj1 = SimpleObject(var1="a", var2="b")
        obj2 = SimpleObject(var1="c", var2="d")
        complex_object = ObjectWithList(
            var1="e", var2="f", simple_object_list=[obj1, obj2]
        )
        dump = complex_object.model_dump(exclude={"var2", "simple_object_list"})
        assert dump == {
            "cls": "ObjectWithList",
            "var1": "e",
        }

    def test_list_include_var1(self):
        obj1 = SimpleObject(var1="a", var2="b")
        obj2 = SimpleObject(var1="c", var2="d")
        complex_object = ObjectWithList(
            var1="e", var2="f", simple_object_list=[obj1, obj2]
        )
        dump = complex_object.model_dump(include={"var1"})
        assert dump == {
            "cls": "ObjectWithList",
            "var1": "e",
        }

    def test_list_exclude_none(self):
        obj1 = SimpleObject(var1="a", var2=None)
        obj2 = SimpleObject(var1="c", var2=None)
        complex_object = ObjectWithList(
            var1=None, var2="f", simple_object_list=[obj1, obj2]
        )
        dump = complex_object.model_dump(exclude_none=True)
        assert dump == {
            "cls": "ObjectWithList",
            "simple_object_list": [
                {"cls": "SimpleObject", "var1": "a"},
                {"cls": "SimpleObject", "var1": "c"},
            ],
            "var2": "f",
        }

    def test_list_exclude_defaults(self):
        obj1 = SimpleObject(var1="a", var2="c")
        obj2 = SimpleObject(var1="d", var2="b")
        complex_object = ObjectWithList(var2="f", simple_object_list=[obj1, obj2])
        dump = complex_object.model_dump(exclude_defaults=True)
        assert dump == {
            "cls": "ObjectWithList",
            "simple_object_list": [
                {"cls": "SimpleObject", "var2": "c"},
                {"cls": "SimpleObject", "var1": "d"},
            ],
            "var2": "f",
        }

    def test_dict(self):
        obj1 = SimpleObject(var1="a", var2="b")
        obj2 = SimpleObject(var1="c", var2="d")
        complex_object = ObjectWithDict(
            var1="e", var2="f", simple_object_dict={"obj1": obj1, "obj2": obj2}
        )
        dump = complex_object.model_dump()
        assert dump == {
            "cls": "ObjectWithDict",
            "simple_object_dict": {
                "obj1": {"cls": "SimpleObject", "var1": "a", "var2": "b"},
                "obj2": {"cls": "SimpleObject", "var1": "c", "var2": "d"},
            },
            "var1": "e",
            "var2": "f",
        }

    def test_dict_none(self):
        obj1 = SimpleObject(var1=None, var2="b")
        obj2 = SimpleObject(var1="c", var2=None)
        complex_object = ObjectWithDict(
            var1="e", var2=None, simple_object_dict={"obj1": obj1, "obj2": obj2}
        )
        dump = complex_object.model_dump()
        assert dump == {
            "cls": "ObjectWithDict",
            "simple_object_dict": {
                "obj1": {"cls": "SimpleObject", "var1": None, "var2": "b"},
                "obj2": {"cls": "SimpleObject", "var1": "c", "var2": None},
            },
            "var1": "e",
            "var2": None,
        }

    def test_dict_exclude_none(self):
        obj1 = SimpleObject(var1=None, var2="b")
        obj2 = SimpleObject(var1="c", var2=None)
        complex_object = ObjectWithDict(
            var1="e", var2=None, simple_object_dict={"obj1": obj1, "obj2": obj2}
        )
        dump = complex_object.model_dump(exclude_none=True)
        assert dump == {
            "cls": "ObjectWithDict",
            "simple_object_dict": {
                "obj1": {"cls": "SimpleObject", "var2": "b"},
                "obj2": {"cls": "SimpleObject", "var1": "c"},
            },
            "var1": "e",
        }

    def test_dict_exclude_defaults(self):
        obj1 = SimpleObject(var2="a")
        obj2 = SimpleObject(var1="c")
        complex_object = ObjectWithDict(
            var1="a", var2="z", simple_object_dict={"obj1": obj1, "obj2": obj2}
        )
        dump = complex_object.model_dump(exclude_defaults=True)
        assert dump == {
            "cls": "ObjectWithDict",
            "simple_object_dict": {
                "obj1": {"cls": "SimpleObject", "var2": "a"},
                "obj2": {"cls": "SimpleObject", "var1": "c"},
            },
            "var2": "z",
        }

    def test_dict_exclude_defaults_and_none(self):
        obj1 = SimpleObject(var2="a")
        obj2 = SimpleObject(var1=None)
        complex_object = ObjectWithDict(
            var1="a", var2="z", simple_object_dict={"obj1": obj1, "obj2": obj2}
        )
        dump = complex_object.model_dump(exclude_none=True, exclude_defaults=True)
        assert dump == {
            "cls": "ObjectWithDict",
            "simple_object_dict": {
                "obj1": {"cls": "SimpleObject", "var2": "a"},
                "obj2": {"cls": "SimpleObject"},
            },
            "var2": "z",
        }

    def test_cod3s_model(self):
        obj1 = SimpleObject(var1="a", var2="b")
        complex_object = ObjectWithCod3sModel(
            var1="c", var2="d", simple_object_cod3s=obj1
        )
        dump = complex_object.model_dump()
        assert dump == {
            "cls": "ObjectWithCod3sModel",
            "simple_object_cod3s": {
                "cls": "SimpleObject",
                "var1": "a",
                "var2": "b",
            },
            "var1": "c",
            "var2": "d",
        }

    def test_simple_model(self):
        obj1 = SimpleModel(x="a", y="b")
        complex_object = ObjectWithSimpleModel(
            var1="c", var2="d", simple_object_model=obj1
        )
        dump = complex_object.model_dump()
        assert dump == {
            "cls": "ObjectWithSimpleModel",
            "simple_object_model": {"x": "a", "y": "b"},
            "var1": "c",
            "var2": "d",
        }

    def test_simple_class(self):
        obj1 = SimpleClass(x="a", y="b")
        complex_object = ObjectWithSimpleClass(
            var1="c", var2="d", simple_object_class=obj1
        )
        dump = complex_object.model_dump()
        assert dump == {
            "var1": "c",
            "var2": "d",
            "simple_object_class": obj1,
            "cls": "ObjectWithSimpleClass",
        }

    def test_simple_class_with_fallback(self):
        obj1 = SimpleClass(x="a", y="b")
        complex_object = ObjectWithSimpleClass(
            var1="c", var2="d", simple_object_class=obj1
        )
        dump = complex_object.model_dump(fallback=lambda obj: obj.serialize())
        assert dump == {
            "var1": "c",
            "var2": "d",
            "simple_object_class": {"x": "a", "y": "b"},
            "cls": "ObjectWithSimpleClass",
        }
