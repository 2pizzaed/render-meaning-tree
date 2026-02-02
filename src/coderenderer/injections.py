# pyright: reportGeneralTypeIssues=false
from src.ast_managers import (
    InjectionPoint,
    InjectionPool,
    TokenCursor,
    injection_for_all,
    observable_token,
    stream_require,
)
from src.coderenderer.entities import Button, make_default_attrs


class ControlFlowButtons(InjectionPool):
    @observable_token()
    def is_simple_statement(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        parent = node.find_first_parent([
            "expression_statement",
            "assignment_statement",
            "variable_declaration"
        ])
        return cursor.manager.is_first_node_token(
            cursor.translate_index(0), parent # type: ignore
        ) if parent else None


    @injection_for_all(is_simple_statement)
    def simple_statement_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        point.push_before(
            Button(
                "play",
                "filled",
                make_default_attrs(point.applied_injections_before,
                    ast_node.id if ast_node else None,
                    ast_node.type if ast_node else None,
                ),
            )
        )
