# template.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils import yaml
import uuid
import shutil
import contextlib
from datetime import datetime
from pathlib import Path

from bottles.backend.logger import Logger
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.globals import Paths
from bottles.backend.models.samples import Samples

logging = Logger()


class TemplateManager:

    @staticmethod
    def new(env: str, config: BottleConfig):
        env = env.lower()
        templates = TemplateManager.get_templates()

        for template in templates:
            if template["env"] == env:
                logging.info(f"Caching new template for {env}…")
                TemplateManager.delete_template(template["uuid"])

        _uuid = str(uuid.uuid4())
        logging.info(f"Creating new template: {_uuid}")
        bottle = ManagerUtils.get_bottle_path(config)

        delattr(config, "Name")
        delattr(config, "Path")
        delattr(config, "Creation_Date")
        delattr(config, "Update_Date")

        ignored = [
            "dosdevices",
            "states",
            ".fvs",
            "*.yml"
            ".*"
        ]

        _path = os.path.join(Paths.templates, _uuid)
        logging.info("Copying files …")

        with contextlib.suppress(FileNotFoundError):
            shutil.copytree(bottle, _path, symlinks=True, ignore=shutil.ignore_patterns(*ignored))

        template = {
            "uuid": _uuid,
            "env": env,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config": config
        }

        with open(os.path.join(_path, "template.yml"), "w") as f:
            yaml.dump(template, f)

        logging.info(f"New template {env} created", jn=True)

        if not TemplateManager.__validate_template(_uuid):
            logging.error("Template validation failed, will retry with next bottle.")
            shutil.rmtree(_path)

    @staticmethod
    def __validate_template(template_uuid: str):
        result = True
        template_path = os.path.join(Paths.templates, template_uuid)
        essentials = [
            "drive_c/ProgramData",
            "drive_c/windows",
        ]

        if not os.path.exists(template_path):
            logging.error(f"Template {template_uuid} not found!")
            result = False

        for essential in essentials:
            if not os.path.exists(os.path.join(template_path, essential)):
                logging.error(f"Template {template_uuid} is missing essential path: {essential}")
                result = False

        path_size = sum(file.stat().st_size for file in Path(template_path).rglob('*'))
        if path_size < 300000000:
            logging.error(f"Template {template_uuid} is too small!")
            result = False
        
        with open(os.path.join(template_path, "template.yml"), "r") as f:
            template = yaml.load(f)
            if template["uuid"] != template_uuid:
                logging.error(f"Template {template_uuid} has invalid uuid!")
                result = False

        return result

    @staticmethod
    def get_template_manifest(template: str):
        with open(os.path.join(Paths.templates, template, "template.yml"), "r") as f:
            return yaml.load(f)

    @staticmethod
    def get_templates():
        res = []
        templates = os.listdir(Paths.templates)

        for template in templates:
            if os.path.exists(os.path.join(Paths.templates, template, "template.yml")):
                _manifest = TemplateManager.get_template_manifest(template)
                if _manifest is not None:
                    res.append(_manifest)

        return res

    @staticmethod
    def delete_template(template_uuid: str):
        if not template_uuid:
            logging.error("Template uuid is not defined!")
            return

        if not os.path.exists(os.path.join(Paths.templates, template_uuid)):
            logging.error(f"Template {template_uuid} not found!")
            return

        logging.info(f"Deleting template: {template_uuid}")
        shutil.rmtree(os.path.join(Paths.templates, template_uuid))
        logging.info("Template deleted successfully!")

    @staticmethod
    def check_outdated(template: dict):
        env = template.get("env", "")
        if env not in Samples.environments:
            TemplateManager.delete_template(template.get("uuid"))
            return True

        _sample = Samples.environments[env]
        for p in _sample.get("Parameters", {}):
            _params = template.get("config", {}).get("Parameters", {})
            if p not in _params or _params[p] != _sample["Parameters"][p]:
                TemplateManager.delete_template(template.get("uuid"))
                return True

        for d in _sample.get("Installed_Dependencies", []):
            _deps = template.get("config", {}).get("Installed_Dependencies", [])
            if d not in _deps:
                TemplateManager.delete_template(template.get("uuid"))
                return True

        return False

    @staticmethod
    def get_env_template(env: str):
        _templates = TemplateManager.get_templates()
        for template in _templates:
            if template["env"] == env.lower():
                if TemplateManager.check_outdated(template):
                    logging.info(f"Deleting outdated template: {template['uuid']}")
                    return None
                return template
        return None

    @staticmethod
    def unpack_template(template: dict, config: BottleConfig):
        def copy_func(source: str, dest: str):
            if os.path.islink(source):
                # we don't want symlinks from templates
                return
            shutil.copy2(source, dest)

        logging.info(f"Unpacking template: {template['uuid']}")
        bottle = ManagerUtils.get_bottle_path(config)
        _path = os.path.join(Paths.templates, template['uuid'])

        shutil.copytree(_path, bottle, symlinks=True, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.*'), ignore_dangling_symlinks=True)
        logging.info("Template unpacked successfully!")
