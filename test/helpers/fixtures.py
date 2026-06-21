from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


@pytest.fixture(autouse=True)
def write_runtime_logs_to_artifacts(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> Iterator[None]:
    if Path(str(request.node.path)).name != "test_solve_tree.py":
        yield
        return

    logger_specs = (
        ("src.meaning_tree", tmp_path / "meaning-tree-log.txt"),
        ("src.tpg_domain", tmp_path / "tpg-log.txt"),
    )
    installed_handlers: list[tuple[logging.Logger, logging.Handler, int]] = []
    formatter = logging.Formatter(LOG_FORMAT)

    for logger_name, log_path in logger_specs:
        logger = logging.getLogger(logger_name)
        previous_level = logger.level
        handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        installed_handlers.append((logger, handler, previous_level))

    try:
        yield
    finally:
        for logger, handler, previous_level in installed_handlers:
            logger.removeHandler(handler)
            handler.close()
            logger.setLevel(previous_level)
