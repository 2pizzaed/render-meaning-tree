from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from src.generator.pipeline import DomainDataGeneratorPipeline
from src.generator.utilities import pipeline_to_loqi
from src.helpers.tpg.trace import restore_trace_from_loqi
from src.model.situation import Action, TraceAct, TraceState
from src.serialization.loqi import LoqiSerializer
from src.tpg_domain import ReasoningResult, solve_reasoning


@dataclass(frozen=True, slots=True)
class PipelineReasoningOutput:
    serializer: LoqiSerializer
    loqi_file: Path
    loqi_text: str
    result: ReasoningResult
    exported_loqi: str | None
    trace_acts: list[TraceAct]
    trace_state: TraceState | None


def solve_pipeline_reasoning(
    directory: Path,
    pipeline: DomainDataGeneratorPipeline,
    *,
    model_dir: str | Path,
    filename: str = "generated-domain.loqi",
    tag: str | None = None,
    tree: str | None = None,
    verbose: bool = False,
    json_trace: bool = False,
    debug_enabled: bool = True,
    export_domain: bool = True,
    time_limit_seconds: int | None = None,
    reasoner_output_stream: TextIO | None = None,
    restore_exported_trace: bool = True,
) -> PipelineReasoningOutput:
    return _solve_pipeline_reasoning_once(
        directory,
        pipeline,
        model_dir=model_dir,
        filename=filename,
        tag=tag,
        tree=tree,
        verbose=verbose,
        json_trace=json_trace,
        debug_enabled=debug_enabled,
        export_domain=export_domain,
        time_limit_seconds=time_limit_seconds,
        reasoner_output_stream=reasoner_output_stream,
        restore_exported_trace=restore_exported_trace,
    )


def solve_graph_full_reasoning(
    directory: Path,
    pipeline: DomainDataGeneratorPipeline,
    *,
    model_dir: str | Path,
    filename: str = "generated-domain.loqi",
    tag: str | None = None,
    tree: str | None = "findCorrect",
    verbose: bool = False,
    json_trace: bool = False,
    debug_enabled: bool = True,
    export_domain: bool = True,
    time_limit_seconds: int | None = None,
    reasoner_output_stream: TextIO | None = None,
    max_iterations: int = 100,
    solver_stops: set[int] | None = None,
) -> PipelineReasoningOutput:
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")

    registry = pipeline.registry
    previous_trace_length = len(registry.trace_acts)
    last_output: PipelineReasoningOutput | None = None

    for _iteration in range(max_iterations):
        last_output = _solve_pipeline_reasoning_once(
            directory,
            pipeline,
            model_dir=model_dir,
            filename=filename,
            tag=tag,
            tree=tree,
            verbose=verbose,
            json_trace=json_trace,
            debug_enabled=debug_enabled,
            export_domain=export_domain,
            time_limit_seconds=time_limit_seconds,
            reasoner_output_stream=reasoner_output_stream,
            restore_exported_trace=True,
        )
        if last_output.result.result is not True or last_output.result.exceptions:
            raise RuntimeError(f"findCorrect solve failed: {last_output.result}")
        if last_output.exported_loqi is None:
            raise RuntimeError("reasoner returned correct result without exported specificDomain")
        if len(last_output.trace_acts) <= previous_trace_length:
            raise RuntimeError(
                "findCorrect solve did not append a trace action before reaching END"
            )
        previous_trace_length = len(last_output.trace_acts)

        current_trace_act = registry.variables.get("P")
        if (
            solver_stops is not None
            and isinstance(current_trace_act, TraceAct)
            and current_trace_act in registry.trace_acts
        ):
            solver_stops.add(registry.trace_acts.index(current_trace_act))
        current_action = (
            current_trace_act.action
            if isinstance(current_trace_act, TraceAct)
            else last_output.trace_acts[-1].action
        )
        if _is_root_end_action(pipeline, current_action):
            return last_output

    raise RuntimeError(f"findCorrect did not finish after {max_iterations} iteration(s)")


