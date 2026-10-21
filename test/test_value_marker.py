import pytest

from src.generator.value_marker import (
    CallTarget,
    Marker,
    MarkerValue,
    ValueMarkerSyntaxError,
    format_value_marker,
    parse_value_markers,
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
def test_parse_single_marker_values(content: str, expected: tuple[MarkerValue, ...]):
    assert parse_value_markers(content) == (Marker(expected),)


def test_parse_several_markers_with_call_targets():
    content = '<! TF > <!fib#2 : (-, "fib(0)")><! f: (-, "a > b"), (-, "c >") >'

    assert parse_value_markers(content) == (
        Marker((MarkerValue(T), MarkerValue(F))),
        Marker((MarkerValue(None, "fib(0)"),), CallTarget("fib", 2)),
        Marker((MarkerValue(None, "a > b"), MarkerValue(None, "c >")), CallTarget("f")),
    )


@pytest.mark.parametrize("content", ["step", "<! TF > extra", "x < y"])
def test_parse_value_markers_ignores_ordinary_comments(content: str):
    assert parse_value_markers(content) is None


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
        ("<! TF > x <! F >", "между метками непонятный фрагмент «x <! F >»"),
        ('<! TF > < (-, "a") >', "между метками непонятный фрагмент «< \\(-"),
        ('<! (T, "a") > <! (-, "b" >', "ожидалось «,», а не конец разметки"),
        ('<! f#0: (-, "a") >', "нумеруются с 1"),
        ('<! f#: (-, "a") >', "непонятный фрагмент «f#:"),
        ("<! : TF >", "непонятный фрагмент «: TF»"),
    ],
)
def test_parse_value_markers_rejects_malformed(content: str, message: str):
    with pytest.raises(ValueMarkerSyntaxError, match=message):
        parse_value_markers(content)


@pytest.mark.parametrize(
    "content",
    [
        "<! TTF >",
        '<! (T, "f(1)"), (F, "say \\"hi\\"") >',
        '<! (-, "f(2)"), (-, "") >',
        '<! fib#2: (-, "fib(0)") >',
        "<! f: TF >",
    ],
)
def test_format_value_marker_round_trips(content: str):
    markers = parse_value_markers(content)
    assert markers is not None
    assert [format_value_marker(marker) for marker in markers] == [content]
