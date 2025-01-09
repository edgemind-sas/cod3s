import pydantic
import copy
import yaml
from .utils import update_dict_deep


class ObjCOD3S(pydantic.BaseModel):
    @classmethod
    def get_subclasses(cls, recursive=True):
        """Enumerates all subclasses of a given class.

        # Arguments
        cls: class. The class to enumerate subclasses for.
        recursive: bool (default: True). If True, recursively finds all sub-classes.

        # Return value
        A list of subclasses of `cls`.
        """
        sub = cls.__subclasses__()
        if recursive:
            for cls in sub:
                sub.extend(cls.get_subclasses(recursive))
        return sub

    @classmethod
    def from_yaml(
        cls,
        file_path: str,
        add_cls=True,
        attr_header=None,
        cls_attr=None,
        data={},
    ):
        with open(file_path, "r", encoding="utf-8") as yaml_file:
            obj_dict = yaml.load(yaml_file, Loader=yaml.SafeLoader)
            if attr_header:
                obj_dict = obj_dict[attr_header]
            if add_cls:
                obj_dict.setdefault("cls", cls.__name__)
            if cls_attr:
                obj_dict["cls"] = cls_attr

            update_dict_deep(obj_dict, data)

            return cls.from_dict(obj_dict)

    # @classmethod
    # def get_clsname(basecls, **specs):
    #     return specs.pop("cls")

    # @classmethod
    # def from_dict(basecls, **specs):

    #     cls_sub_dict = {
    #         cls.__name__: cls for cls in basecls.get_subclasses()}

    #     clsname = basecls.get_clsname(**specs)
    #     cls = cls_sub_dict.get(clsname)

    #     if cls is None:
    #         raise ValueError(
    #             f"{clsname} is not a subclass of {basecls.__name__}")

    #     #ipdb.set_trace()
    #     return cls(**specs)

    @classmethod
    def from_dict(basecls, obj):
        # ipdb.set_trace()
        if isinstance(obj, dict):
            for key, value in obj.items():
                obj[key] = basecls.from_dict(value)

            if "cls" in obj:
                cls_sub_dict = {cls.__name__: cls for cls in ObjCOD3S.get_subclasses()}
                cls_sub_dict[basecls.__name__] = basecls

                clsname = obj.pop("cls")
                cls = cls_sub_dict.get(clsname)

                if cls is None:
                    raise ValueError(
                        f"{clsname} is not a subclass of {ObjCOD3S.__name__}"
                    )

                return cls(**obj)

        elif isinstance(obj, list):
            for index, value in enumerate(obj):
                obj[index] = basecls.from_dict(value)

        return obj

    def update(self, **new_data):
        if len(new_data) > 0:
            for field, value in new_data.items():
                if field != "cls":
                    setattr(self, field, value)

    def model_dump(self, **kwrds):
        """Dumps the model to a dictionary with class information.

        This method extends pydantic's model_dump by:
        1. Adding a 'cls' key with the class name
        2. Recursively converting nested Pydantic models and collections

        Note: serialize_as_any=True is used only on the first super().model_dump() call
        to handle potential type conflicts at the root level. Nested calls don't need
        this flag as they're already properly typed through the parent's serialization.

        Args:
            **kwrds: Additional keyword arguments passed to pydantic's model_dump

        Returns:
            dict: A dictionary representation of the model with class information
        """
        base_dict = super().model_dump(serialize_as_any=True, **kwrds)
        result = {"cls": self.__class__.__name__}

        for key, value in base_dict.items():
            if hasattr(value, "model_dump") and callable(value.model_dump):
                result[key] = value.model_dump(**kwrds)
            elif isinstance(value, list):
                result[key] = [
                    (
                        item.model_dump(**kwrds)
                        if hasattr(item, "model_dump") and callable(item.model_dump)
                        else item
                    )
                    for item in value
                ]
            elif isinstance(value, dict):
                result[key] = {
                    k: (
                        v.model_dump(**kwrds)
                        if hasattr(v, "model_dump") and callable(v.model_dump)
                        else v
                    )
                    for k, v in value.items()
                }
            else:
                result[key] = value

        return result