def check_graph_stepwise_reasoning(
    directory: Path,
    pipeline: DomainDataGeneratorPipeline,
    selected_trace: Sequence[Action],
    *,
    model_dir: str | Path,
    filename: str = "generated-domain.loqi",
    tag: str | None = None,
    tree: str | None = None,
    verbose: bool = False,
    json_trace: bool = False,
    debug_enabled: bool = True,
    export_domain: bool = True,
    time_limit_seconds: int | None = None,
    reasoner_output_stream: TextIO | None = None,
) -> PipelineReasoningOutput:
    if not selected_trace:
        raise ValueError("selected_trace must not be empty")

    last_output: PipelineReasoningOutput | None = None
    for index, action in enumerate(selected_trace):
        _ensure_trace_tail_as_p(pipeline)
        pipeline.registry.variables["A"] = action
        last_output = _solve_pipeline_reasoning_once(
            directory,
            pipeline,
            model_dir=model_dir,
            filename=filename,
            tag=tag,
            tree=tree,
            verbose=verbose,
            json_trace=json_trace,
            debug_enabled=debug_enabled,
            export_domain=export_domain,
            time_limit_seconds=time_limit_seconds,
            reasoner_output_stream=reasoner_output_stream,
            restore_exported_trace=True,
        )
        if last_output.result.result is not True or last_output.result.exceptions:
            return last_output
        if index < len(selected_trace) - 1 and last_output.exported_loqi is None:
            raise RuntimeError(
                "stepwise reasoning returned correct result without exported specificDomain"
            )

    if last_output is None:
        raise RuntimeError("stepwise reasoning produced no output")
    return last_output


def write_pipeline_loqi(
    directory: Path,
    pipeline: DomainDataGeneratorPipeline,
    *,
    filename: str = "generated-domain.loqi",
) -> tuple[LoqiSerializer, Path, str]:
    loqi_results = pipeline_to_loqi(pipeline)
    if len(loqi_results) != 1:
        raise RuntimeError(f"Expected one LOQI result, found {len(loqi_results)}")

    serializer, loqi_text = loqi_results[0]
    loqi_file = directory / filename
    loqi_file.write_text(loqi_text, encoding="utf-8", newline="")
    return serializer, loqi_file, loqi_text


def _solve_pipeline_reasoning_once(
    directory: Path,
    pipeline: DomainDataGeneratorPipeline,
    *,
    model_dir: str | Path,
    filename: str = "generated-domain.loqi",
    tag: str | None = None,
    tree: str | None = None,
    verbose: bool = False,
    json_trace: bool = False,
    debug_enabled: bool = True,
    export_domain: bool = True,
    time_limit_seconds: int | None = None,
    reasoner_output_stream: TextIO | None = None,
    restore_exported_trace: bool = True,
) -> PipelineReasoningOutput:
    serializer, loqi_file, loqi_text = write_pipeline_loqi(
        directory,
        pipeline,
        filename=filename,
    )
    result = solve_reasoning(
        model_dir,
        loqi_file,
        tag=tag,
        tree=tree,
        verbose=verbose,
        json_trace=json_trace,
        debug_enabled=debug_enabled,
        export_domain=export_domain,
        time_limit_seconds=time_limit_seconds,
        reasoner_output_stream=reasoner_output_stream,
    )
    if result is None:
        raise RuntimeError("reasoner returned no output")

    exported_loqi = result.artifacts.get("specificDomain")
    if not isinstance(exported_loqi, str):
        exported_loqi = None

    trace_acts: list[TraceAct] = []
    trace_state: TraceState | None = None
    if restore_exported_trace and exported_loqi is not None:
        trace_acts, trace_state = restore_trace_from_loqi(exported_loqi, pipeline)

    return PipelineReasoningOutput(
        serializer=serializer,
        loqi_file=loqi_file,
        loqi_text=loqi_text,
        result=result,
        exported_loqi=exported_loqi,
        trace_acts=trace_acts,
        trace_state=trace_state,
    )


def _ensure_trace_tail_as_p(pipeline: DomainDataGeneratorPipeline) -> None:
    registry = pipeline.registry
    if registry.trace_acts:
        registry.variables["P"] = registry.trace_acts[-1]


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
