from __future__ import annotations

import pytest

from src.helpers.grammar_case import GrammaticalCase, decline


@pytest.mark.parametrize(
    ("label", "case"),
    [("р", GrammaticalCase.GENITIVE), ("Творительный", GrammaticalCase.INSTRUMENTAL), ("loct", GrammaticalCase.PREPOSITIONAL)],
)
def test_case_is_parsed_from_russian_name_or_grammeme(label: str, case: GrammaticalCase) -> None:
    assert GrammaticalCase.parse(label) is case


def test_unknown_case_is_rejected() -> None:
    with pytest.raises(ValueError):
        GrammaticalCase.parse("x")


@pytest.mark.parametrize(
    ("text", "case", "expected"),
    [
        ("цикл <code>while</code> на строке 5", GrammaticalCase.GENITIVE, "цикла <code>while</code> на строке 5"),
        ("условие существования следующего элемента", GrammaticalCase.INSTRUMENTAL, "условием существования следующего элемента"),
        ("множественное ветвление", GrammaticalCase.ACCUSATIVE, "множественное ветвление"),
        ("отслеженный вызов функции", GrammaticalCase.DATIVE, "отслеженному вызову функции"),
        ("Остановка цикла", GrammaticalCase.ACCUSATIVE, "Остановку цикла"),
        ("любое", GrammaticalCase.PREPOSITIONAL, "любом"),
    ],
)
def test_leading_noun_phrase_is_declined(text: str, case: GrammaticalCase, expected: str) -> None:
    assert decline(text, case) == expected


@pytest.mark.parametrize("text", ["<code>x</code> на строке 1", "statement", "True"])
def test_text_without_leading_russian_noun_phrase_is_unchanged(text: str) -> None:
    assert decline(text, GrammaticalCase.GENITIVE) == text
