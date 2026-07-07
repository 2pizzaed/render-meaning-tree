from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from src.generator.pipeline import DomainDataGeneratorPipeline
from src.generator.utilities import pipeline_to_loqi
from src.helpers.tpg.trace import restore_trace_from_loqi
from src.model.situation import TraceAct, TraceState
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
