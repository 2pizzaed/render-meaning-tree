from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from src.generator.pipeline import DomainDataGeneratorPipeline, PipelineRegistry
from src.generator.utilities import (
    code_file_to_pipeline,
    code_snippet_to_pipeline,
    pipeline_to_loqi,
)
from src.serialization.loqi import LoqiSerializer
from src.tpg_domain import validate_domain_loqi

TEST_OUTPUT_DIR_ENV_VAR = "DOMAIN_BUILD_OUTPUT_DIR"


def resolve_project_root(start: str | Path | None = None) -> Path:
    """Return repository root, detected by the sibling domain directory."""
    current = Path(start) if start is not None else Path(__file__)
    current = current.expanduser().resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "domain").is_dir():
            return candidate

    raise FileNotFoundError(f"Could not find project root with a domain directory from {current}")


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


def open_file_and_wait(path: str | Path) -> None:
    """Open a file with the system viewer and wait until that viewer process exits."""
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(file_path)

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
        return

    if system == "Darwin":
        subprocess.run(["open", "-W", str(file_path)], check=True)
        return

    opener = shutil.which("xdg-open")
    if opener is None:
        raise RuntimeError("xdg-open is required to open files on this platform")

    subprocess.run([opener, str(file_path)], check=True)


# TPG/domain helpers

def code_snippet_to_loqi_files(
    directory: Path,
    code: str,
    *,
    language: str = "python",
    mode: str = "simple",
    filename: str = "generated-domain.loqi",
) -> list[tuple[LoqiSerializer, Path]]:
    pipeline = code_snippet_to_pipeline(code, language=language, mode=mode)
    return pipeline_to_loqi_files(directory, pipeline, filename=filename)


def code_snippet_to_pipeline_registries(
    code: str,
    *,
    language: str = "python",
    mode: str = "simple",
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
            write_text_file(directory, loqi, _loqi_filename(filename, index, len(loqi_results))),
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
    mode: str = "simple",
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
    return all(validate_domain_loqi(loqi_file, model_dir, tag=tag) for _serializer, loqi_file in loqi_files)


def validate_code_file_domain_loqi(
    directory: Path,
    code_file: str | Path,
    *,
    model_dir: str | Path = "domain",
    language: str = "python",
    mode: str = "simple",
    tag: str | None = None,
    filename: str = "generated-domain.loqi",
) -> bool:
    pipeline = code_file_to_pipeline(code_file, language=language, mode=mode)
    loqi_files = pipeline_to_loqi_files(directory, pipeline, filename=filename)
    return all(validate_domain_loqi(loqi_file, model_dir, tag=tag) for _serializer, loqi_file in loqi_files)
