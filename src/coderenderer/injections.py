# pyright: reportGeneralTypeIssues=false
from src.ast_managers import (
    InjectionPoint,
    InjectionPool,
    NodePathElement,
    injection_for_all,
    is_first_node_token,
    observable_node,
)
from src.coderenderer.entities import Button


class ControlFlowButtons(InjectionPool):
    @observable_node()
    def is_simple_statement(cursor: NodePathElement):
        return cursor.type in [
            "expression_statement",
            "assignment_statement",
            "variable_declaration"
        ]

    @injection_for_all(is_first_node_token, is_simple_statement)
    def simple_statement_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        point.push_before(
            Button("play", "filled", {
                "action_id": point.applied_injections_before,
                "node_id": ast_node,
                "node_type": ast_node.type if ast_node else None
            })
        )
