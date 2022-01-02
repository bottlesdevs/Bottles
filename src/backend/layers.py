import os
import uuid
import json
import shutil
import subprocess
from typing import NewType

from ..utils import UtilsLogger
from .runner import Runner
from .manager_utils import ManagerUtils
from .globals import Paths, Samples
from .diff import Diff


logging = UtilsLogger()
BottleConfig = NewType('BottleConfig', dict)


class Layer:

    '''
    (WIP) This feature is not yet implemented.
    ---
    Concept:
    - bottle = Bottle.new() | create a new bottle and return its config
    - layer = Layer.new(bottle, "dotnet48") | create a new empty layer (@__dotnet48__uuid)
    - layer.mount_bottle(bottle) | link the bottle to the layer
    - Dependency.install(layer.config) | install dependency on layer
    - layer.sweep() | unlink bottle files from layer
    - layer.save() | create a index.yml file with stored files and hashes
    - layer = Layer.new(bottle, "epic") | create a new empty layer (@__epic__uuid)
    - layer.mount_bottle(bottle) | link the bottle to the layer
    - layer.mount("dotnet48") | link dotnet48 layer files to the epic layer
    - Installer.run(layer.config) | launch epic installer on layer
    - layer.sweep() | unlink dependency and bottle layers files from layer
    - layer.save() | create a index.yml file with stored files and hashes
    - bottle.add_layer_entry(..) | add a new executable to bottle Layers
    
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
    '''
    __uuid: str = None
    __path: str = None
    __mounts: list = None
    conf: dict = None

    def __gen_layer_path(self, name: str):
        '''
        Generate a new layer path based on the layer name
        and a random uuid. Also create a temporary config.
        '''
        self.__uuid = str(uuid.uuid4())
        folder = f"@__{name}__{self.__uuid}"
        self.__path = f"{Paths.layers}/{folder}"

        _conf = Samples.config.copy()
        _conf["Path"] = f"@__{self.__uuid}"
        _conf["IsLayer"] = True # will be used by Dependency/Installer managers to set the right path

        shutil.makedirs(self.__path)

        self.conf = _conf

    def new(self, name: str):
        logging.info("Creating a new layer …")
        ignored = [
            "dosdevices",
            "users",
            "bottle.yml"
        ]

        self.__gen_layer_path(name)
    
    def mount(self, name: str):
        '''
        This method will mount a layer to the current layer and
        append it to the __mounts list. Mount means symlinking the
        layer files to the current one.
        '''
        pass

    def mount_dir(self, path: str):
        '''
        This method will mount a directory (which is not a layer)
        to the current layer and append it to the __mounts list. This
        should be use to mount external directories, use mount_bottle
        for bottles instead.
        '''
        pass

    def mount_bottle(self, bottle: BottleConfig):
        '''
        This is just a wrapper to mount_dir to get the bottle
        path and mount it to the current layer.
        '''
        pass
    
    def sweep(self) -> BottleConfig:
        pass


        

