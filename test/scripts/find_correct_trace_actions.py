from __future__ import annotations

import argparse
import sys
import tempfile
import textwrap
from pathlib import Path

from src.generator.helpers import action_line_position
from src.generator.pipeline import DomainDataGeneratorPipeline
from src.generator.utilities import code_snippet_to_pipeline
from src.helpers.tpg import solve_graph_full_reasoning
from test.helpers.env import resolve_project_root

TREE_NAME = "findCorrect"
DEFAULT_LOQI_FILENAME = "find-correct-trace.loqi"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    code = _read_code(args)
    rows = trace_action_rows(
        code,
        language=args.language,
        max_iterations=args.max_iterations,
        time_limit_seconds=args.time_limit,
        include_transparent=args.include_transparent,
    )

    print(", ".join(str(row) for row in rows))
    return 0


def trace_action_rows(
    code: str,
    *,
    language: str = "python",
    max_iterations: int = 100,
    time_limit_seconds: int = 30,
    include_transparent: bool = False,
) -> list[tuple[int, int, int]]:
    pipeline = build_correct_trace_pipeline(
        code,
        language=language,
        max_iterations=max_iterations,
        time_limit_seconds=time_limit_seconds,
    )
    registry = pipeline.flatten_results()[0]

    rows: list[tuple[int, int, int]] = []
    for trace_act in registry.trace_acts:
        position = action_line_position(
            registry,
            trace_act.action,
            include_transparent=include_transparent,
        )
        if position is None:
            continue
        rows.append((position.line_number, position.action_index, position.ast_id))
    return rows


def build_correct_trace_pipeline(
    code: str,
    *,
    language: str = "python",
    max_iterations: int = 100,
    time_limit_seconds: int = 30,
) -> DomainDataGeneratorPipeline:
    pipeline = code_snippet_to_pipeline(textwrap.dedent(code), language=language)
    pipeline.fork_enabled = False
    registry = pipeline.flatten_results()[0]
    if registry.trace_acts:
        registry.variables["P"] = registry.trace_acts[0]

    with tempfile.TemporaryDirectory(prefix="find-correct-trace-") as tmp:
        tmp_path = Path(tmp)
        with (tmp_path / "reasoner_output.jsonl").open("a", encoding="utf-8") as output:
            solve_graph_full_reasoning(
                tmp_path,
                pipeline,
                model_dir=resolve_project_root() / "domain",
                filename=DEFAULT_LOQI_FILENAME,
                tree=TREE_NAME,
                export_domain=True,
                debug_enabled=True,
                time_limit_seconds=time_limit_seconds,
                reasoner_output_stream=output,
                max_iterations=max_iterations,
            )
    return pipeline


def _read_code(args: argparse.Namespace) -> str:
    if args.code is not None:
        return args.code
    if args.code_file is not None:
        return args.code_file.read_text(encoding="utf-8")
    return sys.stdin.read()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run findCorrect.tpg until it finishes and print trace actions as "
            "(line_number, action_index, ast_id) tuples."
        )
    )
    parser.add_argument(
        "code_file",
        nargs="?",
        type=Path,
        help="Code fragment file. If omitted, code is read from stdin.",
    )
    parser.add_argument(
        "--code",
        help="Code fragment text. Overrides stdin and code_file.",
    )
    parser.add_argument(
        "--language",
        default="python",
        help="Source language passed to the MeaningTree converter.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=100,
        help="Maximum number of solve calls before failing.",
    )
    parser.add_argument(
        "--time-limit",
        type=int,
        default=30,
        help="Per-solve reasoner time limit in seconds.",
    )
    parser.add_argument(
        "--include-transparent",
        action="store_true",
        help="Include transparent actions when calculating action indexes.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
