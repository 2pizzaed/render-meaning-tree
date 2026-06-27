import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from src.env import load_project_env

pytest_plugins = ("test.helpers.fixtures",)

load_project_env()

MAX_PYTEST_RUN_DIRS = 10


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
