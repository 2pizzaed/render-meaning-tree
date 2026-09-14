import pytest

from src.coderenderer.entities import Token
from src.coderenderer.html import add_spacing_to_stream, should_add_space


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
