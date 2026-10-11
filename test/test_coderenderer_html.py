import pytest

from src.ast_managers import prepare_code
from src.coderenderer.entities import Token
from src.coderenderer.html import (
    add_spacing_to_stream,
    extract_buttons_from_context,
    prepare_html_context,
    should_add_space,
)


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
