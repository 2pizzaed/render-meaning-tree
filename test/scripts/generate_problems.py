"""Сгенерировать учебные задачи по фрагменту и показать отобранные.

Печатает для каждой задачи вариант значений, N, Q, итоговые цепочки условий,
скиллы и концепты; логи pipeline (отказы с причинами и сводка) идут в stderr.
Нужен для подбора чисел ProblemGenerationConfig и разбора, почему фрагмент не дал задач.
"""

from __future__ import annotations

import argparse
import logging
import sys
import textwrap
import time
from dataclasses import replace
from pathlib import Path

from src.generator.problems import (
    DEFAULT_SEED,
    LearningProblem,
    ProblemGenerationConfig,
)
from src.generator.utilities import code_snippet_to_problems

DEFAULT_CONFIG = ProblemGenerationConfig()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    started = time.monotonic()
    problems = code_snippet_to_problems(
        textwrap.dedent(_read_code(args)),
        language=args.language,
        seed=args.seed,
        config=replace(DEFAULT_CONFIG, top_k=args.top_k, selection=args.selection),
    )
    for problem in problems:
        print(_describe(problem))
    print(f"задач: {len(problems)}, {time.monotonic() - started:.1f} с")
    return 0


def _describe(problem: LearningProblem) -> str:
    code = problem.registry.code
    chains = ", ".join(
        f"{role}@{code.code_line_number_by_id(ast_id) if ast_id else '?'}="
        + "".join("T" if value else "F" for value in values)
        for (ast_id, role), values in problem.values.items()
    )
    score = f"{problem.score:.3f}" if problem.score is not None else "-"
    return (
        f"[{problem.variant}] N={problem.steps} Q={score} M={problem.cyclomatic_complexity}\n"
        f"  значения: {chains}\n"
        f"  скиллы: {', '.join(sorted(problem.skills))}\n"
        f"  концепты: {', '.join(sorted(problem.concepts))}"
    )


def _read_code(args: argparse.Namespace) -> str:
    if args.code is not None:
        return args.code
    if args.code_file is not None:
        return args.code_file.read_text(encoding="utf-8")
    return sys.stdin.read()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate learning problems for a code fragment and print the selected ones."
    )
    parser.add_argument(
        "code_file",
        nargs="?",
        type=Path,
        help="Code fragment file. If omitted, code is read from stdin.",
    )
    parser.add_argument("--code", help="Code fragment text. Overrides stdin and code_file.")
    parser.add_argument(
        "--language",
        default="python",
        help="Source language passed to the MeaningTree converter.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Generation seed.")
    parser.add_argument(
        "--top-k", type=int, default=DEFAULT_CONFIG.top_k, help="Problems to select."
    )
    parser.add_argument(
        "--selection",
        choices=("score", "random"),
        default=DEFAULT_CONFIG.selection,
        help="Selection strategy: top-k by Q or k random problems.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
