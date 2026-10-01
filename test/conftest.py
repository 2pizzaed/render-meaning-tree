import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.env import load_project_env
from test.helpers.env import SlowToolchainBackendWarning, toolchains_without_rpc

pytest_plugins = ("test.helpers.fixtures",)

load_project_env()

MAX_PYTEST_RUN_DIRS = 10


SLOW_BACKEND_TOOLCHAINS_KEY = pytest.StashKey[list[str]]()


def _slow_backend_message(toolchains: list[str]) -> str:
    return (
        f"toolchain is not using the RPC backend (CLI: {', '.join(toolchains)}). "
        "Every call starts a new JVM, so the test run will be far too slow. "
        "Strongly recommended: stop the tests (Ctrl+C), set up RPC "
        "(bash rpc_server.sh start; TOOLCHAIN_BACKEND=auto or rpc and "
        "JSON_RPC_TOOLCHAIN_SERVER in .env) and run them again."
    )


def _check_toolchain_backend(config: pytest.Config) -> None:
    toolchains = toolchains_without_rpc()
    config.stash[SLOW_BACKEND_TOOLCHAINS_KEY] = toolchains
    if toolchains:
        # Попадает в warnings summary в конце прогона; с -W error::...SlowToolchainBackendWarning
        # прогон сразу прерывается.
        config.issue_config_time_warning(
            SlowToolchainBackendWarning(_slow_backend_message(toolchains)), stacklevel=2
        )


def pytest_sessionstart(session: pytest.Session) -> None:
    # warnings summary печатается только в конце, поэтому дублируем предупреждение
    # в начале прогона, пока его ещё есть смысл остановить.
    toolchains = session.config.stash.get(SLOW_BACKEND_TOOLCHAINS_KEY, [])
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if toolchains and reporter is not None:
        reporter.write_sep("!", "WARNING: " + SlowToolchainBackendWarning.__name__, red=True, bold=True)
        reporter.write_line(_slow_backend_message(toolchains), yellow=True, bold=True)
        reporter.write_sep("!", red=True, bold=True)


def pytest_configure(config):
    project_root = Path(__file__).resolve().parents[1]
    temp_root = project_root / ".tmp.pytest"
    temp_root.mkdir(parents=True, exist_ok=True)
    worker_id = os.getenv("PYTEST_XDIST_WORKER")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_suffix = f"{timestamp}-{worker_id}" if worker_id else timestamp
    run_temp = temp_root / f"run-{run_suffix}"
    run_temp.mkdir(parents=True, exist_ok=True)
    if worker_id is None:
        _prune_old_run_dirs(temp_root, keep=MAX_PYTEST_RUN_DIRS, cur=run_temp)
    tempfile.tempdir = str(run_temp)
    config.option.basetemp = str(run_temp)
    if worker_id is None:
        _check_toolchain_backend(config)


def _prune_old_run_dirs(temp_root: Path, *, keep: int, cur: Path) -> None:
    run_dirs = sorted(
        (path for path in temp_root.iterdir() if path.is_dir() and path.name.startswith("run-")),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    protected = {cur.resolve()}
    for path in run_dirs[keep:]:
        if path.resolve() not in protected:
            shutil.rmtree(path, ignore_errors=True)
