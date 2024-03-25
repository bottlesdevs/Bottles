import yaml as _yaml

from bottles.backend.models.config import BottleConfig

try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeLoader, SafeDumper

YAMLError = _yaml.YAMLError
SafeDumper.add_representer(BottleConfig, BottleConfig.yaml_serialize_handler)


def dump(data, stream=None, **kwargs):
    """
    Serialize a Python object into a YAML stream.
    If stream is None, return the produced string instead.
    Note: This function is a replacement for PyYAML's dump() function,
          using the CDumper class instead of the default Dumper, to achieve
          the best performance.
    """
    return _yaml.dump(data, stream, Dumper=SafeDumper, **kwargs)


# noinspection PyPep8Naming
def load(stream, Loader=SafeLoader):
    """
    Load a YAML stream.
    Note: This function is a replacement for PyYAML's safe_load() function,
          using the CLoader class instead of the default Loader, to achieve
          the best performance.
    """
    return _yaml.load(stream, Loader=Loader)
