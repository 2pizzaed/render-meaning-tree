import pytest

from src.ast_managers import prepare_code
from src.coderenderer.entities import Token
from src.coderenderer.html import (
    add_spacing_to_stream,
    extract_buttons_from_context,
    prepare_html_context,
    should_add_space,
)
from src.generator.utilities import code_snippet_to_registry


def make_token(index: int, value: str) -> Token:
    return Token(index, value, "unknown", "token", index, None)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("obj", "."),
        (".", "method"),
        ("std", "::"),
        ("::", "cout"),
        ("ptr", "->"),
        ("->", "field"),
        ("obj", ".*"),
        (".*", "member"),
        ("ptr", "->*"),
        ("->*", "member"),
    ],
)
def test_member_access_tokens_are_rendered_without_spaces(
    left: str,
    right: str,
) -> None:
    assert not should_add_space(make_token(0, left), make_token(1, right))


def test_spacing_keeps_original_token_indexes() -> None:
    tokens = [
        make_token(0, "std"),
        make_token(1, "::"),
        make_token(2, "cout"),
        make_token(3, "+"),
        make_token(4, "value"),
    ]

    spaced = add_spacing_to_stream(tokens)
    rendered_tokens = [entity for entity in spaced if isinstance(entity, Token)]

    assert "".join(token.value for token in rendered_tokens) == "std::cout + value"
    assert [token.index for token in rendered_tokens if token.index >= 0] == list(
        range(5)
    )


def test_call_buttons_only_for_program_procedures_and_bound_to_call() -> None:
    manager = prepare_code(
        "def g(a):\n    return a\n\nd = set()\ng(1)\ng(2)\nd.add(1)\n", "python"
    )

    buttons = extract_buttons_from_context(prepare_html_context(manager))

    # Стрелки - только у вызовов функции программы, и обе привязаны к самому вызову,
    # а не к оператору, который им начинается.
    assert [
        (button["type"], button["node_type"], manager.code_piece(button["node_id"]))
        for button in buttons
        if button["type"] in {"step-into", "step-out"}
    ] == [
        ("step-into", "function_call", "g(1)"),
        ("step-out", "function_call", "g(1)"),
        ("step-into", "function_call", "g(2)"),
        ("step-out", "function_call", "g(2)"),
    ]
    played = {manager.code_piece(button["node_id"]) for button in buttons if button["type"] == "play"}
    # Библиотечный метод - обычный оператор; у оператора-вызова функции кнопки play нет.
    assert "d.add(1)" in played
    assert not {"g(1)", "g(2)"} & played


@pytest.mark.parametrize(
    ("language", "code"),
    [
        (
            "java",
            (
                "switch (x) {\n"
                "case 1, 2: // <! F >\n    a = 1; break;\n"
                "case 3: // <! F >\n    a = 2; break;\n"
                "case 4, 5: // <! T >\n    a = 3; break;\n"
                "default: a = 4;\n}"
            ),
        ),
        (
            "python",
            (
                "match x:\n"
                "    case 1 | 2: # <! F >\n        a = 1\n"
                "    case 3: # <! F >\n        a = 2\n"
                "    case 4 | 5: # <! T >\n        a = 3\n"
                "    case _: a = 4\n"
            ),
        ),
    ],
    ids=["java", "python"],
)
def test_case_groups_have_one_annotated_condition_and_button_per_branch(
    language: str, code: str
) -> None:
    registry = code_snippet_to_registry(code, language=language)
    conditions = [action for action in registry.all_actions() if action.is_condition]
    cases = registry.code.ast.find_paths_by_type("basic_case_block")
    assert len(cases) == len(conditions) == 3
    assert [action.ast_id for action in conditions] == [case.id for case in cases]
    assert [action.rule.role for action in conditions] == ["first_case", "next_case", "next_case"]
    assert [
        action.annotation.marker if action.annotation else None for action in conditions
    ] == ["<! F >", "<! F >", "<! T >"]

    context = prepare_html_context(registry.code)
    questions = [
        button for button in extract_buttons_from_context(context)
        if button["type"] == "question"
    ]
    assert [button["node_id"] for button in questions] == [action.ast_id for action in conditions]
    # Кнопка стоит в заголовке после последнего значения и разделителя, а не после тела.
    for button, last_value in zip(questions, ("2", "3", "5"), strict=True):
        before_button = context["lines"][button["line_index"]][:button["column_index"]]
        values = [
            entity.value for entity in before_button
            if isinstance(entity, Token) and entity.value.strip() not in {"", ":"}
        ]
        assert values[-1] == last_value


def test_condition_button_precedes_header_colon_despite_trailing_comment() -> None:
    # Meaning Tree вешает комментарий конца строки на условие (trailing_comments),
    # но кнопка всё равно должна стоять сразу после условия, перед `:`.
    manager = prepare_code("if x <= 1:  # <! T >\n    y = 1\n", "python")

    context = prepare_html_context(manager)
    [button] = [
        button for button in extract_buttons_from_context(context)
        if button["type"] == "question"
    ]
    before_button = context["lines"][button["line_index"]][:button["column_index"]]
    values = [
        entity.value for entity in before_button
        if isinstance(entity, Token) and entity.value.strip()
    ]
    assert values == ["if", "x", "<=", "1"]


def test_list_unpacking_declaration_gets_play_button() -> None:
    manager = prepare_code("def f(x):\n    return x, x\n\na, b = f(1)\n", "python")

    buttons = extract_buttons_from_context(prepare_html_context(manager))

    played = {manager.code_piece(button["node_id"]) for button in buttons if button["type"] == "play"}
    assert "a, b = f(1)" in played
