import yaml as _yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
    _c = True
except ImportError:
    _c = False


def dump(data, stream=None, **kwargs):
    """
    Serialize a Python object into a YAML stream.
    If stream is None, return the produced string instead.
    Note: This function is a replacement for PyYAML's dump() function, using
          the CDumper class instead of the default Dumper, to achieve best 
          performance.
    """
    if _c:
        return _yaml.dump(data, stream, Dumper=Dumper, **kwargs)
    return _yaml.dump(data, stream, **kwargs)


def load(stream, Loader=Loader):
    """
    Load a YAML stream.
    Note: This function is a replacement for PyYAML's safe_load() function, 
          using the CLoader class instead of the default Loader, to achieve 
          best performance.
    """
    if _c:
        return _yaml.load(stream, Loader=Loader)
    return _yaml.safe_load(stream)
