"""Разметить Python-сниппет метками ``<! … >`` по реальной трассе его выполнения.

Сниппет выполняется в отдельном процессе (``trace_runner``), и по трассе в конец строк
дописываются метки в синтаксисе ``docs/ideas/value_annotations_idea.md``: цепочки ``T``/``F``
условий ``if``/``elif``/``while``/``for`` и ветвей ``match``, подсказки вызовов функций
сниппета ``(-, "fib(2)")``. Цель вызова (``fib`` или ``fib#2``) ставится, только если без неё
вызов на строке неоднозначен. Условие, которое ни разу не вычислялось, и вызов, который ни
разу не выполнялся, меток не получают.

Ошибка (``AnnotateTraceError``): в сниппете уже есть разметка, оператор стоит на строке не
один (``a = 1; b = 2``, ``if x: y = 1``), у ветви ``match`` есть охрана, на строке метки уже
есть комментарий, сниппет ждёт ввода, падает, не укладывается во время или цепочка длиннее
лимита.
"""

from __future__ import annotations

import argparse
import ast
import bisect
import io
import json
import logging
import subprocess
import sys
import tokenize
from collections import Counter, defaultdict
from pathlib import Path

from src.generator.value_marker import (
    CallTarget,
    Marker,
    MarkerValue,
    format_value_marker,
    is_value_marker,
)
from test.tools.trace_runner import (
    call_key,
    callee_name,
    case_key,
    is_default_case,
    node_key,
)

DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_VALUES = 100
_RUNNER = Path(__file__).with_name("trace_runner.py")
# Вызовы в заголовке определения (декоратор, значение по умолчанию, базовый класс)
# выполняются при определении, генератор их не трассирует.
_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

logger = logging.getLogger(__name__)


class AnnotateTraceError(ValueError):
    """Сниппет нельзя разметить; сообщение готово для вывода."""


def annotate(
    code: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_values: int = DEFAULT_MAX_VALUES,
) -> str:
    """Текст сниппета с метками по трассе его выполнения."""
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    try:
        tree = ast.parse(code)
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except (SyntaxError, tokenize.TokenError) as error:
        raise AnnotateTraceError(f"сниппет не разбирается: {error}") from error
    lines = code.split("\n")
    comments = {
        token.start[0]: token.string
        for token in tokens
        if token.type == tokenize.COMMENT
    }
    for line, comment in comments.items():
        if is_value_marker(comment.removeprefix("#")):
            raise AnnotateTraceError(
                f"строка {line}: в сниппете уже есть разметка {comment}"
            )
    _check_supported(tree, lines)

    conditions, calls = _run_tracer(code, timeout, max_values)
    layout = _Layout(tree, tokens)
    markers: defaultdict[int, list[str]] = defaultdict(list)
    for line, values in layout.condition_markers(conditions):
        markers[line].append(
            format_value_marker(Marker(tuple(MarkerValue(v) for v in values)))
        )
    for line, marker in layout.call_markers(calls):
        markers[line].append(format_value_marker(marker))

    for line, line_markers in markers.items():
        if line in comments:
            raise AnnotateTraceError(
                f"строка {line}: метке {line_markers[0]} мешает комментарий {comments[line]}"
            )
        lines[line - 1] = f"{lines[line - 1].rstrip()}  # {' '.join(line_markers)}"
    return "\n".join(lines)


