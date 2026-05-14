from __future__ import annotations

import os
from pathlib import Path

from src.generator.utilities import code_file_to_loqi, code_snippet_to_loqi
from src.tpg_domain import validate_domain_loqi

TEST_OUTPUT_DIR_ENV_VAR = "DOMAIN_BUILD_OUTPUT_DIR"


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


# TPG/domain helpers

def code_snippet_to_loqi_file(
    directory: Path,
    code: str,
    *,
    language: str = "python",
    mode: str = "simple",
    filename: str = "generated-domain.loqi",
) -> Path:
    loqi = code_snippet_to_loqi(code, language=language, mode=mode)
    return write_text_file(directory, loqi, filename)


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
    loqi_file = code_snippet_to_loqi_file(
        directory,
        code,
        language=language,
        mode=mode,
        filename=filename,
    )
    return validate_domain_loqi(loqi_file, model_dir, tag=tag)


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
    loqi = code_file_to_loqi(code_file, language=language, mode=mode)
    loqi_file = write_text_file(directory, loqi, filename)
    return validate_domain_loqi(loqi_file, model_dir, tag=tag)
