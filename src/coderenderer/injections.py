# pyright: reportGeneralTypeIssues=false
from matplotlib.artist import get

from src.ast_managers import (
    InjectionPoint,
    InjectionPool,
    NodePathElement,
    TokenCursor,
    injection_for_all,
    injection_for_any,
    is_language,
    is_language_not_in,
    observable_node,
    observable_token,
    stream_ensure_token,
    stream_require,
)
from src.coderenderer.entities import Button, Token, make_button_attrs

COMPOUND_STATEMENT_TYPES = frozenset({
    "general_for_loop",
    "range_for_loop",
    "while_loop",
    "do_while_loop",
    "if_statement",
    "switch_statement",
    "program_entry_point",
})


@observable_node()
def is_compound_type(node: NodePathElement) -> bool:
    """
    Проверяет, является ли AST-узел составным statement (цикл, if, switch).

    Используется при экспорте кода для определения, показывать ли код целиком
    или ссылку на строку.
    """
    return node.type.lower() in COMPOUND_STATEMENT_TYPES



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
                "break_statement",
                "continue_statement",
            ]
        )

        if target and \
            target.find_first_parent(lambda x: x.instanceof("for_loop")) and \
            not target.find_first_parent(lambda x: x.instanceof("compound_statement")):
            return None

        return (
            target
            and cursor.manager.is_first_node_token(
                token,
                target,  # type: ignore
            )
            and cursor.provide_context(target)
            # здесь и далее provide_context
            # сохраняет target для инъекции (успешного аннотирования в HTML),
            # возможно этот способ нужно доработать
            if target and isinstance(token, Token)
            else None
        )

    @observable_token()
    def is_defined_function(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        target = node.find_first(lambda p: p.instanceof("function_call"))
        if not target:
            return False
        if target.instanceof("method_call"):
            return True

        node_source = target.get(cursor.manager.ast)
        name = node_source.get("function", {}).get("name")  # type: ignore
        return node_source and \
            name in cursor.manager.user_defined_function_names # type: ignore


    @observable_token(before=[is_defined_function])
    def is_function_call_start(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]

        target = node.find_first(
                lambda p : p.instanceof("function_call"))

        return (
            target
            and cursor.manager.is_first_node_token(
                token,
                target,  # type: ignore
            )
            and cursor.provide_context(target)
            if isinstance(token, Token)
            else None
        )

    @observable_token(before=[is_defined_function])
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
            and cursor.provide_context(target)
            if isinstance(token, Token)
            else None
        )

    @observable_token()
    def is_condition(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]
        target = node.find_first(
            lambda p : p.field_name == "condition" and \
            (not p.parent or not p.parent.instanceof("for_loop"))
        )

        return (
            target and
            cursor.manager.is_last_node_token(
                token,
                target,  # type: ignore
            )
            and cursor.provide_context(target)
            if isinstance(token, Token)
            else None
        )

    @observable_token(before=[is_language_not_in(["python"])])
    def is_body_start(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]
        target = node.find_first("compound_statement")

        return (
            target
            and cursor.manager.is_first_node_token(
                token,
                target,  # type: ignore
            )
            and token.is_opening_brace()
            and cursor.provide_context(target)
            if isinstance(token, Token)
            else None
        )

    @observable_token(before=[is_language_not_in(["python"])])
    def is_body_end(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]
        target = node.find_first("compound_statement")

        return (
            target
            and cursor.manager.is_last_node_token(
                token,
                target,  # type: ignore
            )
            and token.is_closing_brace()
            and cursor.provide_context(target)
            if isinstance(token, Token)
            else None
        )

    @observable_token()
    def is_for_each_container_var(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]

        target = node.find_first(
            lambda x: x.field_name == "container" and \
                x.parent and x.parent.instanceof("for_each_loop")
        )

        return (
            target
            and cursor.manager.is_last_node_token(
                token,
                target,  # type: ignore
            )
            and cursor.provide_context(target)
            if isinstance(token, Token)
            else None
        )

    @observable_token()
    def is_for_each_item_var(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]


        target = node.find_first(
            lambda x: (x.field_name == "item" or x.field_name == "identifier")
            and x.parent
            and (
                x.parent.instanceof("for_each_loop")
                or (x.parent.instanceof("range_for_loop") and cursor.manager.language == "python")
            )
        )

        return (
            target
            and cursor.manager.is_last_node_token(
                token,
                target,  # type: ignore
            )
            and cursor.provide_context(target)
            if isinstance(token, Token)
            else None
        )

    @observable_token()
    def is_for_update(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]

        target = node.find_first(
            lambda x: x.field_name == "update" and x.parent \
                and x.parent.instanceof("for_loop")
        )

        return (
            target
            and cursor.manager.is_first_node_token(
                token,
                target,  # type: ignore
            )
            and cursor.provide_context(target)
            if isinstance(token, Token)
            else None
        )

    @observable_token()
    def is_for_init(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]

        target = node.find_first(
            lambda x: x.field_name == "initializer" and x.parent \
                and x.parent.instanceof("general_for_loop")
        )

        return (
            target
            and cursor.manager.is_first_node_token(
                token,
                target,  # type: ignore
            )
            and cursor.provide_context(target)
            if isinstance(token, Token)
            else None
        )

    @observable_token()
    def for_condition_detect(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = stream_ensure_token(cursor[0])

        target = node.find_first(
            lambda x: x.field_name == "condition" and x.parent and x.parent.instanceof("for_loop")
        )

        return (
            target
            and cursor.manager.is_first_node_token(
                token,
                target,  # type: ignore
            )
            and cursor.provide_context(target)
            if isinstance(token, Token)
            else None
        )


    @observable_token(before=[is_language_not_in(["python"])])
    def range_for_condition_detect(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = stream_ensure_token(cursor[0])
        prev_token = stream_ensure_token(cursor[-1])

        target = node.find_first(
            lambda x: x.field_name == "range" and x.parent and x.parent.instanceof("range_for_loop")
        )

        if not target or not prev_token.value.endswith(";"):
            return None
        pos = 0
        for t in range(*cursor.manager.token_index_range(target)): # type: ignore
            t_token = cursor.manager.get_token(t)
            if isinstance(t_token, Token) and t_token.value == ";":
                pos += 1
            if t_token == prev_token and pos >= 2:
                return False

        return isinstance(token, Token) and cursor.provide_context(target)


    @observable_token(before=[is_language_not_in(["python"])])
    def range_for_update_detect(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = stream_ensure_token(cursor[0])
        prev_token = stream_ensure_token(cursor[-1])

        target = node.find_first(
            lambda x: x.field_name == "range" and x.parent and x.parent.instanceof("range_for_loop")
        )

        if not target or not prev_token.value.endswith(";"):
            return None
        pos = 0
        t_range = cursor.manager.token_index_range(target)
        for t in range(*t_range):  # type: ignore
            t_token = cursor.manager.get_token(t)
            if isinstance(t_token, Token) and t_token.value == ";":
                pos += 1
            if t_token == prev_token and pos < 2:
                return False

        return isinstance(token, Token) and pos == 2 and cursor.provide_context(target)


    @observable_token(before=[is_language_not_in(["python"])])
    def range_for_init_detect(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = stream_ensure_token(cursor[0])
        prev_token = stream_ensure_token(cursor[-1])

        target = node.find_first(
            lambda x: x.field_name == "range" and x.parent and x.parent.instanceof("range_for_loop")
        )

        if not target or not prev_token.value.endswith("("):
            return None

        t_range = cursor.manager.token_index_range(target)
        if prev_token.index == t_range[0]:  # type: ignore
            return None

        return isinstance(token, Token) and cursor.provide_context(target)


    @observable_token(before=[is_language("python")])
    def is_range_in_for_python(cursor: TokenCursor):
        node = stream_require(cursor.ast_node(0))
        token = cursor[0]

        target = node.find_first(
            lambda x: x.field_name == "range" and x.parent \
                and x.parent.instanceof("range_for_loop")
        )

        return (
            target
            and cursor.manager.is_first_node_token(
                token,
                target,  # type: ignore
            )
            and cursor.provide_context(target)
            if isinstance(token, Token)
            else None
        )

    @injection_for_all(is_simple_statement)
    def simple_statement_button(point: InjectionPoint):
        if len(point.matched_conditions) > 1:
            point.cancel()
            return
        ast_node = point.context_node or point.ast_node(0)
        point.push_before(
            Button(
                "play",
                "filled",
                **make_button_attrs(
                    point.applied_injections_before,
                    ast_node,
                    position="before",
                ),
            )
        )

    @injection_for_all(is_function_call_start)
    def stepinto_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        target = point.context_node or ast_node
        point.push_before(
            Button(
                "step-into",
                "filled",
                **make_button_attrs(
                    point.applied_injections_before,
                    target,
                    position="before",
                ),
            )
        )

    @injection_for_all(is_function_call_end)
    def stepout_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        target = point.context_node or ast_node
        point.push_after(
            Button(
                "step-out",
                "filled",
                **make_button_attrs(
                    point.applied_injections_before,
                    target,
                    position="after",
                ),
            )
        )

    @injection_for_all(is_condition)
    def condition_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        target = point.context_node or ast_node
        point.push_after(
            Button(
                "question",
                "filled",
                **make_button_attrs(
                    point.applied_injections_before,
                    target,
                    position="after",
                ),
            )
        )

    @injection_for_all(is_body_start)
    def body_start_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        target = point.context_node or ast_node
        point.push_after(
            Button(
                "play",
                "filled",
                **make_button_attrs(
                    point.applied_injections_before,
                    target,
                    position="after",
                ),
            )
        )

    @injection_for_all(is_body_end)
    def body_end_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        target = point.context_node or ast_node
        point.push_after(
            Button(
                "stop",
                "filled",
                **make_button_attrs(
                    point.applied_injections_before,
                    target,
                    position="after",
                ),
            )
        )

    @injection_for_all(is_for_each_item_var)
    def for_each_item_var_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        target = point.context_node or ast_node
        point.push_after(
            Button(
                "question",
                "filled",
                **make_button_attrs(
                    point.applied_injections_before,
                    target,
                    position="before",
                ),
            )
        )

    @injection_for_any(is_for_each_container_var,
                       is_range_in_for_python)
    def for_each_container_var_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        target = point.context_node or ast_node
        point.push_before(
            Button(
                "play",
                "filled",
                **make_button_attrs(
                    point.applied_injections_before,
                    target,
                    position="before",
                ),
            )
        )

    @injection_for_any(
        range_for_init_detect,
        range_for_update_detect,
        is_for_init,
        is_for_update,
    )
    def for_component_play_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        target = point.context_node or ast_node
        point.push_before(
            Button(
                "play",
                "filled",
                **make_button_attrs(
                    point.applied_injections_before,
                    target,
                    position="before",
                ),
            )
        )

    @injection_for_any(for_condition_detect, range_for_condition_detect)
    def for_condition_button(point: InjectionPoint):
        ast_node = point.ast_node(0)
        target = point.context_node or ast_node
        point.push_before(
            Button(
                "question",
                "filled",
                **make_button_attrs(
                    point.applied_injections_before,
                    target,
                    position="before",
                ),
            )
        )
