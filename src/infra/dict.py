from typing import Any, Optional


def get_nested(json: dict | Any, keypath: list[str]) -> Optional[Any]:
    if not isinstance(json, dict):
        return None
    key = keypath.pop(0)
    value = json.get(key)
    if len(keypath) == 0:
        return value
    else:
        # we need to go deeper
        return get_nested(value, keypath)
