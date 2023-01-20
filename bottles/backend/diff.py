import os
import hashlib


class Diff:
    """
    This class is no more used by the application, it's just a
    reference for future implementations.
    """
    __ignored = [
        "dosdevices",
        "users",
        "bottle.yml",
        "storage"
    ]

    @staticmethod
    def hashify(path: str) -> dict:
        """
        Hash (SHA-1) all files in a directory and return
        them in a dictionary. Here we use SHA-1 instead of
        better ones like SHA-256 because we only need to
        compare the file hashes, it's faster, and it's
        not a security risk.
        """
        _files = {}

        if path[-1] != os.sep:
            '''
            Be sure to add a trailing slash at the end of the path to
            prevent the correct path name in the result.
            '''
            path += os.sep

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in Diff.__ignored]
            for f in files:
                if f in Diff.__ignored:
                    continue
                with open(os.path.join(root, f), "rb") as fr:
                    _hash = hashlib.sha1(fr.read()).hexdigest()

                _key = os.path.join(root, f)
                _key = _key.replace(path, "")
                _files[_key] = _hash

        return _files

    @staticmethod
    def file_hashify(path: str) -> str:
        """Hash (SHA-1) a file and return it."""
        with open(path, "rb") as fr:
            _hash = hashlib.sha1(fr.read()).hexdigest()

        return _hash

    @staticmethod
    def compare(parent: dict, child: dict) -> dict:
        """
        Compare two hashes dictionaries and return the
        differences (added, removed, changed).
        """

        added = []
        changed = []
        removed = [f for f in parent if f not in child]

        for f in child:
            if f not in parent:
                added.append(f)
            elif parent[f] != child[f]:
                changed.append(f)

        return {
            "added": added,
            "removed": removed,
            "changed": changed
        }
