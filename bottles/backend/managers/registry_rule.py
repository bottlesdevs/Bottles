import os
import uuid
from typing import TYPE_CHECKING, Iterable, List, Optional

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.registry_rule import RegistryRule
from bottles.backend.wine.reg import Reg
from bottles.backend.utils.manager import ManagerUtils

if TYPE_CHECKING:  # pragma: no cover
    from bottles.backend.managers.manager import Manager

logging = Logger()


class RegistryRuleManager:
    """Manage reusable registry rules stored in bottle configs."""

    @staticmethod
    def load_rules(config: BottleConfig) -> dict[str, RegistryRule]:
        rules = {}
        for raw in getattr(config, "Registry_Rules", []) or []:
            rule = RegistryRule.from_dict(raw or {})
            if rule.name:
                rules[rule.name] = rule
        return rules

    @classmethod
    def list_rules(cls, config: BottleConfig) -> List[RegistryRule]:
        return list(cls.load_rules(config).values())

    @classmethod
    def upsert_rule(
        cls, manager: "Manager", config: BottleConfig, rule: RegistryRule
    ) -> None:
        rules = cls.load_rules(config)
        rules[rule.name] = rule
        serialised = [item.to_dict() for item in rules.values()]
        manager.update_config(config=config, key="Registry_Rules", value=serialised)

    @classmethod
    def delete_rule(cls, manager: "Manager", config: BottleConfig, name: str):
        rules = cls.load_rules(config)
        if name in rules:
            del rules[name]
            serialised = [item.to_dict() for item in rules.values()]
            manager.update_config(
                config=config, key="Registry_Rules", value=serialised
            )

    @classmethod
    def apply_rules(
        cls,
        config: BottleConfig,
        rule_names: Optional[Iterable[str]] = None,
        trigger: Optional[str] = None,
    ):
        rules = cls.load_rules(config)
        selected = (
            {name: rules[name] for name in rule_names if name in rules}
            if rule_names
            else rules
        )

        if trigger:
            selected = {
                name: rule
                for name, rule in selected.items()
                if not rule.triggers or trigger in rule.triggers or "all" in rule.triggers
            }

        reg = Reg(config)
        for name, rule in selected.items():
            if not rule.keys.strip():
                continue
            logging.info(f"Applying registry rule '{name}' for {config.Name}")
            reg_file = ManagerUtils.get_temp_path(f"{uuid.uuid4()}.reg")
            keys = rule.keys.lstrip()
            has_header = keys.upper().startswith("REGEDIT4") or keys.lower().startswith(
                "windows registry editor version"
            )

            with open(reg_file, "w") as bundle_file:
                if not has_header:
                    bundle_file.write("REGEDIT4\n\n")
                bundle_file.write(keys.rstrip())
                bundle_file.write("\n")
            reg.launch(f"import {reg_file}", communicate=True, minimal=True)
            os.remove(reg_file)
