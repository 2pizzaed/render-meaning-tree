from __future__ import annotations

import os
from pathlib import Path

TEST_OUTPUT_DIR_ENV_VAR = "DOMAIN_BUILD_OUTPUT_DIR"
OPEN_TEST_ARTIFACTS_ENV_VAR = "OPEN_TEST_ARTIFACTS"
PNG_DOT_OUTPUT_ENV_VAR = "PNG_DOT_OUTPUT"


class SlowToolchainBackendWarning(UserWarning):
    """Тесты вызывают тулчейн через CLI (новая JVM на каждый вызов), а не через RPC-сервер."""


def toolchains_without_rpc() -> list[str]:
    """Фасады тулчейна, выбравшие при импорте не RPC-бэкенд."""
    # Бэкенд выбирается при импорте фасада; health-проба auto-режима кешируется на процесс.
    from src import meaning_tree, tpg_domain

    backends = {
        "tpg_domain (its_DomainModel, its_Reasoner)": tpg_domain.ACTIVE_BACKEND,
        "meaning_tree": meaning_tree.ACTIVE_BACKEND,
    }
    return [name for name, backend in backends.items() if backend != "rpc"]




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


def should_output_dot_png(default: bool = True) -> bool:
    """Нужно ли сохранять PNG-артефакты для dot-рендера."""
    configured = os.getenv(PNG_DOT_OUTPUT_ENV_VAR)
    if configured is None:
        return default
    return configured.strip().lower() in {"1", "true", "yes", "on"}
