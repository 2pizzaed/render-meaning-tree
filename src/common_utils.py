from enum import Enum
from typing import Any, Self, get_type_hints, get_origin, get_args, Union
from types import UnionType
from dataclasses import fields, is_dataclass, MISSING
import inspect


class DictLikeDataclass:
    """ Mixins for dataclasses to be used as dict.
    Also, automatic construction from dict using types declared for property annotations/type hints (mandatory or optional as typing.Optional) is provided.
    """
    def __getitem__(self, key):
        return getattr(self, key)
    
    def __setitem__(self, key, value):
        object.__setattr__(self, key, value)
    
    def __delitem__(self, key):
        object.__delattr__(self, key)
    
    def get(self, key, default=None):
        return getattr(self, key, default)
    
    def __contains__(self, key):
        return hasattr(self, key)

    @classmethod
    def make(cls, data: dict):
        """ Try to create instance from dict, creating children recursively using types declared for property annotations/type hints (mandatory or optional as typing.Optional).
        Behaviour:
        - if unknown keys are present in data, raise ValueError as no such attributes are expected
        - if attr is mandatory, raise ValueError if not present in data
        - if attr is optional, ignore if not present in data
        - if attr is list, create list of children recursively using types declared for property annotations/type hints (mandatory or optional as typing.Optional)
        - if attr is dict, create dict of children recursively using types declared for property annotations/type hints (mandatory or optional as typing.Optional)
        - if attr is Enum, use SelfValidatedEnum.lookup to create instance
        """
        # Get type hints for this class
        type_hints = cls._get_type_hints()
        
        # Check for unknown keys
        unknown_keys = set(data.keys()) - set(type_hints.keys())
        if unknown_keys:
            raise ValueError(f"Error making an instance of {cls.__name__}: Unknown keys in data: {unknown_keys}. Expected keys: {list(type_hints.keys())}")
        
        # Process each field
        processed_data = {}
        for field_name, (field_type, is_optional) in type_hints.items():
            if field_name in data:
                value = data[field_name]
                processed_data[field_name] = cls._process_value(value, field_type, is_optional)
            elif not is_optional:
                raise ValueError(f"Mandatory field '{field_name}' is missing from data")
            # Optional fields are ignored if not present
        
        return cls(**processed_data)

    @classmethod
    def _process_value(cls, value: Any, field_type: type, is_optional: bool) -> Any:
        """Process a single value according to its type annotation"""
        # Handle None values for optional fields
        if value is None and is_optional:
            return None
        
        # Handle Union types (including Optional)
        if get_origin(field_type) is Union or get_origin(field_type) is UnionType:
        # if get_origin(field_type).__name__ == 'UnionType':
            # For Optional[T], we get Union[T, None]
            args = get_args(field_type)
            if len(args) == 2 and type(None) in args:
                # This is Optional[T], get the actual type T
                actual_type = args[0] if args[1] is type(None) else args[1]
                return cls._process_value(value, actual_type, False)
            else:
                # This is a regular Union, try each type
                for arg_type in args:
                    try:
                        return cls._process_value(value, arg_type, False)
                    except (ValueError, TypeError):
                        continue
                raise ValueError(f"Cannot convert {value} to any of {args}")
        
        # Handle List types
        if get_origin(field_type) is list:
            if not isinstance(value, list):
                raise ValueError(f"Expected list for field, got {type(value)}")
            
            element_type = get_args(field_type)[0] if get_args(field_type) else Any
            return [cls._process_value(item, element_type, False) for item in value]
        
        # Handle Dict types
        if get_origin(field_type) is dict:
            if not isinstance(value, dict):
                raise ValueError(f"Expected dict for field, got {type(value)}")
            
            key_type, value_type = get_args(field_type) if get_args(field_type) else (Any, Any)
            return {cls._process_value(k, key_type, False): cls._process_value(v, value_type, False) 
                   for k, v in value.items()}
        
        # Handle Enum types
        if inspect.isclass(field_type) and issubclass(field_type, SelfValidatedEnum):
            return field_type.lookup(value)
        
        # Handle dataclass types
        if inspect.isclass(field_type) and is_dataclass(field_type):
            if not isinstance(value, dict):
                raise ValueError(f"Expected dict for dataclass field, got {type(value)}")
            
            # Create instance of the dataclass
            return field_type.make(value)
        
        # Handle primitive types
        if field_type in (int, float, str, bool):
            try:
                return field_type(value)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Cannot convert {value} to {field_type.__name__}: {e}")
        
        # Handle Any type
        if field_type is Any:
            return value
        
        # For other types, try direct conversion
        try:
            return field_type(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Cannot convert {value} to {field_type}: {e}")

    @classmethod
    def _get_type_hints(cls) -> dict[str, tuple[type, bool]]:
        """ Return dict of property names, types and `optional` flag """
        type_hints = {}
        
        # Get type hints from the class
        hints = get_type_hints(cls)
        
        # Get field information from dataclass
        if is_dataclass(cls):
            dataclass_fields = fields(cls)
            for field in dataclass_fields:
                field_name = field.name
                field_type = hints.get(field_name, Any)
                
                # Check if field is optional (has default value, default_factory, or is Optional type)
                is_optional = (field.default is not MISSING or 
                              field.default_factory is not MISSING)
                
                # Also check if it's explicitly Optional type
                if get_origin(field_type) is Union:
                    args = get_args(field_type)
                    if len(args) == 2 and type(None) in args:
                        is_optional = True
                
                type_hints[field_name] = (field_type, is_optional)
        else:
            # For non-dataclass classes, just use type hints
            for field_name, field_type in hints.items():
                is_optional = get_origin(field_type) is Union and type(None) in get_args(field_type)
                type_hints[field_name] = (field_type, is_optional)
        
        return type_hints

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
