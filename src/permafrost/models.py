
from __future__ import annotations

import hashlib
from typing import Any
from enum import Enum
from pydantic import BaseModel, ConfigDict, computed_field

from typing_extensions import Self


from .hash import get_field_signature

class PermafrostState(Enum, str):
    PRESENT = "present"
    ABSENT = "absent"


def is_list_composed_of_permafrost(items: list[Any]) -> bool:
    return all(isinstance(item, Permafrost) for item in items)


class Permafrost(BaseModel):
    model_config = ConfigDict(extra="forbid", forzen=True)

    # state: PermafrostState = PermafrostState.PRESENT

    _exclude_from_hash: list[str] = []
    _sort_by: list[str] = []
    _model_hash: str | None = None

    def __hash__(self) -> int:
        return hash(self.get_hash())

    def get_hash(self) -> str:
        if self._model_hash is None:
            self._model_hash = self._compute_model_hash()
        return self._model_hash

    def _compute_model_hash(self) -> str:
        """Generate a hash for the object.

        Calculating a hash can be very complicated if the data that we are storing is dynamic
        In order for this function to work, it's recommended to exclude all objects or list of objects with _exclude_from_hash
        List of hashable elements are fine and they will be converted automatically to Tuple.
        """

        values = []
        md5hash = hashlib.md5(usedforsecurity=False)
        for field_name in sorted(self.__class__.model_fields.keys()):
            if field_name.startswith("_") or field_name in self._exclude_from_hash:
                continue

            value = getattr(self, field_name)
            signatures = get_field_signature(value)
            for item in signatures:
                values.append(item)
                md5hash.update(item)

        return md5hash.hexdigest()


    # @property
    # def _sorting_id(self) -> tuple[Any]:
    #     if not self._sort_by:
    #         return (self.get_hash(),)

    #     return tuple[Any, ...](getattr(self, key) for key in self._sort_by if hasattr(self, key))

    # def _sorting_keys(self, other: Permafrost) -> tuple[list[Any], list[Any]]:
    #     """Retrieve the values of the attributes listed in the _sort_key list, for both objects."""
    #     if not self._sort_by:
    #         raise TypeError(f"Sorting not supported for instance of {self.__class__.__name__}")

    #     if not hasattr(other, "_sort_by") and not other._sort_by:
    #         raise TypeError(
    #             f"Sorting not supported between instance of {other.__class__.__name__} and {self.__class__.__name__}"
    #         )

    #     self_sort_keys: list[Any] = [getattr(self, key) for key in self._sort_by if hasattr(self, key)]
    #     other_sort_keys: list[Any] = [getattr(other, key) for key in other._sort_by if hasattr(other, key)]

    #     return self_sort_keys, other_sort_keys

    def __eq__(self, other: Self) -> bool:
        return self.get_hash() == other.get_hash()

    # def __lt__(self, other: Self) -> bool:
    #     self_sort_keys, other_sort_keys = self._sorting_keys(other)
    #     return tuple[Any, ...](self_sort_keys) < tuple[Any, ...](other_sort_keys)

    # def __le__(self, other: Self) -> bool:
    #     self_sort_keys, other_sort_keys = self._sorting_keys(other)
    #     return tuple[Any, ...](self_sort_keys) <= tuple[Any, ...](other_sort_keys)

    # def __gt__(self, other: Self) -> bool:
    #     self_sort_keys, other_sort_keys = self._sorting_keys(other)
    #     return tuple[Any, ...](self_sort_keys) > tuple[Any, ...](other_sort_keys)

    # def __ge__(self, other: Self) -> bool:
    #     self_sort_keys, other_sort_keys = self._sorting_keys(other)
    #     return tuple[Any, ...](self_sort_keys) >= tuple[Any, ...](other_sort_keys)

    def duplicate(self) -> Self:
        """Duplicate the current object by doing a deep copy of everything and recreating a new object."""
        return self.model_copy(deep=True)



    # @staticmethod
    # def _organize_sub_items(items: list[Permafrost], shared_ids: set[str]) -> dict[tuple[Any], Permafrost]:
    #     """Convert a list of Permafrost into a dict with the sorting_id as the key, or the id if it was provided as part of the shared_ids"""
    #     sub_items = {}
    #     for item in items:
    #         if item.id and item.id in shared_ids:
    #             sub_items[item.id,] = item
    #             continue
    #         sub_items[item._sorting_id] = item

    #     return sub_items

    @staticmethod
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
                if key in other_only_ids and value.state != PermafrostState.ABSENT
            ]
        )

        for item_id in shared_ids:
            other_item = other_sub_items[item_id]
            local_item = local_sub_items[item_id]
            if other_item.state == PermafrostState.ABSENT:
                continue
            new_list.append(local_item.update(other_item))

        return new_list


    def _get_updated_list_value(self, field_name: str, attr_local: list[Any], attr_other: list[Any]) -> list[Any]:
        if self._is_list_composed_of_stone_model(attr_local) and self._is_list_composed_of_stone_model(attr_other):
            return self.update_list_model(field_name=field_name, attr_local=attr_local, attr_other=attr_other)

        return attr_other

    def _get_field_names_for_diff(self) -> list[str]:
        return list[str](self.__class__.model_fields.keys())

    # def diff(self, other: Self) -> HashableModelDiff:
    #     in_both, local_only, other_only = compare_lists(
    #         list1=self._get_field_names_for_diff(), list2=other._get_field_names_for_diff()
    #     )
    #     diff_result = HashableModelDiff(added=dict.fromkeys(local_only), removed=dict.fromkeys(other_only))

    #     for field_name in in_both:
    #         if field_name.startswith("_") or field_name in self._exclude_from_hash:
    #             continue

    #         local_value = getattr(self, field_name)
    #         other_value = getattr(other, field_name)
    #         local_signatures = self._get_signature_field(local_value)
    #         other_signatures = other._get_signature_field(other_value)

    #         if local_signatures != other_signatures:
    #             if isinstance(local_value, HashableModel) and isinstance(other_value, HashableModel):
    #                 diff_result.changed[field_name] = local_value.diff(other=other_value)
    #             else:
    #                 diff_result.changed[field_name] = None

    #     return diff_result