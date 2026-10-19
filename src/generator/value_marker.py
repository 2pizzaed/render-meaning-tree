"""Синтаксис маркера значений ``<! … >``.

Комментарий-маркер - одна или несколько меток ``<! … >`` подряд: в Python на строке
только один комментарий, а размечать на строке может понадобиться условие и вызовы.
Содержимое метки - необязательная цель ``имя:`` или ``имя#k:`` (k-й по тексту вызов
функции ``имя`` на строке) и значения в одной из двух форм:

- краткая ``TTF``: только значения;
- список кортежей ``(T, "f(1)"), (F, "f(2)")``: значение и подсказка (hint) для
  SemanticValue. Подсказка - строковый литерал в синтаксисе JSON. Вместо ``T``/``F``
  можно написать ``-``: значение без логического смысла (``null``), например
  аннотация вызова ``(-, "f(2)")``.

Пробелы вокруг скобок, запятых, двоеточия и меток допускаются.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

# Комментарий, похожий на маркер; содержимое проверяется отдельно, чтобы опечатка
# в маркере давала ошибку, а не превращала его в обычный комментарий.
_MARKER_RE = re.compile(r"^\s*<!.*>\s*$", re.DOTALL)
_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')
_TARGET_RE = re.compile(r"\s*(?P<name>[A-Za-z_]\w*)\s*(?:#\s*(?P<index>\d+)\s*)?:")
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
class CallTarget:
    """Вызов функции ``name`` на строке; ``index`` - номер среди них по тексту, с 1."""

    name: str
    index: int | None = None


@dataclass(frozen=True, slots=True)
class Marker:
    """Одна метка ``<! … >`` комментария-маркера."""

    values: tuple[MarkerValue, ...]
    target: CallTarget | None = None


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str


def is_value_marker(content: str) -> bool:
    return _MARKER_RE.match(content) is not None


def parse_value_markers(content: str) -> tuple[Marker, ...] | None:
    """Метки комментария; ``None``, если комментарий не маркер.

    Некорректное содержимое маркера - ``ValueMarkerSyntaxError``.
    """
    if not is_value_marker(content):
        return None
    return tuple(_parse_marker(body) for body in _split_markers(content))


def format_value_marker(marker: Marker) -> str:
    """Каноническая запись метки для сообщений."""
    values = marker.values
    if all(item.hint is None for item in values):
        body = "".join(format_flag(item.value) for item in values)
    else:
        body = ", ".join(
            f"({format_flag(item.value)}, {json.dumps(item.hint, ensure_ascii=False)})"
            for item in values
        )
    target = marker.target
    if target is not None:
        index = f"#{target.index}" if target.index is not None else ""
        body = f"{target.name}{index}: {body}"
    return f"<! {body} >"


def _split_markers(content: str) -> list[str]:
    """Содержимое меток ``<! … >``; ``>`` внутри строки-подсказки метку не закрывает.

    Маркер кончается на ``>`` вне строки, поэтому закрывающая ``>`` у метки есть всегда.
    """
    bodies: list[str] = []
    position = 0
    while content[position:].strip():
        start = len(content) - len(content[position:].lstrip())
        if not content.startswith("<!", start):
            raise ValueMarkerSyntaxError(
                f"между метками непонятный фрагмент «{content[start:].strip()}»"
            )
        position = start + 2
        while position < len(content) and content[position] != ">":
            string = _STRING_RE.match(content, position) if content[position] == '"' else None
            position = string.end() if string is not None else position + 1
        bodies.append(content[start + 2 : position])
        position += 1
    return bodies


def _parse_marker(body: str) -> Marker:
    target = None
    if match := _TARGET_RE.match(body):
        index = match.group("index")
        if index is not None and int(index) == 0:
            raise ValueMarkerSyntaxError("вызовы на строке нумеруются с 1")
        target = CallTarget(match.group("name"), int(index) if index is not None else None)
        body = body[match.end() :]
    if _SHORT_FORM_RE.fullmatch(body):
        return Marker(tuple(MarkerValue(char == "T") for char in body.strip()), target)
    return Marker(_parse_tuples(_tokenize(body)), target)


def format_flag(value: bool | None) -> str:
    """Значение в записи маркера: ``T``, ``F`` или ``-`` для ``null``."""
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
