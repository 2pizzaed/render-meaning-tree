from enum import Enum
from typing import Any, Self


class DictLikeDataclass:
    """ Mixins for dataclasses to be used as dict.
    Also, automatic construction from dict using types declared for property annotations/type hints (mandatory or optional as typing.Optional) is provided (TODO).
    """
    __getitem__ = getattr
    __setitem__ = object.__setattr__
    __delitem__ = object.__delattr__
    get = getattr
    __contains__ = hasattr

    def make(self, data: dict):
        """ Try to create instance from dict, creating children recursively using types declared for property annotations/type hints (mandatory or optional as typing.Optional).
        Behaviour:
        - if unknown keys are present in data, raise ValueError as no such attributes are expected
        - if attr is mandatory, raise ValueError if not present in data
        - if attr is optional, ignore if not present in data
        - if attr is list, create list of children recursively using types declared for property annotations/type hints (mandatory or optional as typing.Optional)
        - if attr is dict, create dict of children recursively using types declared for property annotations/type hints (mandatory or optional as typing.Optional)
        - if attr is Enum, use SelfValidatedEnum.lookup to create instance
        """
        # TODO: implement for all cases of attr definition
        for key, value in data.items():
            if isinstance(value, dict):
                data[key] = self.__class__.make(value)
            elif isinstance(value, list):
                data[key] = [self.__class__.make(v) if isinstance(v, dict) else v for v in value]

        return self.__class__(**data)

    @classmethod
    def _get_type_hints(cls) -> dict[str, type, bool]:
        """ Return dict of property names, types and optional flag """
        return ... # TODO

class SelfValidatedEnum(Enum):
    @classmethod
    def lookup(cls, value, raise_on_error: bool = True) -> Self | None:
        try:
            return cls(value)  # lookup instance by value
        except ValueError:
            if raise_on_error:
                raise ValueError(f"Invalid value for enum {cls.__name__}: {value}, expected one of: {list(cls.__members__.values())}.")
            return None

    def __eq__(self, other: Self | Any):
        """ Allow comparison with both enum instance and plain value """
        if isinstance(other, SelfValidatedEnum):
            return self.value == other.value
        return self.value == other
