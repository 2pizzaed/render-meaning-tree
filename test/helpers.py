from __future__ import annotations

import os
import platform
import shutil
import subprocess
from collections.abc import Sequence
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
)
from src.model.rules import TransitionDeclaration
from src.model.situation import Action, TraceAct
from src.serialization.loqi import LoqiSerializer
from src.tpg_domain import validate_domain_loqi

TEST_OUTPUT_DIR_ENV_VAR = "DOMAIN_BUILD_OUTPUT_DIR"
OPEN_TEST_ARTIFACTS_ENV_VAR = "OPEN_TEST_ARTIFACTS"


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
