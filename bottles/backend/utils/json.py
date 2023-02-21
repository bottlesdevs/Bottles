"""This should be a drop-in replacement for the json module built in CPython"""
import json as _json
from typing import Optional, IO, Any, Type

from bottles.backend.models.config import DictCompatMixIn


class ExtJSONEncoder(_json.JSONEncoder):
    def default(self, o):
        if isinstance(o, DictCompatMixIn):
            return o.json_serialize_handler(o)
        return super().default(o)


def load(fp: IO[str | bytes]) -> Any:
    return _json.load(fp)


def loads(s: str | bytes) -> Any:
    """Deserialize s (a str, bytes or bytearray instance containing a JSON document) to a Python object."""
    return _json.loads(s)


def dump(
        obj: Any, fp: IO[str], *,
        indent: Optional[str | int] = None, cls: Optional[Type[_json.JSONEncoder]] = None
) -> None:
    """
    Serialize obj as a JSON formatted stream to fp (a .write()-supporting file-like object).

    :param obj: the object you want to serialize
    :param fp: the file-like object you want to write
    :param indent: `None` for compact output, `0` for newline only, non-negative integer for indent level
    :param cls: Custom JsonEncoder subclass, use ExtJsonEncoder if not provided
    """
    if cls is None:  # replace default JsonEncoder
        cls = ExtJSONEncoder
    return _json.dump(obj, fp, indent=indent, cls=cls)


def dumps(obj: Any, *, indent: Optional[str | int] = None, cls: Optional[Type[_json.JSONEncoder]] = None) -> str:
    """
    Serialize obj to a JSON formatted str.

    :param obj: the object you want to serialize
    :param indent: `None` for compact output, `0` for newline only, non-negative integer for indent level
    :param cls: Custom JsonEncoder subclass, use ExtJsonEncoder if not provided
    :return: serialized result
    """
    if cls is None:  # replace default JsonEncoder
        cls = ExtJSONEncoder
    return _json.dumps(obj, indent=indent, cls=cls)
