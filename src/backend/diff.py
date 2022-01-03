import os
import hashlib


class Diff:
    __ignored = [
        "dosdevices",
        "users",
        "bottle.yml",
        "layer.yml",
    ]

    @staticmethod
    def hashify(path: str) -> dict:
        '''
        Hash (SHA-1) all files in a directory and return
        them in a dictionary. Here we use SHA-1 instead of
        better ones like SHA-256 because we only need to
        compare the file hashes, it's faster and it's
        not a security risk.
        '''
        _files = {}

        if path[-1] != os.sep:
            '''
            Be sure to add a trailing slash at the end of the path to
            prevent the correct path name in the result.
            '''
            path += os.sep

        for root, dirs, files in os.walk(path):
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
    def compare(parent: dict, child: dict) -> dict:
        '''
        Compare two hashes dictionaries and return the
        differences (added, removed, changed).
        '''
        
        added = []
        removed = []
        changed = []
        
        for f in child:
            if f not in parent:
                added.append(f)
            elif parent[f] != child[f]:
                changed.append(f)
        
        for f in parent:
            if f not in child:
                removed.append(f)
        
        return {
            "added": added, 
            "removed": removed, 
            "changed": changed
        }
