"""Сгенерировать учебные задачи по фрагменту или каталогу фрагментов.

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
from src.generator.value_marker import format_flag
from src.types import SNIPPET_LANGUAGES_BY_SUFFIX

DEFAULT_CONFIG = ProblemGenerationConfig()
logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.code is None and args.code_file is not None and args.code_file.is_dir():
        return _generate_directory(args.code_file, args)
    _generate_problems(_read_code(args), args, args.output)
    return 0


def _generate_directory(directory: Path, args: argparse.Namespace) -> int:
    started = time.monotonic()
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file()
        and SNIPPET_LANGUAGES_BY_SUFFIX.get(path.suffix.lower()) == args.language
    )
    if not files:
        logger.error("No %s snippets found in %s", args.language, directory)
        return 1

    total_problems = total_questions = failed = 0
    for index, path in enumerate(files, start=1):
        relative_path = path.relative_to(directory)
        print(f"[{index}/{len(files)}] {relative_path}", flush=True)
        # Вопросы всех сниппетов — в одном каталоге, имя файла начинается с пути сниппета.
        prefix = "__".join(relative_path.with_suffix("").parts) + "__"
        try:
            problems, questions = _generate_problems(
                path.read_text(encoding="utf-8"), args, args.output, prefix
            )
        except Exception:
            logger.exception("Failed to generate problems for %s", path)
            failed += 1
            continue
        total_problems += problems
        total_questions += questions
    print(
        f"Batch completed: {len(files) - failed}/{len(files)} snippets processed, "
        f"{failed} failed, {total_problems} problems, {total_questions} questions saved, "
        f"{time.monotonic() - started:.1f} s"
    )
    return 1 if failed else 0


def _generate_problems(
    code: str, args: argparse.Namespace, output: Path | None, prefix: str = ""
) -> tuple[int, int]:
    started = time.monotonic()
    pipeline = code_snippet_to_problem_pipeline(
        textwrap.dedent(code),
        language=args.language,
        seed=args.seed,
        config=replace(DEFAULT_CONFIG, top_k=args.top_k, selection=args.selection),
        origin=args.origin,
        origin_license=args.origin_license,
        target_language=args.target_language,
    )
    problems = pipeline.results()
    for problem in problems:
        print(_describe(problem))
    saved = 0
    if output is not None:
        questions = problems_to_question_templates(pipeline, problems)
        _write_questions(output, questions, prefix)
        saved = len(questions)
        print(
            f"Export completed: {len(questions)} of {len(problems)} questions "
            f"saved to {output.resolve()}"
        )
    print(f"Problems: {len(problems)}, {time.monotonic() - started:.1f} s")
    return len(problems), saved


def _write_questions(output_dir: Path, questions: list[dict[str, Any]], prefix: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for question in questions:
        name = question["commonQuestion"]["questionData"]["questionName"]
        text = json.dumps(question, ensure_ascii=False, indent=2)
        (output_dir / f"{prefix}{name}.json").write_text(text, encoding="utf-8")


def _describe(problem: LearningProblem) -> str:
    code = problem.registry.code
    chains = ", ".join(
        f"{role}@{code.code_line_number_by_id(ast_id) if ast_id else '?'}="
        + "".join(format_flag(value) for value in values)
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
        description="Generate learning problems for a code fragment or directory of snippets."
    )
    parser.add_argument(
        "code_file",
        nargs="?",
        type=Path,
        help="Code fragment file or directory (searched recursively for --language files). "
        "If omitted, code is read from stdin.",
    )
    parser.add_argument(
        "--code", help="Code fragment text. Overrides stdin and code_file."
    )
    parser.add_argument(
        "--language",
        default="python",
        help="Source language passed to MeaningTree; also filters directory files "
        "by extension (default: python).",
    )
    parser.add_argument(
        "--target-language",
        choices=("java", "python", "c++"),
        help="Language of the problem code: the fragment is translated by MeaningTree "
        "(default: source language).",
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help="Generation seed."
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_CONFIG.top_k,
        help="Problems to select per snippet.",
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
        help="Directory to save CompPrehension question JSON files. For directory input, "
        "file names of each snippet's questions start with its relative path "
        "without extension, with '__' between path parts and before the question name.",
    )
    parser.add_argument(
        "--origin", help="Source of the code fragment for question metadata."
    )
    parser.add_argument(
        "--origin-license",
        help="License of the code fragment source. Requires --origin.",
    )
    args = parser.parse_args(argv)
    if args.origin_license is not None and args.origin is None:
        parser.error("--origin-license requires --origin")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
