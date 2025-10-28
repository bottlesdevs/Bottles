"""Pytest bootstrap for repository-local imports.

Ensures the repository root is on sys.path so `import bottles` works when
running `pytest` without installing the package.
"""

import os
import sys


def _add_repo_root_to_syspath() -> None:
    this_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(this_dir, os.pardir))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


_add_repo_root_to_syspath()


