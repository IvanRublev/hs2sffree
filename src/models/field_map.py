from dataclasses import dataclass
from typing import Callable, Optional, Any


@dataclass(frozen=True)
class FieldMap:
    """
    FieldMap

    Represents the mapping configuration for a single HubSpot field and an optional transformation
    applied to its value.

    Attributes:
        src_field (str):
            Name of the field in the HubSpot record to read.
        required (bool):
            Whether the field value is required in the Salesforce.
        transform_fun (Optional[Callable[[Value, Context], tuple[Any, Context]]]):
            Optional function invoked to transform the source value.
            The callable receives two arguments:
                - the input value from src_field of any type.
                - the current Context (a dict-like mapping).
            It can return:
                - a transformed_value of any type.
                - a tuple of (transformed_value, context), the returned Context
                  to be provided to consequent transform function calls.
    """

    Context = dict
    TransformFun = Callable[[Any, Context], tuple[Any, Context]]
    TransformFunNoContextUpdate = Callable[[Any, Context], Any]

    src_field: str
    transform_fun: Optional[TransformFun | TransformFunNoContextUpdate] = None
    required: bool = False
