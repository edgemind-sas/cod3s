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


class TestFromDictDoesNotConsumeItsInput:
    """A declaration held in data is built more than once.

    ``from_dict`` used to write through the mapping it was given: every nested
    value was reassigned in place and ``cls`` was popped off the caller's own
    dict. A knowledge base built twice, a study sweeping a parameter or an
    importer replaying an export therefore got one successful build and then a
    failure naming a key still visible in the source it wrote.
    """

    def test_the_mapping_is_unchanged(self):
        specs = {"cls": "SimpleObject", "var1": "a", "var2": "b"}

        core.ObjCOD3S.from_dict(specs)

        assert specs == {"cls": "SimpleObject", "var1": "a", "var2": "b"}

    def test_the_same_mapping_builds_twice(self):
        specs = {"cls": "SimpleObject", "var1": "a", "var2": "b"}

        first = core.ObjCOD3S.from_dict(specs)
        second = core.ObjCOD3S.from_dict(specs)

        assert first.var1 == second.var1 == "a"
        assert first is not second

    def test_a_nested_declaration_is_unchanged_too(self):
        """The recursion reassigned every nested value in place as well."""
        specs = {
            "cls": "ObjectWithList",
            "var1": "e",
            "simple_object_list": [{"cls": "SimpleObject", "var1": "a"}],
        }
        expected = {
            "cls": "ObjectWithList",
            "var1": "e",
            "simple_object_list": [{"cls": "SimpleObject", "var1": "a"}],
        }

        built = core.ObjCOD3S.from_dict(specs)

        assert specs == expected
        assert built.simple_object_list[0].var1 == "a"

    def test_a_mapping_without_cls_is_returned_as_data(self):
        """No ``cls`` means nothing to build: the values are converted, and the
        result is a NEW mapping rather than the caller's one written through."""
        inner = {"cls": "SimpleObject", "var1": "a"}
        specs = {"plain": 1, "built": inner}

        result = core.ObjCOD3S.from_dict(specs)

        assert result is not specs
        assert result["plain"] == 1
        assert isinstance(result["built"], SimpleObject)
        assert specs == {"plain": 1, "built": {"cls": "SimpleObject", "var1": "a"}}

    def test_leaves_are_shared_not_copied(self):
        """A declaration may hold an object that must not be duplicated.

        In the PyCATSHOO case it cannot be: an occurrence law carries the
        engine variable its rate lives in, and deep-copying that raises
        ``Pickling of "Pycatshoo.IVariable" instances is not enabled``.
        """
        leaf = SimpleClass(x="a", y="b")
        specs = {"cls": "ObjectWithSimpleClass", "simple_object_class": leaf}

        built = core.ObjCOD3S.from_dict(specs)

        assert built.simple_object_class is leaf
