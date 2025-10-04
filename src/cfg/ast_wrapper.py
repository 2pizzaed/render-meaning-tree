from dataclasses import dataclass, field
from typing import Self

from adict import adict

import src.cfg.access_property as access_property
from src.cfg.cfg import Node, CFG


@dataclass
class ASTNodeWrapper:
    ast_node: Node | dict[str, Node] | list[Node]  # AST dict (from json) having at least 'type' and 'id' keys.
    parent: Self | None = None  # parent node that sees this node as a child.
    children: dict[str, Self] | list[Self] | None = None
    # related: dict[str, Self] | None = None
    metadata: adict = field(default_factory=adict)

    def get(self, role: str, identification: dict = None, previous_action_data: Self = None) -> Self | None:
        return access_property.resolve(self, role, identification, previous_action_data)

    def describe(self) -> dict:
        """ return type and id of the AST node if set """
        return {
            'ast_type': self.ast_node.get('type'), 
            'ast_id': self.ast_node.get('id'),
            # 'type': type(self.ast_node).__name__,
        }
