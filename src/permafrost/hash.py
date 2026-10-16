from typing import Any, TYPE_CHECKING



def get_hash_value(value: Any) -> bytes:
    """Get the hash for any given value.

    This function is used to get the hash for any given value.
    It will return a bytes object that can be used to compare the value.
    """
    if hasattr(value, "get_hash"):
        return value.get_hash().encode()

    return str(value).encode()

def get_field_signature(cls, value: Any) -> list[bytes]:
    """Get the signature of the field value.

    This function is used to get the signature of the field value.
    It will return a list of bytes that can be used to compare the field value.
    """
    hashes: list[bytes] = []
    if isinstance(value, list):
        for item in sorted(value):
            hashes.append(get_hash_value(item))
    elif isinstance(value, dict):
        for key, content in frozenset[tuple[Any, Any]](sorted(value.items())):
            hashes.append(get_hash_value(key))
            hashes.append(get_hash_value(content))
    else:
        hashes.append(get_hash_value(value))

    return sorted(hashes)