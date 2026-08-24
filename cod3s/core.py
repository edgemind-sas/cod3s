import pydantic
import yaml

from .utils import update_dict_deep


def terminate_session():
    try:
        import Pycatshoo

        Pycatshoo.CSystem.terminate()
    except ImportError:
        pass


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

    @classmethod
    def from_dict(basecls, obj):
        """Build an object from a declaration, WITHOUT consuming it.

        The containers are rebuilt rather than written through, so the mapping
        the caller passed is still the mapping the caller passed once this
        returns. It used to be emptied: every nested value was reassigned in
        place and ``cls`` was popped off the caller's own dict, so a
        declaration held in data survived exactly one use.

        That is the regime of anything that keeps its declarations rather than
        writing them inline -- a knowledge base built twice, a study sweeping a
        parameter, an importer replaying a platform export. The symptom is
        remote from its cause: ``{"cls": "delay", "time": 14}`` comes back
        ``{"time": 14}`` and the SECOND build fails with a missing ``cls``,
        naming a key the caller can still see in the source it wrote.

        Leaves are shared, not copied, and that is deliberate rather than
        expedient. A declaration legitimately holds objects that must not be
        duplicated and, in the PyCATSHOO case, cannot be: an occurrence law may
        carry the ``IVariable`` its rate lives in, so that an indicator can
        reference it by name, and ``copy.deepcopy`` on that raises ``Pickling
        of "Pycatshoo.IVariable" instances is not enabled``.
        """
        if isinstance(obj, dict):
            specs = {key: basecls.from_dict(value) for key, value in obj.items()}

            if "cls" in specs:
                cls_sub_dict = {cls.__name__: cls for cls in ObjCOD3S.get_subclasses()}
                cls_sub_dict[basecls.__name__] = basecls

                clsname = specs.pop("cls")
                if isinstance(clsname, type):
                    clsname = clsname.__name__
                cls = cls_sub_dict.get(clsname)

                if cls is None:
                    raise ValueError(
                        f"{clsname} is not a subclass of {ObjCOD3S.__name__}"
                    )

                return cls(**specs)

            return specs

        if isinstance(obj, list):
            return [basecls.from_dict(value) for value in obj]

        return obj

    def update(self, **new_data):
        if len(new_data) > 0:
            for field, value in new_data.items():
                if field != "cls":
                    setattr(self, field, value)

    def model_dump(self, **kwrds):
        """
        Sérialise le modèle en préservant les types pour ajouter 'cls' aux objets COD3S.
        """

        def add_cls_rec(value, dump):
            if isinstance(value, ObjCOD3S):
                dump["cls"] = value.__class__.__name__
                # Itérer sur les champs définis du modèle
            if isinstance(value, pydantic.BaseModel):
                for field_name in type(value).model_fields:
                    if field_name in dump:
                        field_value = getattr(value, field_name, None)
                        add_cls_rec(field_value, dump[field_name])
            elif isinstance(value, list):
                for i in range(len(dump)):
                    add_cls_rec(value[i], dump[i])
            elif isinstance(value, dict):
                for k in dump.keys():
                    add_cls_rec(value[k], dump[k])

        result = super().model_dump(**kwrds)
        add_cls_rec(self, result)

        return result

    # def model_dump(self, **kwrds):
    #     """Dumps the model to a dictionary with class information.

    #     This method extends pydantic's model_dump by:
    #     1. Adding a 'cls' key with the class name
    #     2. Recursively converting nested Pydantic models and collections

    #     Note: serialize_as_any=True is used only on the first super().model_dump() call
    #     to handle potential type conflicts at the root level. Nested calls don't need
    #     this flag as they're already properly typed through the parent's serialization.

    #     Args:
    #         **kwrds: Additional keyword arguments passed to pydantic's model_dump

    #     Returns:
    #         dict: A dictionary representation of the model with class information
    #     """
    #     base_dict = super().model_dump(serialize_as_any=True, **kwrds)
    #     # base_dict = self.__dict__

    #     result = {"cls": self.__class__.__name__}

    #     # __import__("ipdb").set_trace()
    #     #        for key, value in base_dict.items():
    #     for key, value in base_dict.items():
    #         if hasattr(value, "model_dump") and callable(value.model_dump):
    #             result[key] = value.model_dump(**kwrds)
    #         elif isinstance(value, list):
    #             result[key] = [
    #                 (
    #                     item.model_dump(**kwrds)
    #                     if hasattr(item, "model_dump") and callable(item.model_dump)
    #                     else item
    #                 )
    #                 for item in value
    #             ]
    #         elif isinstance(value, dict):
    #             result[key] = {
    #                 k: (
    #                     v.model_dump(**kwrds)
    #                     if hasattr(v, "model_dump") and callable(v.model_dump)
    #                     else v
    #                 )
    #                 for k, v in value.items()
    #             }
    #         else:
    #             result[key] = value

    #     return result
