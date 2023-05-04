import codecs
import dataclasses
import os
import uuid
from datetime import datetime
from itertools import groupby
from typing import List, Dict, Optional

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.utils.generic import random_string
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.wineprogram import WineProgram

logging = Logger()


@dataclasses.dataclass
class RegItem:
    key: str
    value: str
    value_type: str
    data: str


class Reg(WineProgram):
    program = "Wine Registry CLI"
    command = "reg"

    def bulk_add(self, regs: List[RegItem]):
        """Import multiple registries at once, with v5.00 reg file"""
        config = self.config
        logging.info(f"Importing {len(regs)} Key(s) to {config.Name} registry")
        winedbg = WineDbg(config)

        mapping: Dict[str, List[RegItem]] = {k: list(v) for k, v in groupby(regs, lambda x: x.key)}
        reg_file_header = "Windows Registry Editor Version 5.00\n\n"
        reg_key_header = "[%s]\n"
        reg_item_fmt = '"%s"="%s:%s"\n'
        reg_item_def_fmt = '"%s"="%s"\n'  # default is REG_SZ(string)

        file_content = reg_file_header
        for key, items in mapping.items():
            file_content += reg_key_header % key
            for item in items:
                if item.value_type:
                    file_content += reg_item_fmt % (item.value, item.value_type, item.data)
                else:
                    file_content += reg_item_def_fmt % (item.value, item.data)
            file_content += "\n"

        tmp_reg_filepath = os.path.join(Paths.temp, f"bulk_{int(datetime.now().timestamp())}_{random_string(8)}.reg")
        with open(tmp_reg_filepath, 'wb') as f:
            f.write(codecs.BOM_UTF16_LE)
            f.write(file_content.encode('utf-16le'))

        # avoid conflicts when executing async
        winedbg.wait_for_process("reg.exe")

        res = self.launch(("import", tmp_reg_filepath), communicate=True, minimal=True, action_name="bulk_add")
        logging.info(res.data)

    def add(self, key: str, value: str, data: str, value_type: Optional[str] = None):
        config = self.config
        logging.info(f"Adding Key: [{key}] with Value: [{value}] and "
                     f"Data: [{data}] in {config.Name} registry")
        winedbg = WineDbg(config)
        args = "add '%s' /v '%s' /d '%s' /f" % (key, value, data)

        if value_type is not None:
            args = "add '%s' /v '%s' /t %s /d '%s' /f" % (
                key, value, value_type, data
            )

        # avoid conflicts when executing async
        winedbg.wait_for_process("reg.exe")

        res = self.launch(args, communicate=True, minimal=True, action_name="add")
        logging.info(res.data)

    def remove(self, key: str, value: str):
        """Remove a key from the registry"""
        config = self.config
        logging.info(f"Removing Value: [{key}] from Key: [{value}] in "
                     f"{config.Name} registry")
        winedbg = WineDbg(config)
        args = "delete '%s' /v %s /f" % (key, value)

        # avoid conflicts when executing async
        winedbg.wait_for_process("reg.exe")

        res = self.launch(args, communicate=True, minimal=True, action_name="remove")
        logging.info(res.data)

    def import_bundle(self, bundle: dict):
        """Import a bundle of keys into the registry"""
        config = self.config
        logging.info(f"Importing bundle to {config.Name} registry")
        winedbg = WineDbg(config)
        reg_file = ManagerUtils.get_temp_path(f"{uuid.uuid4()}.reg")

        # prepare reg file
        with open(reg_file, "w") as f:
            f.write("REGEDIT4\n\n")

            for key in bundle:
                f.write(f"[{key}]\n")

                for value in bundle[key]:
                    if value["data"] == "-":
                        f.write(f'"{value["value"]}"=-\n')
                    elif "key_type" in value:
                        f.write(f'"{value["value"]}"={value["key_type"]}:{value["data"]}\n')
                    else:
                        f.write(f'"{value["value"]}"="{value["data"]}"\n')

                f.write("\n")

        args = f"import {reg_file}"

        # avoid conflicts when executing async
        winedbg.wait_for_process("reg.exe")

        res = self.launch(args, communicate=True, minimal=True, action_name="import_bundle")
        logging.info(f"Import bundle result: '{res.data}'")

        # remove reg file
        os.remove(reg_file)
