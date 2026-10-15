"""Синтаксис маркера значений ``<! … >``.

Содержимое маркера - одна из двух форм:

- краткая ``TTF``: только значения;
- список кортежей ``(T, "f(1)"), (F, "f(2)")``: значение и подсказка (hint) для
  SemanticValue. Подсказка - строковый литерал в синтаксисе JSON. Вместо ``T``/``F``
  можно написать ``-``: значение без логического смысла (``null``), например
  аннотация вызова ``(-, "f(2)")``.

Пробелы вокруг скобок и запятых допускаются.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

# Комментарий, похожий на маркер; содержимое проверяется отдельно, чтобы опечатка
# в маркере давала ошибку, а не превращала его в обычный комментарий.
_MARKER_RE = re.compile(r"^\s*<!(?P<body>.*)>\s*$", re.DOTALL)
_SHORT_FORM_RE = re.compile(r"\s*[TF]+\s*")
_TOKEN_RE = re.compile(
    r'\s*(?:(?P<punct>[(),])|(?P<flag>[TF]\b|-)|(?P<string>"(?:[^"\\]|\\.)*"))'
)
_FLAG_VALUES: dict[str, bool | None] = {"T": True, "F": False, "-": None}


class ValueMarkerSyntaxError(ValueError):
    """Содержимое маркера не соответствует синтаксису; сообщение - причина."""


@dataclass(frozen=True, slots=True)
class MarkerValue:
    value: bool | None
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str


def is_value_marker(content: str) -> bool:
    return _MARKER_RE.match(content) is not None


def parse_value_marker(content: str) -> tuple[MarkerValue, ...] | None:
    """Значения маркера; ``None``, если комментарий не маркер.

    Некорректное содержимое маркера - ``ValueMarkerSyntaxError``.
    """
    marker = _MARKER_RE.match(content)
    if marker is None:
        return None
    body = marker.group("body")
    if _SHORT_FORM_RE.fullmatch(body):
        return tuple(MarkerValue(char == "T") for char in body.strip())
    return _parse_tuples(_tokenize(body))


def format_value_marker(values: Sequence[MarkerValue]) -> str:
    """Каноническая запись маркера для сообщений."""
    if all(item.hint is None for item in values):
        body = "".join(_flag(item.value) for item in values)
    else:
        body = ", ".join(
            f"({_flag(item.value)}, {json.dumps(item.hint, ensure_ascii=False)})"
            for item in values
        )
    return f"<! {body} >"


def _flag(value: bool | None) -> str:
    if value is None:
        return "-"
    return "T" if value else "F"


def _tokenize(body: str) -> list[_Token]:
    tokens: list[_Token] = []
    position = 0
    while body[position:].strip():
        match = _TOKEN_RE.match(body, position)
        if match is None or match.lastgroup is None:
            raise ValueMarkerSyntaxError(f"непонятный фрагмент «{body[position:].strip()}»")
        tokens.append(_Token(match.lastgroup, match.group(match.lastgroup)))
        position = match.end()
    if not tokens:
        raise ValueMarkerSyntaxError("пустая разметка")
    return tokens


def _parse_tuples(tokens: list[_Token]) -> tuple[MarkerValue, ...]:
    """``кортеж (, кортеж)*``."""
    values: list[MarkerValue] = []
    index = 0
    while True:
        args, index = _parse_tuple(tokens, index)
        values.append(_marker_value(args))
        if index == len(tokens):
            return tuple(values)
        index = _expect(tokens, index, ",")


def _parse_tuple(tokens: list[_Token], index: int) -> tuple[list[_Token], int]:
    """``( аргумент (, аргумент)* )``; состав аргументов проверяет ``_marker_value``."""
    index = _expect(tokens, index, "(")
    args: list[_Token] = []
    while True:
        if index == len(tokens) or tokens[index].kind == "punct":
            raise ValueMarkerSyntaxError(f"ожидался аргумент кортежа, а не {_describe(tokens, index)}")
        args.append(tokens[index])
        index += 1
        if index < len(tokens) and tokens[index].text == ")":
            return args, index + 1
        index = _expect(tokens, index, ",")


def _marker_value(args: list[_Token]) -> MarkerValue:
    match args:
        case [_Token("flag", flag), _Token("string", literal)]:
            try:
                hint = json.loads(literal)
            except json.JSONDecodeError as error:
                raise ValueMarkerSyntaxError(f"некорректная строка {literal}") from error
            return MarkerValue(_FLAG_VALUES[flag], hint)
        case _:
            written = ", ".join(token.text for token in args)
            raise ValueMarkerSyntaxError(f'кортеж ({written}) не в форме (T|F|-, "подсказка")')


def _expect(tokens: list[_Token], index: int, text: str) -> int:
    if index == len(tokens) or tokens[index].text != text:
        raise ValueMarkerSyntaxError(f"ожидалось «{text}», а не {_describe(tokens, index)}")
    return index + 1


def _describe(tokens: list[_Token], index: int) -> str:
    return f"«{tokens[index].text}»" if index < len(tokens) else "конец разметки"
