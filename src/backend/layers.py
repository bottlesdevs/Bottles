# layers.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import uuid
import yaml
import shutil
from glob import glob
from typing import NewType

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.models.samples import Samples
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.globals import Paths
from bottles.backend.diff import Diff

logging = Logger()


class LayersStore:

    @staticmethod
    def list() -> list:
        """List all layers."""
        layers = os.listdir(Paths.layers)
        for f in layers:
            f = os.path.join(Paths.layers, f)
            if os.path.isdir(f):
                yield f

    @staticmethod
    def get(name: str = None, _uuid: str = None) -> dict:
        """Get layer by name or uuid and return as a dict."""
        if name:
            pattern = f"{Paths.layers}/@__{name}__*"
        elif _uuid:
            pattern = f"{Paths.layers}/@__*__{_uuid}"
        else:
            raise Exception("No layer name or uuid provided.")

        layer = False
        for f in glob(pattern):
            if os.path.isdir(f):
                layer = f
                break

        if layer:
            with open(f"{layer}/layer.yml", "r") as f:
                conf = yaml.safe_load(f)
                return conf

        return False

    @staticmethod
    def get_layer_by_name(name: str) -> dict:
        """Get layer by name and return as a dict."""
        return LayersStore.get(name=name)

    @staticmethod
    def get_layer_by_uuid(uuid: str) -> dict:
        """Get layer by uuid and return as a dict."""
        return LayersStore.get(_uuid=uuid)


