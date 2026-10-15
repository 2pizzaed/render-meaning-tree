"""Сгенерировать учебные задачи по фрагменту и показать отобранные.

Печатает для каждой задачи вариант значений, N, Q, итоговые цепочки условий,
скиллы и концепты; логи pipeline (отказы с причинами и сводка) идут в stderr.
Нужен для подбора чисел ProblemGenerationConfig и разбора, почему фрагмент не дал задач.
С ``--output`` сохраняет задачи в каталог как вопросы CompPrehension
(SerializableQuestionTemplate), по файлу ``<questionName>.json`` на вопрос, как экспорт playground,
и сообщает в stdout, сколько вопросов сохранено и куда. Вывод в stdout - на английском.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import textwrap
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from src.generator.problems import (
    DEFAULT_SEED,
    LearningProblem,
    ProblemGenerationConfig,
)
from src.generator.utilities import (
    code_snippet_to_problem_pipeline,
    problems_to_question_templates,
)

DEFAULT_CONFIG = ProblemGenerationConfig()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    started = time.monotonic()
    pipeline = code_snippet_to_problem_pipeline(
        textwrap.dedent(_read_code(args)),
        language=args.language,
        seed=args.seed,
        config=replace(DEFAULT_CONFIG, top_k=args.top_k, selection=args.selection),
        origin=args.origin,
        origin_license=args.origin_license,
    )
    problems = pipeline.results()
    for problem in problems:
        print(_describe(problem))
    if args.output is not None:
        questions = problems_to_question_templates(pipeline, problems)
        _write_questions(args.output, questions)
        print(
            f"Export completed: {len(questions)} of {len(problems)} questions "
            f"saved to {args.output.resolve()}"
        )
    print(f"Problems: {len(problems)}, {time.monotonic() - started:.1f} s")
    return 0


def _write_questions(output_dir: Path, questions: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for question in questions:
        name = question["commonQuestion"]["questionData"]["questionName"]
        text = json.dumps(question, ensure_ascii=False, indent=2)
        (output_dir / f"{name}.json").write_text(text, encoding="utf-8")


def _describe(problem: LearningProblem) -> str:
    code = problem.registry.code
    chains = ", ".join(
        f"{role}@{code.code_line_number_by_id(ast_id) if ast_id else '?'}="
        + "".join("T" if value else "F" for value in values)
        for (_, ast_id, role), values in problem.values.items()
    )
    score = f"{problem.score:.3f}" if problem.score is not None else "-"
    return (
        f"[{problem.variant}] trace steps (N)={problem.steps}, selection score (Q)={score}, "
        f"cyclomatic complexity (M)={problem.cyclomatic_complexity}, "
        f"difficulty (complexity)={problem.complexity:.3f}\n"
        f"  values: {chains}\n"
        f"  skills: {', '.join(sorted(problem.skills))}\n"
        f"  concepts: {', '.join(sorted(problem.concepts))}"
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
    parser.add_argument(
        "--output",
        type=Path,
        help="Directory to save problems as CompPrehension question JSON files.",
    )
    parser.add_argument("--origin", help="Source of the code fragment for question metadata.")
    parser.add_argument(
        "--origin-license", help="License of the code fragment source. Requires --origin."
    )
    args = parser.parse_args(argv)
    if args.origin_license is not None and args.origin is None:
        parser.error("--origin-license requires --origin")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
