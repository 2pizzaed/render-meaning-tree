"""Трассировщик сниппета для ``annotate_trace``: выполняется в отдельном процессе.

Только стандартная библиотека: процесс запускается с ``python -I``, и проекта на пути
импорта нет. Из stdin читается JSON ``{"code": …, "max_values": …}``, в stdout пишется JSON
``{"conditions": {ключ: [bool, …]}, "calls": {ключ: [подсказка, …]}, "error": str | None}``.
Ключи - позиции узлов ``ast`` (функции ``*_key``), по ним ``annotate_trace`` находит узлы
в своём разборе того же кода.

Условия ``if``/``elif``/``while`` оборачиваются записывающей функцией, итерируемое ``for`` -
генератором, который записывает ``T`` на каждый элемент и ``F`` при исчерпании (после
``break`` значения нет). В начало тела каждой ветви ``match`` вставляется отметка: выбранная
ветвь получает ``T``, проверенные до неё - ``F``. Вызовы функций сниппета ловит
``sys.monitoring`` по событию начала функции; место вызова - инструкция ``CALL`` вызывающего
кадра, её позиция совпадает с позицией узла ``ast.Call``.
"""

from __future__ import annotations

import ast
import io
import json
import reprlib
import sys
import traceback
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from inspect import (
    CO_ASYNC_GENERATOR,
    CO_COROUTINE,
    CO_GENERATOR,
    CO_VARARGS,
    CO_VARKEYWORDS,
)
from types import CodeType, FrameType
from typing import Any

SNIPPET_FILENAME = "<snippet>"
_COND = "__trace_cond__"
_ITER = "__trace_iter__"
_CASE = "__trace_case__"
# Генератор и сопрограмма начинают выполняться не в месте вызова, а при первом next().
_DEFERRED_START = CO_GENERATOR | CO_COROUTINE | CO_ASYNC_GENERATOR
_TOOL_ID = sys.monitoring.PROFILER_ID

_hint_repr = reprlib.Repr()
_hint_repr.maxstring = 20
_hint_repr.maxother = 20


def node_key(node: ast.stmt | ast.pattern) -> str:
    return f"{node.lineno}:{node.col_offset}"


def case_key(case: ast.match_case) -> str:
    """У ``match_case`` нет позиции, её заменяет позиция шаблона."""
    return node_key(case.pattern)


def call_key(node: ast.Call) -> str:
    return f"{node.lineno}:{node.col_offset}:{node.end_lineno}:{node.end_col_offset}"


def is_default_case(case: ast.match_case) -> bool:
    """Ветвь ``case _:`` - в MT ветвь по умолчанию, без условия.

    ``case x:`` тоже неопровержима, но MT разбирает её как обычную ветвь с условием.
    """
    return (
        _is_irrefutable(case)
        and isinstance(case.pattern, ast.MatchAs)
        and case.pattern.name is None
    )


def _is_irrefutable(case: ast.match_case) -> bool:
    pattern = case.pattern
    return (
        isinstance(pattern, ast.MatchAs)
        and pattern.pattern is None
        and case.guard is None
    )


def callee_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


class ChainLimitError(BaseException):
    """Цепочка длиннее лимита. Не ``Exception``, чтобы ``except Exception`` сниппета её не поймал."""


@dataclass(frozen=True, slots=True)
class _CallSite:
    key: str
    name: str
    is_method: bool