class Layer:
    """
    (WIP) This feature is not yet implemented.
    ---
    Concept:
    - bottle = Bottle.new() | create a new bottle and return its config
    - layer = Layer.new("dotnet48") | create a new empty layer (@__dotnet48__uuid)
    - layer.mount_bottle(bottle) | link the bottle to the layer
    - Dependency.install(layer.config) | install dependency on layer
    - layer.sweep() | unlink bottle files from layer
        - sweep should also export registry diffs
    - layer.save() | create a index.yml file with stored files and hashes
    - layer = Layer.new("epic") | create a new empty layer (@__epic__uuid)
    - layer.mount_bottle(bottle) | link the bottle to the layer
    - layer.mount("dotnet48") | link dotnet48 layer files to the epic layer
    - Installer.run(layer.config) | launch epic installer on layer
    - layer.sweep() | unlink dependency and bottle layers files from layer
    - layer.save() | create an index.yml file with stored files and hashes
    - bottle.add_layer_entry(…) | add a new executable to bottle Layers

    Notes:
    - directories are not symlinked to avoid the new layer files to be created in the bottle directory
    - layers should be able to be mounted to other layers
    - layers should remembed other mounted layers, so that they can be unlinked when unmounting
    - layers need an index.yml file to store the files and hashes
    - layers paths need a uuid to avoid collisions, format: @__<name>__<uuid>
    - bottles should store layers as by entry point (programs/executables):
        - Layers:
            - uuid
                - name: <name>
                - exec_path: <exec_path> (C:\Program Files\Epic\Epic.exe)
                - exec_args: <exec_args> (--args)
                - exec_env:
                    - <name>: <value>
                - exec_cwd: <exec_cwd> (C:\Program Files\Epic)
                - parameters:
                    - <name>: <value> (dxvk: True)
    """
    __uuid: str = None
    __path: str = None
    __mounts: list = []
    __config: dict = {}
    runtime_conf: dict = {}

    def init(self, layer: dict):
        """Initialize a new layer from a dict."""
        self.__uuid = layer["UUID"]
        self.__path = layer["Path"]

        _conf = Samples.config.copy()
        _conf["Name"] = layer["Name"]
        _conf["Path"] = layer["Path"]

        self.runtime_conf = _conf
        self.__config = layer

        return self

    def new(self, name: str, runner: str = None):
        """
        Generate a new layer path based on the layer name
        and a random uuid. Also create a runtime config which
        is just a sample bottle config to be used by the
        manager to treat the layer as a bottle, plus the
        layer config.
        """
        logging.info(f"Creating a new layer for {name}…", )

        self.__uuid = str(uuid.uuid4())
        folder = f"@__{name}__{self.__uuid}"
        self.__path = f"{Paths.layers}/{folder}"

        _conf = Samples.config.copy()
        _conf["Name"] = f"@__{name}__{self.__uuid}"
        _conf["Path"] = f"@__{name}__{self.__uuid}"
        _conf["IsLayer"] = True  # will be used by Dependency/Installer managers to set the right path
        if runner is not None:
            _conf["Runner"] = runner
        os.makedirs(self.__path)

        self.runtime_conf = _conf
        self.__config = {
            "Name": name,
            "UUID": self.__uuid,
            "Path": _conf["Path"],
            "Tree": {},
        }

        return self

    def get_uuid(self) -> str:
        """Get the layer uuid."""
        return self.__uuid

    def __link_files(self, path, duplicate=False):
        for root, __, files in os.walk(path):
            if "dosdevices" in root:
                continue

            for f in files:
                if "layer.yml" in f or "bottle.yml" in f:
                    continue  # TODO: avoid replacing configurations, need improvement

                print("File:", f)
                _source = os.path.join(root, f)
                _layer = _source.replace(path, self.__path)

                os.makedirs(os.path.dirname(_layer), exist_ok=True)  # should not be ok, need handling

                if os.path.exists(_layer):
                    if os.path.islink(_layer):
                        os.unlink(_layer)

                if not duplicate:
                    os.symlink(_source, _layer)
                else:
                    shutil.copy2(_source, _layer)

    def mount_dir(self, path: str, name: str = None, duplicate: bool = False):
        """
        Mount a directory (which is not a layer) to the current layer and
        append it to the __mounts list. This should be used to mount external
         directories, use mount_bottle for bottles instead.
        """
        logging.info(f"Mounting path {path} to layer {self.__path}…", )
        _name = name if name else os.path.basename(path)
        _uuid = str(uuid.uuid4())
        hashes = Diff.hashify(path)

        self.__mounts.append({
            "Name": _name,
            "UUID": _uuid,
            "Path": path,
            "Tree": hashes,
            "Type": "absDir",
        })
        self.__link_files(path, duplicate)

    def mount(self, name: str = None, _uuid: str = None, duplicate: bool = False):
        """
        This method will mount a layer to the current layer and
        append it to the __mounts list.
        """
        layer = LayersStore.get(name, _uuid)
        if layer:
            logging.info(f"Mounting layer {layer['Name']}…", )
            layer["Type"] = "layer"
            path = f"{Paths.layers}/@__{layer['Name']}__{layer['UUID']}"  # TODO: please don't hardcode this :S
            self.__mounts.append(layer)
            self.__link_files(path, duplicate)
        else:
            logging.error(f"Layer {_uuid} not found…", )

    def mount_bottle(self, config: dict, duplicate: bool = False):
        """Mount a bottle to the current layer."""
        logging.info(f"Mounting bottle {config['Name']}…", )
        _path = ManagerUtils.get_bottle_path(config)
        self.mount_dir(_path, config["Name"], duplicate)
        self.runtime_conf["Runner"] = config["Runner"]
        self.runtime_conf["IsLayer"] = True

    def sweep(self):
        """
        Unlink all the files in the layer and update the layer tree
        with residues.
        """
        logging.info(f"Sweeping layer {self.__config['Name']}…", )
        for mount in self.__mounts:
            _tree = mount["Tree"]

            for f in _tree:
                _file = f"{self.__path}/{f}"

                if not os.path.exists(_file):
                    continue

                if Diff.file_hashify(_file) != _tree[f]:
                    continue

                if os.path.islink(_file):
                    os.unlink(_file)
                else:
                    os.remove(_file)

            self.__mounts.remove(mount)

        self.__config["Tree"] = Diff.hashify(self.__path)

    def save(self):
        """Save the layer configuration."""
        logging.info(f"Saving layer {self.__config['Name']}…", )
        with open(f"{self.__path}/layer.yml", "w") as f:
            yaml.dump(self.__config, f)
