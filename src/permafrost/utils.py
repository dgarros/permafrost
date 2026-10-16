from itertools import groupby

from typing import Any

def duplicates(input_list: list) -> list:
    """Identify and return all the duplicates in a list."""

    dups = []

    clean_input_list = [item for item in input_list or [] if item is not None]
    for x, y in groupby(sorted(clean_input_list)):
        #  list(y) returns all the occurences of item x
        if len(list(y)) > 1:
            dups.append(x)

    return dups


def intersection(list1: list[Any], list2: list[Any]) -> list:
    """Calculate the intersection between 2 lists."""
    return list[Any](set[Any](list1) & set[Any](list2))