class _Tracer:
    def __init__(self, tree: ast.Module, max_values: int) -> None:
        self.max_values = max_values
        self.conditions: defaultdict[str, list[bool]] = defaultdict(list)
        self.calls: defaultdict[str, list[str]] = defaultdict(list)
        self._sites: dict[tuple[int | None, ...], _CallSite] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (name := callee_name(node)) is not None:
                position = (
                    node.lineno,
                    node.end_lineno,
                    node.col_offset,
                    node.end_col_offset,
                )
                self._sites[position] = _CallSite(
                    call_key(node), name, isinstance(node.func, ast.Attribute)
                )
        self._positions: dict[CodeType, list[tuple[int | None, ...]]] = {}

    def record_condition(self, key: str, value: bool) -> None:
        chain = self.conditions[key]
        chain.append(value)
        if len(chain) > self.max_values:
            raise ChainLimitError(
                f"условие в строке {key.split(':')[0]} вычислено больше {self.max_values} раз"
            )

    def cond(self, key: str, value: object) -> bool:
        # bool() вычисляется один раз, как у самого if/while.
        result = bool(value)
        self.record_condition(key, result)
        return result

    def iterate(self, key: str, iterable: Iterable[Any]) -> Iterator[Any]:
        for item in iterable:
            self.record_condition(key, True)
            yield item
        self.record_condition(key, False)

    def case(self, keys: tuple[str | None, ...], chosen: int | None) -> None:
        """Ветвь ``chosen`` выбрана (``None`` - ни одна), все ветви до неё не подошли."""
        checked = keys if chosen is None else keys[:chosen]
        for key in checked:
            if key is not None:
                self.record_condition(key, False)
        if chosen is not None and (key := keys[chosen]) is not None:
            self.record_condition(key, True)

    def on_start(self, code: CodeType, _offset: int) -> None:
        if code.co_filename != SNIPPET_FILENAME or code.co_flags & _DEFERRED_START:
            return
        frame = sys._getframe(1)
        caller = frame.f_back
        if caller is None or caller.f_code.co_filename != SNIPPET_FILENAME:
            return
        positions = self._positions.get(caller.f_code)
        if positions is None:
            positions = self._positions[caller.f_code] = list(
                caller.f_code.co_positions()
            )
        site = self._sites.get(positions[caller.f_lasti // 2])
        # Имя отсекает вызовы, которые начинают другой код: класс (A() -> __init__),
        # лямбду в переменной, тело класса при его определении.
        if site is None or site.name != code.co_name:
            return
        hints = self.calls[site.key]
        hints.append(_hint(site.name, frame, code, site.is_method))
        if len(hints) > self.max_values:
            raise ChainLimitError(
                f"вызов {site.name} в строке {site.key.split(':')[0]} "
                f"выполнен больше {self.max_values} раз"
            )


def _hint(name: str, frame: FrameType, code: CodeType, is_method: bool) -> str:
    """``имя(аргументы)``: значения параметров на входе в функцию, ``self`` метода опускается."""
    names = code.co_varnames
    positional = list(names[: code.co_argcount])
    keyword_only = names[code.co_argcount : code.co_argcount + code.co_kwonlyargcount]
    extra = code.co_argcount + code.co_kwonlyargcount
    if is_method and positional and positional[0] in ("self", "cls"):
        positional = positional[1:]
    values = frame.f_locals
    parts = [_hint_repr.repr(values[arg]) for arg in positional]
    if code.co_flags & CO_VARARGS:
        parts.extend(_hint_repr.repr(item) for item in values[names[extra]])
        extra += 1
    parts.extend(f"{arg}={_hint_repr.repr(values[arg])}" for arg in keyword_only)
    if code.co_flags & CO_VARKEYWORDS:
        parts.extend(
            f"{key}={_hint_repr.repr(value)}"
            for key, value in values[names[extra]].items()
        )
    return f"{name}({', '.join(parts)})"


class _Instrumenter(ast.NodeTransformer):
    def visit_If(self, node: ast.If) -> ast.If:
        self.generic_visit(node)
        node.test = _helper_call(
            _COND, node.test, ast.Constant(node_key(node)), node.test
        )
        return node

    def visit_While(self, node: ast.While) -> ast.While:
        self.generic_visit(node)
        node.test = _helper_call(
            _COND, node.test, ast.Constant(node_key(node)), node.test
        )
        return node

    def visit_For(self, node: ast.For) -> ast.For:
        self.generic_visit(node)
        node.iter = _helper_call(
            _ITER, node.iter, ast.Constant(node_key(node)), node.iter
        )
        return node

    def visit_Match(self, node: ast.Match) -> ast.Match:
        self.generic_visit(node)
        keys = [
            None if is_default_case(case) else case_key(case) for case in node.cases
        ]
        key_tuple = ast.Tuple([ast.Constant(key) for key in keys], ast.Load())
        for index, case in enumerate(node.cases):
            mark = _helper_call(_CASE, case.body[0], key_tuple, ast.Constant(index))
            case.body.insert(0, ast.copy_location(ast.Expr(mark), case.body[0]))
        # Отметка «ни одна ветвь не подошла»; после неопровержимой ветви ветвь - ошибка синтаксиса.
        if not _is_irrefutable(node.cases[-1]):
            last = node.cases[-1]
            mark = _helper_call(_CASE, last.body[-1], key_tuple, ast.Constant(None))
            body = ast.copy_location(ast.Expr(mark), last.body[-1])
            node.cases.append(
                ast.match_case(
                    ast.copy_location(ast.MatchAs(), last.pattern), None, [body]
                )
            )
        return node


def _helper_call(name: str, location: ast.AST, *args: ast.expr) -> ast.Call:
    call = ast.Call(ast.Name(name, ast.Load()), list(args), [])
    return ast.fix_missing_locations(ast.copy_location(call, location))


def trace(code: str, max_values: int) -> dict[str, Any]:
    tree = ast.parse(code, SNIPPET_FILENAME)
    tracer = _Tracer(tree, max_values)
    compiled = compile(
        ast.fix_missing_locations(_Instrumenter().visit(tree)), SNIPPET_FILENAME, "exec"
    )
    namespace = {
        "__name__": "__main__",
        _COND: tracer.cond,
        _ITER: tracer.iterate,
        _CASE: tracer.case,
    }
    error = None
    sys.monitoring.use_tool_id(_TOOL_ID, "annotate-trace")
    sys.monitoring.register_callback(
        _TOOL_ID, sys.monitoring.events.PY_START, tracer.on_start
    )
    sys.monitoring.set_events(_TOOL_ID, sys.monitoring.events.PY_START)
    try:
        exec(compiled, namespace)  # noqa: S102 - выполнить сниппет и есть задача трассировщика
    except ChainLimitError as limit:
        error = str(limit)
    except EOFError as exc:
        error = f"{_snippet_line(exc)}сниппет ждёт ввода, а ввода нет"
    except BaseException as exc:  # noqa: BLE001 - любое завершение сниппета с ошибкой - отказ
        error = f"{_snippet_line(exc)}{type(exc).__name__}: {exc}"
    finally:
        sys.monitoring.set_events(_TOOL_ID, 0)
        sys.monitoring.free_tool_id(_TOOL_ID)
    return {"conditions": tracer.conditions, "calls": tracer.calls, "error": error}


def _snippet_line(exc: BaseException) -> str:
    lines = [
        frame.lineno
        for frame in traceback.extract_tb(exc.__traceback__)
        if frame.filename == SNIPPET_FILENAME
    ]
    return f"строка {lines[-1]}: " if lines else ""


def main() -> None:
    request = json.loads(sys.stdin.read())
    # Ввод прочитан до конца: input() сниппета получит EOFError, а не зависнет.
    sys.stdin = io.StringIO()
    output = sys.stdout
    sys.stdout = io.StringIO()
    result = trace(request["code"], request["max_values"])
    # JSON в ASCII: кодировка stdout процесса зависит от системы (cp1251 в Windows).
    output.write(json.dumps(result))


if __name__ == "__main__":
    main()
