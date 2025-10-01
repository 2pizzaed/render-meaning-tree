from dataclasses import dataclass, field
from typing import Dict, List, Optional, Self

from adict import adict

import src.cfg.access_property as access_property
from src.cfg.cfg import Node, CFG


@dataclass
class ASTNodeWrapper:
    ast_node: Node | dict[str, Node] | List[Node]  # AST dict (from json) having at least 'type' and 'id' keys.
    parent: Self | None = None  # parent node that sees this node as a child.
    children: Dict[str, Self] | List[Self] | None = None
    related: Dict[str, Self] | None = None
    metadata: adict = field(default_factory=adict)

    def get(self, role: str, identification: dict = None, previous_action_data: Self = None) -> Self | None:
        return access_property.get(self, role, identification, previous_action_data)