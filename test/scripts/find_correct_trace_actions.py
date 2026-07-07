from __future__ import annotations

import argparse
import sys
import tempfile
import textwrap
from pathlib import Path

from src.generator.helpers import action_line_position
from src.generator.pipeline import DomainDataGeneratorPipeline
from src.generator.utilities import code_snippet_to_pipeline
from src.helpers.tpg import PipelineReasoningOutput, solve_pipeline_reasoning
from src.model.situation import Action, TraceAct
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
    pipeline = code_snippet_to_pipeline(textwrap.dedent(code), language=language)
    pipeline.fork_enabled = False
    registry = pipeline.flatten_results()[0]
    if registry.trace_acts:
        registry.variables["P"] = registry.trace_acts[0]

    with tempfile.TemporaryDirectory(prefix="find-correct-trace-") as tmp:
        tmp_path = Path(tmp)
        previous_trace_length = len(registry.trace_acts)

        for _iteration in range(max_iterations):
            reasoning = _solve_once(
                tmp_path,
                pipeline,
                time_limit_seconds=time_limit_seconds,
            )

            if len(reasoning.trace_acts) <= previous_trace_length:
                raise RuntimeError(
                    "findCorrect solve did not append a trace action before reaching END"
                )
            previous_trace_length = len(reasoning.trace_acts)

            current_trace_act = registry.variables.get("P")
            current_action = (
                current_trace_act.action
                if isinstance(current_trace_act, TraceAct)
                else reasoning.trace_acts[-1].action
            )
            if _is_root_end_action(pipeline, current_action):
                break
        else:
            raise RuntimeError(
                f"findCorrect did not finish after {max_iterations} iteration(s)"
            )

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


def _solve_once(
    tmp_path: Path,
    pipeline: DomainDataGeneratorPipeline,
    *,
    time_limit_seconds: int,
) -> PipelineReasoningOutput:
    with (tmp_path / "reasoner_output.jsonl").open("a", encoding="utf-8") as output:
        reasoning = solve_pipeline_reasoning(
            tmp_path,
            pipeline,
            model_dir=resolve_project_root() / "domain",
            filename=DEFAULT_LOQI_FILENAME,
            tree=TREE_NAME,
            export_domain=True,
            debug_enabled=True,
            time_limit_seconds=time_limit_seconds,
            reasoner_output_stream=output,
        )
    if reasoning.result.result is not True or reasoning.result.exceptions:
        raise RuntimeError(f"findCorrect solve failed: {reasoning.result}")
    if reasoning.exported_loqi is None:
        raise RuntimeError("findCorrect solve did not export specificDomain")
    return reasoning


def _is_root_end_action(
    pipeline: DomainDataGeneratorPipeline,
    action: Action,
) -> bool:
    entry_point_id = pipeline.code.ast.find_paths_by_type("program_entry_point")[0].id
    entry_point = pipeline.get_construct_for(entry_point_id)
    if entry_point is None:
        return False
    return (
        action.rule.role == "END"
        and entry_point.rule.name == "global_statements_structure"
        and action.ast_id == entry_point.ast_id
    )


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
