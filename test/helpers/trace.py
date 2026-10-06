"""Build small AST-backed traces without invoking the toolchain."""

from typing import cast

from src.ast_managers import ASTNodeManager, CodeManager
from src.generator.pipeline.registry import SituationRegistry
from src.model.rules import (
    ActionDeclaration,
    ConstructDeclaration,
    TransitionDeclaration,
)
from src.model.situation import Action, Construct, SemanticValue, TraceAct
from src.types import JsonValue, Node, ScopeTable, SourceMap


def ast_node(ast_id: int, node_type: str, **fields: JsonValue) -> Node:
    return cast(Node, {"id": ast_id, "type": node_type, **fields})


class TraceBuilder:
    def __init__(self, root: Node) -> None:
        self.ast = ASTNodeManager(root)
        self.ast._process()
        scopes: ScopeTable = {
            "type": "scope_table",
            "current_scope_id": 0,
            "assignment_binding": "LOCAL",
            "symbols": {"declarations": [], "definitions": [], "overload_groups": []},
            "types": {"declared_types": [], "type_declarations": [], "hierarchy": []},
            "imports": {"items": []},
            "scopes": [],
        }
        source_map: SourceMap = {
            "type": "source_map",
            "origin": root,
            "source_code": "",
            "language": "python",
            "byte_positions": {},
            "render_scope_table": scopes,
            "metrics": {},
        }
        code = CodeManager(self.ast, source_map, {"type": "tokens", "items": []})
        self.registry = SituationRegistry(code=code)

    @property
    def trace(self) -> list[TraceAct]:
        return self.registry.trace_acts

    def construct(
        self,
        ast_id: int,
        *,
        name: str = "block_structure",
        kind: str = "compound.sequence",
        parent: Construct | None = None,
        preorder: bool = False,
    ) -> Construct:
        node = self.ast.get(ast_id)
        if node is None:
            raise ValueError(f"No AST node {ast_id}")
        rule = ConstructDeclaration(name, kind, node["type"], preorder=preorder)
        construct = Construct(parent, ast_id, rule, self.registry)
        self.registry.add(construct)
        return construct

    def action(
        self,
        ast_id: int,
        parent: Construct,
        *,
        role: str = "item",
        kind: str = "inline",
        opaque: bool = True,
    ) -> Action:
        rule = ActionDeclaration(role, kind, opaque=opaque)
        rule.parent = parent.rule
        parent.rule.actions.append(rule)
        action = Action(ast_id, [], rule, parent, self.registry)
        self.registry.add(action)
        return action

    def act(
        self,
        action: Action,
        *,
        transition: TransitionDeclaration | None = None,
        value: SemanticValue | None = None,
        unfolded_from: Action | None = None,
    ) -> TraceAct:
        act = TraceAct(action, transition, self.registry, value, unfolded_from)
        self.registry.add(act)
        return act
