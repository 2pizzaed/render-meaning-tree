from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from src.generator.pipeline import (
    DomainDataGeneratorPipeline,
    PipelineRegistry,
    SituationDomainDataRegistry,
)
from src.generator.utilities import (
    code_file_to_pipeline,
    code_snippet_to_pipeline,
    pipeline_to_loqi,
    registry_to_loqi,
)
from src.model.rules import TransitionDeclaration
from src.model.situation import Action, TraceAct
from src.serialization.loqi import LoqiSerializer
from src.tpg_domain import validate_domain_loqi

TEST_OUTPUT_DIR_ENV_VAR = "DOMAIN_BUILD_OUTPUT_DIR"
OPEN_TEST_ARTIFACTS_ENV_VAR = "OPEN_TEST_ARTIFACTS"

_TRACE_ACT_OBJECT_RE = re.compile(
    r"(?:var\s+\w+\s*=\s*)?obj\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*TraceAct\s*\{(?P<body>.*?)\}",
    re.DOTALL,
)
_TRACE_ACT_REF_RE = re.compile(
    r"\b(?P<rel>hasAction|hasTransition|directlyBeforeOf)\((?P<target>[A-Za-z_][A-Za-z0-9_]*)\);"
)


@dataclass(frozen=True, slots=True)
class _TraceActSpec:
    object_name: str
    action_name: str
    transition_name: str | None
    next_name: str | None
    source_order: int


def resolve_project_root(start: str | Path | None = None) -> Path:
    """Return repository root, detected by the sibling domain directory."""
    current = Path(start) if start is not None else Path(__file__)
    current = current.expanduser().resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "domain").is_dir():
            return candidate

    raise FileNotFoundError(
        f"Could not find project root with a domain directory from {current}"
    )


def resolve_test_output_dir(default: Path) -> Path:
    """Вернуть директорию для тестовых артефактов: env override или tmp_path."""
    configured = os.getenv(TEST_OUTPUT_DIR_ENV_VAR)
    if configured is None or not configured.strip():
        return default
    path = Path(configured).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text_file(
    directory: Path,
    content: str,
    filename: str,
) -> Path:
    """Записать текстовый файл в указанную директорию и вернуть путь к нему."""
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


def should_open_test_artifacts(default: bool = False) -> bool:
    """Нужно ли открывать тестовые артефакты во внешнем viewer."""
    configured = os.getenv(OPEN_TEST_ARTIFACTS_ENV_VAR)
    if configured is None:
        return default
    return configured.strip().lower() in {"1", "true", "yes", "on"}


def open_file_and_wait(path: str | Path, *, enabled: bool = False) -> Path | None:
    """Open a file with the system viewer and wait until that viewer process exits."""
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    if not enabled:
        return None

    system = platform.system()
    if system == "Windows":
        env = os.environ.copy()
        env["OPEN_FILE_AND_WAIT_PATH"] = str(file_path)
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "$path = $env:OPEN_FILE_AND_WAIT_PATH; "
                    "if ([string]::IsNullOrWhiteSpace($path)) { throw 'OPEN_FILE_AND_WAIT_PATH is empty' }; "
                    "Start-Process -FilePath $path -PassThru | Wait-Process"
                ),
            ],
            env=env,
            check=True,
        )
        return file_path

    if system == "Darwin":
        subprocess.run(["open", "-W", str(file_path)], check=True)
        return file_path

    opener = shutil.which("xdg-open")
    if opener is None:
        raise RuntimeError("xdg-open is required to open files on this platform")

    subprocess.run([opener, str(file_path)], check=True)
    return file_path


# TPG/domain helpers


def code_snippet_to_loqi_files(
    directory: Path,
    code: str,
    *,
    language: str = "python",
    mode: str = "procedural",
    filename: str = "generated-domain.loqi",
) -> list[tuple[LoqiSerializer, Path]]:
    pipeline = code_snippet_to_pipeline(code, language=language, mode=mode)
    return pipeline_to_loqi_files(directory, pipeline, filename=filename)


def code_snippet_to_pipeline_registries(
    code: str,
    *,
    language: str = "python",
    mode: str = "procedural",
) -> Sequence[PipelineRegistry]:
    pipeline = code_snippet_to_pipeline(code, language=language, mode=mode)
    return pipeline.flatten_results()


