# versioning.py
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

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils

# The implementations doing the actual work
from bottles.backend.models.btrfssubvolume import try_create_bottle_snapshots_versioning_wrapper, BottleSnapshotsVersioningWrapper
from bottles.backend.models.fvs_versioning import BottleFvsVersioning

# noinspection PyTypeChecker
class VersioningManager:
    def __init__(self, manager):
        self.manager = manager

    def _get_bottle_versioning_system(self, config: BottleConfig):
        bottle_path = ManagerUtils.get_bottle_path(config)
        bottle_snapshots_wrapper = try_create_bottle_snapshots_versioning_wrapper(bottle_path)
        if bottle_snapshots_wrapper:
            return bottle_snapshots_wrapper
        def update_config(config: BottleConfig, key: str, value: any):
            self.manager.update_config(config, key, value)
        return BottleFvsVersioning(config, bottle_path, update_config)

    def is_initialized(self, config: BottleConfig):
        bottle_versioning_system = self._get_bottle_versioning_system(config)
        return bottle_versioning_system.is_initialized()

    def re_initialize(self, config: BottleConfig):
        bottle_versioning_system = self._get_bottle_versioning_system(config)
        return bottle_versioning_system.re_initialize()

    def update_system(self, config: BottleConfig):
        bottle_versioning_system = self._get_bottle_versioning_system(config)
        return bottle_versioning_system.update_system()

    def create_state(self, config: BottleConfig, message: str = "No message"):
        bottle_versioning_system = self._get_bottle_versioning_system(config)
        return bottle_versioning_system.create_state(message)

    def list_states(self, config: BottleConfig) -> Result:
        bottle_versioning_system = self._get_bottle_versioning_system(config)
        return bottle_versioning_system.list_states()

    def set_state(
        self, config: BottleConfig, state_id: int, after: callable = None
    ) -> Result:
        bottle_versioning_system = self._get_bottle_versioning_system(config)
        return bottle_versioning_system.set_state(state_id, after)
