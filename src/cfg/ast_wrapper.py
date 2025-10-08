from dataclasses import dataclass, field
from typing import Self

import src.cfg.access_property as access_property


@dataclass
class ASTNodeWrapper:
    ast_node: 'src.cfg.cfg.Node | dict[str, src.cfg.cfg.Node] | list[src.cfg.cfg.Node]'  # AST dict (from json) having at least 'type' and 'id' keys.
    parent: Self | None = None  # parent node that sees this node as a child.
    children: dict[str, Self] | list[Self] | None = None
    # related: dict[str, Self] | None = None
    metadata: 'dict | cfg.Metadata' = field(default_factory=dict)

    def get(self,
            role: str,
            identification: 'dict | a.Identification' = None,
            previous_action_data: Self = None
           ) -> Self | None:
        return access_property.resolve(self, role, identification, previous_action_data)

    def describe(self) -> dict:
        """ return type and id of the AST node if set """
        if isinstance(self.ast_node, dict):
            return {
                'ast_type': self.ast_node.get('type'), 
                'ast_id': self.ast_node.get('id'),
                # 'type': type(self.ast_node).__name__,
            }
        else:
            return {
                'ast_type': str(type(self.ast_node).__name__),
                'ast_id': None,
                # 'type': type(self.ast_node).__name__,
            }