def pipeline_to_loqi_files(
    directory: Path,
    pipeline: DomainDataGeneratorPipeline,
    *,
    filename: str = "generated-domain.loqi",
) -> list[tuple[LoqiSerializer, Path]]:
    loqi_results = pipeline_to_loqi(pipeline)
    return [
        (
            serializer,
            write_text_file(
                directory, loqi, _loqi_filename(filename, index, len(loqi_results))
            ),
        )
        for index, (serializer, loqi) in enumerate(loqi_results, start=1)
    ]


def _loqi_filename(filename: str, index: int, total: int) -> str:
    if total == 1:
        return filename
    path = Path(filename)
    return f"{path.stem}-{index}{path.suffix}"


def validate_code_snippet_domain_loqi(
    directory: Path,
    code: str,
    *,
    model_dir: str | Path = "domain",
    language: str = "python",
    mode: str = "procedural",
    tag: str | None = None,
    filename: str = "generated-domain.loqi",
) -> bool:
    loqi_files = code_snippet_to_loqi_files(
        directory,
        code,
        language=language,
        mode=mode,
        filename=filename,
    )
    return all(
        validate_domain_loqi(loqi_file, model_dir, tag=tag)
        for _serializer, loqi_file in loqi_files
    )


def validate_code_file_domain_loqi(
    directory: Path,
    code_file: str | Path,
    *,
    model_dir: str | Path = "domain",
    language: str = "python",
    mode: str = "procedural",
    tag: str | None = None,
    filename: str = "generated-domain.loqi",
) -> bool:
    pipeline = code_file_to_pipeline(code_file, language=language, mode=mode)
    loqi_files = pipeline_to_loqi_files(directory, pipeline, filename=filename)
    return all(
        validate_domain_loqi(loqi_file, model_dir, tag=tag)
        for _serializer, loqi_file in loqi_files
    )


def line_actions(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    line_number: int,
    *,
    include_transparent: bool = False,
) -> list[Action]:
    """Вернуть actions для строки; по умолчанию только opaque, опционально и transparent."""
    registry = _registry_for(context)
    actions: list[Action] = []
    seen: set[int] = set()
    for node in _code_manager_for(context).line_number_to_ast_nodes(line_number):
        for action in registry.get_actions_for(node.id):
            if not include_transparent and not action.is_opaque:
                continue
            action_identity = id(action)
            if action_identity in seen:
                continue
            seen.add(action_identity)
            actions.append(action)
    return actions


def require_line_action(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    line_number: int,
    *,
    action_index: int = 0,
    include_transparent: bool = False,
) -> Action:
    """Выбрать action по номеру строки и индексу действия на этой строке."""
    actions = line_actions(
        context,
        line_number,
        include_transparent=include_transparent,
    )
    if action_index < 0 or action_index >= len(actions):
        raise LookupError(
            f"Expected action index {action_index} on line {line_number}, found {len(actions)} action(s)"
        )
    return actions[action_index]


def add_trace_act_for_line(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    line_number: int,
    *,
    action_index: int = 0,
    include_transparent: bool = False,
    transition: TransitionDeclaration | None = None,
    variable_name: str | None = "P",
) -> TraceAct:
    """Создать TraceAct для action на строке и добавить его в registry."""
    registry = _registry_for(context)
    action = require_line_action(
        context,
        line_number,
        action_index=action_index,
        include_transparent=include_transparent,
    )
    trace_act = TraceAct(
        action=action,
        used_transition=_resolve_transition(action, transition),
        situation=registry.owner,
    )
    registry.add(trace_act)
    if variable_name is not None:
        registry.variables[variable_name] = trace_act
    return trace_act


def add_trace_act_for_action(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    action: Action,
    *,
    transition: TransitionDeclaration | None = None,
    variable_name: str | None = "P",
) -> TraceAct:
    """Создать TraceAct для уже выбранного action и добавить его в registry."""
    registry = _registry_for(context)
    trace_act = TraceAct(
        action=action,
        used_transition=_resolve_transition(action, transition),
        situation=registry.owner,
    )
    registry.add(trace_act)
    if variable_name is not None:
        registry.variables[variable_name] = trace_act
    return trace_act


