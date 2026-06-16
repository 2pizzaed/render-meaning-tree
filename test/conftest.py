import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from src.env import load_project_env

load_project_env()

MAX_PYTEST_RUN_DIRS = 3


def pytest_configure(config):
    project_root = Path(__file__).resolve().parents[1]
    temp_root = project_root / ".tmp.pytest"
    temp_root.mkdir(parents=True, exist_ok=True)
    run_temp = temp_root / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_temp.mkdir(parents=True, exist_ok=True)
    _prune_old_run_dirs(temp_root, keep=MAX_PYTEST_RUN_DIRS, current=run_temp)
    tempfile.tempdir = str(run_temp)
    config.option.basetemp = str(run_temp)


def _prune_old_run_dirs(temp_root: Path, *, keep: int, current: Path) -> None:
    run_dirs = sorted(
        (
            path
            for path in temp_root.iterdir()
            if path.is_dir() and path.name.startswith("run-")
        ),
        reverse=True,
    )
    protected = {current.resolve()}
    for path in run_dirs[keep:]:
        if path.resolve() not in protected:
            shutil.rmtree(path, ignore_errors=True)
