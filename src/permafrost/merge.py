
from .models import Permafrost

def merge(left: Permafrost,  right: Permafrost) -> Permafrost:
    """Merge the current object with the new value from the new one if they are defined.

    Currently this method works for the following type of fields
        int, str, bool, float: If present the value from Other is overwriting the local value
        list[BaseSchemaModel]: The list will be merge if all elements in the list have a _sorting_id and if it's unique.
        Permafrost: the value will be merged using update()
    """

    field_to_update = {}

    for field_name in right.__class__.model_fields.keys():
        field_other = getattr(right, field_name)
        if not hasattr(left, field_name):
            try:
                field_to_update[field_name] = field_other
            except ValueError:
                # handles the case where self and other are different types and other has fields that self does not
                pass
            continue


        field_local = getattr(left, field_name)
        if field_other is None or field_local == field_other:
            continue

        if field_local is None or isinstance(field_other, int | str | bool | float):
            field_to_update[field_name] = field_other
            continue

        if isinstance(field_local, list) and isinstance(field_other, list):
            new_field = left._get_updated_list_value(
                field_name=field_name, attr_local=field_local, attr_other=field_other
            )
            field_to_update[field_name] = new_field
            continue

        if isinstance(field_local, Permafrost) and isinstance(field_other, Permafrost):
            updated_field = merge(left=field_local, right=field_other)
            field_to_update[field_name] = updated_field
            continue

    return left.model_copy(update=field_to_update)