def trace_acts_from_loqi(
    loqi_text: str,
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
    *,
    replace_existing: bool = True,
) -> list[TraceAct]:
    """Восстановить TraceAct из LOQI-текста и привязать их к текущему registry."""
    registry = _registry_for(context)
    serializer, _ = registry_to_loqi(registry)
    trace_specs = _parse_trace_act_specs(loqi_text)

    if replace_existing:
        registry.trace_acts.clear()

    trace_acts: list[TraceAct] = []
    for trace_spec in _order_trace_act_specs(trace_specs):
        action = serializer.object_by_name(trace_spec.action_name)
        if not isinstance(action, Action):
            raise LookupError(
                f"Expected Action for {trace_spec.action_name!r}, found {type(action).__name__}"
            )

        used_transition = None
        if trace_spec.transition_name is not None:
            used_transition = serializer.object_by_name(trace_spec.transition_name)
            if not isinstance(used_transition, TransitionDeclaration):
                raise LookupError(
                    "Expected TransitionDeclaration for "
                    f"{trace_spec.transition_name!r}, found {type(used_transition).__name__}"
                )

        trace_act = TraceAct(
            action=action,
            used_transition=used_transition,
            situation=registry.owner,
        )
        registry.add(trace_act)
        trace_acts.append(trace_act)

    return trace_acts


def _code_manager_for(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
):
    if isinstance(context, DomainDataGeneratorPipeline):
        return context.code
    return context.owner.code


def _registry_for(
    context: DomainDataGeneratorPipeline | SituationDomainDataRegistry,
) -> SituationDomainDataRegistry:
    if isinstance(context, DomainDataGeneratorPipeline):
        return context.registry
    return context


def _resolve_transition(
    action: Action,
    transition: TransitionDeclaration | None,
) -> TransitionDeclaration | None:
    if transition is not None:
        return transition
    transitions = action.possible_transitions()
    if len(transitions) == 1:
        return transitions[0]
    if not transitions:
        return None
    raise LookupError(
        f"Expected explicit transition for action {action.rule.role!r}, found {len(transitions)} candidates"
    )


def _parse_trace_act_specs(loqi_text: str) -> list[_TraceActSpec]:
    trace_specs: list[_TraceActSpec] = []
    for index, match in enumerate(_TRACE_ACT_OBJECT_RE.finditer(loqi_text)):
        refs = {
            ref_match.group("rel"): ref_match.group("target")
            for ref_match in _TRACE_ACT_REF_RE.finditer(match.group("body"))
        }
        action_name = refs.get("hasAction")
        if action_name is None:
            raise ValueError(
                f"TraceAct {match.group('name')!r} does not declare hasAction(...)"
            )
        trace_specs.append(
            _TraceActSpec(
                object_name=match.group("name"),
                action_name=action_name,
                transition_name=refs.get("hasTransition"),
                next_name=refs.get("directlyBeforeOf"),
                source_order=index,
            )
        )
    return trace_specs


def _order_trace_act_specs(trace_specs: Sequence[_TraceActSpec]) -> list[_TraceActSpec]:
    specs_by_name = {trace_spec.object_name: trace_spec for trace_spec in trace_specs}
    incoming_names = {
        trace_spec.next_name
        for trace_spec in trace_specs
        if trace_spec.next_name in specs_by_name
    }
    ordered: list[_TraceActSpec] = []
    seen: set[str] = set()

    for trace_spec in trace_specs:
        if trace_spec.object_name in incoming_names:
            continue
        _append_trace_chain(trace_spec, specs_by_name, seen, ordered)

    for trace_spec in trace_specs:
        _append_trace_chain(trace_spec, specs_by_name, seen, ordered)

    return ordered


def _append_trace_chain(
    start: _TraceActSpec,
    specs_by_name: dict[str, _TraceActSpec],
    seen: set[str],
    ordered: list[_TraceActSpec],
) -> None:
    current: _TraceActSpec | None = start
    while current is not None and current.object_name not in seen:
        ordered.append(current)
        seen.add(current.object_name)
        current = (
            specs_by_name.get(current.next_name)
            if current.next_name is not None
            else None
        )
