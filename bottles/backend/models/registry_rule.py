from dataclasses import dataclass, field
from typing import List


@dataclass
class RegistryRule:
    """Reusable registry rule definition.

    Each rule stores registry key definitions as raw text so the backend can
    generate a .reg file when the rule is applied.
    """

    name: str
    description: str = ""
    keys: str = ""
    triggers: List[str] = field(default_factory=list)
    run_once: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "RegistryRule":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            keys=data.get("keys", ""),
            triggers=data.get("triggers", []) or [],
            run_once=data.get("run_once", False),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "keys": self.keys,
            "triggers": self.triggers,
            "run_once": self.run_once,
        }
