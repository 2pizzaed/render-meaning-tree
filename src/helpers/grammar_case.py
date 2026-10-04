"""Склонение русских имён объектов по падежам (pymorphy3, словарь ru).

Имя объекта — именная группа с хвостом, например ``цикл <code>while</code>
на строке 5`` или ``условие существования следующего элемента``. Склоняется
только начальная группа: согласованные прилагательные/причастия и главное
существительное в именительном падеже. Всё после неё (дополнения в родительном
падеже, HTML-разметка, «на строке N») остаётся как есть. Текст, который не
начинается с такой группы, возвращается без изменений.
"""

from __future__ import annotations

import re
from enum import StrEnum
from functools import cache

import pymorphy3
from pymorphy3.analyzer import Parse


class GrammaticalCase(StrEnum):
    """Падеж; значение — граммема pymorphy3."""

    NOMINATIVE = "nomn"
    GENITIVE = "gent"
    DATIVE = "datv"
    ACCUSATIVE = "accs"
    INSTRUMENTAL = "ablt"
    PREPOSITIONAL = "loct"

    @classmethod
    def parse(cls, label: str) -> GrammaticalCase:
        """Падеж по первой букве русского названия (``'р'``, ``'родительный'``) или граммеме."""
        label = label.strip().lower()
        return _CASES_BY_LETTER.get(label[:1]) or cls(label)  # ValueError для неизвестного


_CASES_BY_LETTER = {
    "и": GrammaticalCase.NOMINATIVE,
    "р": GrammaticalCase.GENITIVE,
    "д": GrammaticalCase.DATIVE,
    "в": GrammaticalCase.ACCUSATIVE,
    "т": GrammaticalCase.INSTRUMENTAL,
    "п": GrammaticalCase.PREPOSITIONAL,
}

_WORD_RE = re.compile(r"\s*(?P<word>[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*)")
_ADJECTIVES = frozenset({"ADJF", "PRTF"})


@cache
def _morph() -> pymorphy3.MorphAnalyzer:
    return pymorphy3.MorphAnalyzer(lang="ru")


def decline(text: str, case: GrammaticalCase) -> str:
    """``text`` с начальной именной группой в падеже ``case``."""
    if case is GrammaticalCase.NOMINATIVE:
        return text
    group: list[tuple[re.Match[str], Parse]] = []
    pos = 0
    while (match := _WORD_RE.match(text, pos)) is not None:
        parse = _nominative_parse(match["word"])
        if parse is None:
            break
        group.append((match, parse))
        pos = match.end()
        if parse.tag.POS == "NOUN":
            break
    if not group:
        return text

    animacy = group[-1][1].tag.animacy
    parts: list[str] = []
    last = 0
    for match, parse in group:
        grammemes = {case.value}
        # Винительный прилагательных мужского рода и мн. числа зависит от одушевлённости.
        if case is GrammaticalCase.ACCUSATIVE and animacy is not None and (
            parse.tag.gender == "masc" or parse.tag.number == "plur"
        ):
            grammemes.add(animacy)
        inflected = parse.inflect(grammemes)
        if inflected is None:
            return text
        parts += [text[last : match.start("word")], _same_capitalization(match["word"], inflected.word)]
        last = match.end()
    return "".join(parts) + text[last:]


def _nominative_parse(word: str) -> Parse | None:
    """Разбор слова как существительного или прилагательного в именительном падеже."""
    return next(
        (
            parse
            for parse in _morph().parse(word)
            if "nomn" in parse.tag and (parse.tag.POS == "NOUN" or parse.tag.POS in _ADJECTIVES)
        ),
        None,
    )


def _same_capitalization(original: str, word: str) -> str:
    return word[:1].upper() + word[1:] if original[:1].isupper() else word


__all__ = ["GrammaticalCase", "decline"]
