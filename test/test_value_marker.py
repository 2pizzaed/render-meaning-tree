import pytest

from src.generator.value_marker import (
    MarkerValue,
    ValueMarkerSyntaxError,
    format_value_marker,
    parse_value_marker,
)

T, F = True, False


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (" <! TTF > ", (MarkerValue(T), MarkerValue(T), MarkerValue(F))),
        ("<!F>", (MarkerValue(F),)),
        (
            '<! (T, "f(1)"),(F, "f(2)") >',
            (MarkerValue(T, "f(1)"), MarkerValue(F, "f(2)")),
        ),
        (
            '<!( T ,"a, (b)" ) , ( F,"x > 0" )>',
            (MarkerValue(T, "a, (b)"), MarkerValue(F, "x > 0")),
        ),
        ('<! (T, "") >', (MarkerValue(T, ""),)),
        ('<! (-, "f(2)"),( - ,"") >', (MarkerValue(None, "f(2)"), MarkerValue(None, ""))),
        (r'<! (F, "say \"hi\"\\") >', (MarkerValue(F, 'say "hi"\\'),)),
    ],
)
def test_parse_value_marker(content: str, expected: tuple[MarkerValue, ...]):
    assert parse_value_marker(content) == expected


@pytest.mark.parametrize("content", ["step", "<! TF > extra", "x < y"])
def test_parse_value_marker_ignores_ordinary_comments(content: str):
    assert parse_value_marker(content) is None


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("<!  >", "пустая разметка"),
        ("<! TX >", "непонятный фрагмент «TX»"),
        ('<! (TT, "a") >', "непонятный фрагмент «TT"),
        ('<! (T, "a") (F, "b") >', "ожидалось «,», а не «\\(»"),
        ('<! (T, "a"), >', "ожидалось «\\(», а не конец разметки"),
        ('<! (T, "a" >', "ожидалось «,», а не конец разметки"),
        ("<! (T) >", 'кортеж \\(T\\) не в форме \\(T\\|F\\|-, "подсказка"\\)'),
        ("<! T-F >", "ожидалось «\\(», а не «T»"),
        ("<! (-) >", "не в форме"),
        ('<! ("a", T) >', "не в форме"),
        ('<! (T, "a", "b") >', "не в форме"),
        ('<! (T, "a"b") >', "непонятный фрагмент"),
        (r'<! (T, "\q") >', r'некорректная строка "\\q"'),
        ('<! T, (F, "a") >', "ожидалось «\\(», а не «T»"),
    ],
)
def test_parse_value_marker_rejects_malformed(content: str, message: str):
    with pytest.raises(ValueMarkerSyntaxError, match=message):
        parse_value_marker(content)


@pytest.mark.parametrize(
    "content",
    ["<! TTF >", '<! (T, "f(1)"), (F, "say \\"hi\\"") >', '<! (-, "f(2)"), (-, "") >'],
)
def test_format_value_marker_round_trips(content: str):
    values = parse_value_marker(content)
    assert values is not None
    assert format_value_marker(values) == content