def _check_supported(tree: ast.Module, lines: list[str]) -> None:
    """Каждый оператор - на своей строке, у ветвей ``match`` нет охраны.

    Комментарий в конце строки MT отдаёт последнему оператору строки, а не заголовку
    ``if x: y = 1`` или первому из ``a = 1; b = 2``, и метка не привяжется. Охрану
    ``case 1 if x:`` MT отбрасывает, и трасса генератора разошлась бы с реальной.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.match_case) and node.guard is not None:
            raise AnnotateTraceError(
                f"строка {node.guard.lineno}: охрана case ({ast.unparse(node.guard)}) "
                "не поддерживается: Meaning Tree её отбрасывает"
            )
        if isinstance(node, ast.stmt):
            # col_offset у ast - в байтах UTF-8.
            before = lines[node.lineno - 1].encode()[: node.col_offset].decode().strip()
            if before:
                raise AnnotateTraceError(
                    f"строка {node.lineno}: оператор должен начинать строку, а перед ним «{before}»"
                )


def _run_tracer(
    code: str, timeout: float, max_values: int
) -> tuple[dict[str, list[bool]], dict[str, list[str]]]:
    # Запрос и ответ - JSON в ASCII, поэтому кодировка потоков процесса не важна.
    request = json.dumps({"code": code, "max_values": max_values})
    try:
        process = subprocess.run(
            [sys.executable, "-I", str(_RUNNER)],
            input=request,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise AnnotateTraceError(
            f"сниппет не завершился за {timeout:g} с (бесконечный цикл или блокирующий вызов)"
        ) from error
    if process.returncode != 0:
        raise AnnotateTraceError(f"трассировщик упал: {process.stderr.strip()}")
    result = json.loads(process.stdout)
    if result["error"] is not None:
        raise AnnotateTraceError(result["error"])
    return result["conditions"], result["calls"]


class _Layout:
    """Строки меток: по узлам ``ast`` того же кода, что разобрал трассировщик."""

    def __init__(self, tree: ast.Module, tokens: list[tokenize.TokenInfo]) -> None:
        self._tree = tree
        self._colon_lines = sorted(
            token.start[0]
            for token in tokens
            if token.type == tokenize.OP and token.string == ":"
        )
        self._parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        self._functions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def condition_markers(
        self, chains: dict[str, list[bool]]
    ) -> list[tuple[int, list[bool]]]:
        """Метки условий: в строке заголовка конструкции."""
        markers: list[tuple[int, list[bool]]] = []
        for node in ast.walk(self._tree):
            if isinstance(node, (ast.If, ast.While, ast.For)):
                key, header = node_key(node), self._header_line(node.body[0].lineno)
            elif isinstance(node, ast.match_case) and not is_default_case(node):
                key, header = case_key(node), self._header_line(node.body[0].lineno)
            else:
                continue
            if chains.get(key):
                markers.append((header, chains[key]))
        return markers

    def call_markers(self, hints: dict[str, list[str]]) -> list[tuple[int, Marker]]:
        """Метки выполненных вызовов функций сниппета, с целью при неоднозначности."""
        by_line: defaultdict[int, list[ast.Call]] = defaultdict(list)
        for node in ast.walk(self._tree):
            if isinstance(node, ast.Call) and callee_name(node) in self._functions:
                line = self._call_line(node)
                if line is None:
                    continue
                if node.lineno <= line <= (node.end_lineno or node.lineno):
                    by_line[line].append(node)
                elif call_key(node) in hints:
                    logger.warning(
                        "строка %d: вызов %s не занимает строку %d, где метка привязалась бы к нему; "
                        "вызов не размечен",
                        node.lineno,
                        ast.unparse(node),
                        line,
                    )

        markers: list[tuple[int, Marker]] = []
        for line, calls in sorted(by_line.items()):
            calls.sort(key=lambda call: (call.lineno, call.col_offset))
            names = Counter(callee_name(call) for call in calls)
            seen: Counter[str | None] = Counter()
            for call in calls:
                name = callee_name(call)
                seen[name] += 1
                if call_key(call) not in hints:
                    continue
                values = tuple(
                    MarkerValue(None, hint) for hint in hints[call_key(call)]
                )
                target = None
                if len(calls) > 1 and name is not None:
                    target = CallTarget(name, seen[name] if names[name] > 1 else None)
                markers.append((line, Marker(values, target)))
        return markers

    def _call_line(self, call: ast.Call) -> int | None:
        """Строка, где метка привяжется к вызову: заголовок конструкции или конец оператора."""
        current: ast.AST = call
        while (parent := self._parents.get(current)) is not None:
            if isinstance(parent, ast.stmt):
                if isinstance(parent, _DEFINITIONS):
                    return None
                body = getattr(parent, "body", None) or getattr(parent, "cases", None)
                if body:
                    first = (
                        body[0].pattern if isinstance(parent, ast.Match) else body[0]
                    )
                    return self._header_line(first.lineno)
                return parent.end_lineno
            current = parent
        return None

    def _header_line(self, body_line: int) -> int:
        """Строка двоеточия заголовка: последнего ``:`` перед первой строкой тела."""
        return self._colon_lines[bisect.bisect_left(self._colon_lines, body_line) - 1]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    code = (
        args.code_file.read_text(encoding="utf-8")
        if args.code_file
        else sys.stdin.read()
    )
    try:
        # Текст выводится как есть: перевод строки в конце сохраняется из сниппета.
        sys.stdout.write(annotate(code, timeout=args.timeout, max_values=args.max_values))
    except AnnotateTraceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Annotate a Python snippet with <! … > value markers from its real execution trace."
    )
    parser.add_argument(
        "code_file",
        nargs="?",
        type=Path,
        help="Python snippet file. If omitted, code is read from stdin.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Seconds the snippet may run before tracing fails.",
    )
    parser.add_argument(
        "--max-values",
        type=int,
        default=DEFAULT_MAX_VALUES,
        help="Maximum chain length of one condition or call.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
