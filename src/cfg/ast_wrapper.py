from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self

import src.cfg.access_property as access_property
from src.ast_analyzer import ASTNodeAnalyzer

if TYPE_CHECKING:
    from src.ast_managers import CodeManager


@dataclass
class ASTNodeWrapper:
    ast_node: dict[str, Any]  # AST dict (from json) having at least 'type' and 'id' keys.
    parent: Self | None = None  # parent node that sees this node as a child.
    children: dict[str, Self] | list[Self] | None = None
    # related: dict[str, Self] | None = None
    # metadata: 'dict | cfg.Metadata' = field(default_factory=dict)  # TODO remove
    _astnodeanalyzer: "ASTNodeAnalyzer | CodeManager | None" = None  # Note: set for root only (when parent is not set).

    def get(self,
            role: str,
            identification: 'dict | a.Identification' = None,
            previous_action_data: Self = None
           ) -> Self | None:
        return access_property.resolve(self, role, identification, previous_action_data)

    def get_root(self, _seen: set[int] = None) -> Self | None:
        """Traverse up to the root node."""
        if not self.parent:
            return self
        seen = _seen or set()
        self_id = id(self)
        if self_id in seen:
            return None  # loop detected! No root can be found.
        seen.add(self_id)
        return self.parent.get_root(_seen=seen)

    def describe(self) -> dict:
        """ return type and id of the AST node if set """
        if isinstance(self.ast_node, dict):
            return {
                'ast_node': self.ast_node.get('type'),
                'ast_id': self.ast_node.get('id'),
                # 'type': type(self.ast_node).__name__,
            }
        else:
            return {
                'ast_node': str(type(self.ast_node).__name__),
                'ast_id': None,
                # 'type': type(self.ast_node).__name__,
            }
