

from typing import Any

from .utils import intersection, duplicates

def update_list_model(
    field_name: str, attr_local: list[Permafrost], attr_other: list[Permafrost]
) -> list[Any]:
    """
    Merging the list is not easy,
    we need to create a unique id based on the sorting keys
    and if we have 2 sub items with the same key we can merge them recursively with update()
    """

    # Identify all nodes that are sharing a real IDs
    local_sub_real_ids = {item.id for item in attr_local if item.id}
    other_sub_real_ids = {item.id for item in attr_other if item.id}
    shared_real_ids = local_sub_real_ids & other_sub_real_ids

    local_sub_items = Permafrost._organize_sub_items(items=attr_local, shared_ids=shared_real_ids)
    other_sub_items = Permafrost._organize_sub_items(items=attr_other, shared_ids=shared_real_ids)

    new_list = []

    if len(local_sub_items) != len(attr_local) or len(other_sub_items) != len(attr_other):
        raise ValueError(f"Unable to merge the list for {field_name}, not all items are supporting _sorting_id")

    if duplicates(list[tuple[Any]](local_sub_items.keys())) or duplicates(list(other_sub_items.keys())):
        raise ValueError(f"Unable to merge the list for {field_name}, some items have the same _sorting_id")

    shared_ids = intersection(list(local_sub_items.keys()), list(other_sub_items.keys()))
    local_only_ids = set(local_sub_items.keys()) - set(shared_ids)
    other_only_ids = set(other_sub_items.keys()) - set(shared_ids)

    new_list = [value for key, value in local_sub_items.items() if key in local_only_ids]
    new_list.extend(
        [
            value
            for key, value in other_sub_items.items()
            # if key in other_only_ids and value.state != PermafrostState.ABSENT
        ]
    )

    for item_id in shared_ids:
        other_item = other_sub_items[item_id]
        local_item = local_sub_items[item_id]
        # if other_item.state == PermafrostState.ABSENT:
        #     continue
        new_list.append(local_item.update(other_item))

    return new_list


def get_updated_list_value(self, field_name: str, attr_local: list[Any], attr_other: list[Any]) -> list[Any]:
    if self._is_list_composed_of_stone_model(attr_local) and self._is_list_composed_of_stone_model(attr_other):
        return self.update_list_model(field_name=field_name, attr_local=attr_local, attr_other=attr_other)

    return attr_other