# pyright: reportGeneralTypeIssues=false
from src.ast_managers import (
    InjectionPoint,
    InjectionPool,
    TokenCursor,
    injection_for_all,
    observable_token,
    stream_require,
)
from src.coderenderer.entities import Button, Token, make_button_attrs


class ControlFlowButtons(InjectionPool):
    @observable_token()
    def is_simple_statement(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]

        target = node.find_first(
            [
                "expression_statement",
                "assignment_statement",
                "variable_declaration",
                "return_statement",
            ]
        )

        return cursor.manager.is_first_node_token(
            token, target # type: ignore
        ) if target and isinstance(token, Token) else None


    @observable_token()
    def is_function_call_start(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]

        target = node.find_first(
                lambda p : p.instanceof("function_call")
        )
        return (
            target
            and cursor.manager.is_first_node_token(
                token,
                target,  # type: ignore
            )
            if isinstance(token, Token)
            else None
        )

    @observable_token()
    def is_function_call_end(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]

        target = node.find_first(
            lambda p : p.instanceof("function_call")
        )
        return (
            target
            and cursor.manager.is_last_node_token(
                token,
                target,  # type: ignore
            )
            if isinstance(token, Token)
            else None
        )

    @injection_for_all(is_simple_statement)
    def simple_statement_button(point: InjectionPoint):
        if len(point.matched_conditions) > 1:
            point.cancel()
            return
        ast_node = point.ast_node(0)
        point.push_before(
            Button(
                "play",
                "filled",
                **make_button_attrs(
                    point.applied_injections_before, ast_node),
            )
        )

    @injection_for_all(is_function_call_start)
    def stepinto_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        point.push_before(
            Button(
                "step-into",
                "filled",
                **make_button_attrs(point.applied_injections_before, ast_node),
            )
        )

    @injection_for_all(is_function_call_end)
    def stepout_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        point.push_after(
            Button(
                "step-out",
                "filled",
                **make_button_attrs(point.applied_injections_before, ast_node),
            )
        )
