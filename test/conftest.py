import shutil
import tempfile
from pathlib import Path

from src.env import load_project_env

load_project_env()

MAX_PYTEST_RUN_DIRS = 2


def pytest_configure(config):
    project_root = Path(__file__).resolve().parents[1]
    temp_root = project_root / ".tmp" / "pytest"
    temp_root.mkdir(parents=True, exist_ok=True)
    run_temp = Path(tempfile.mkdtemp(prefix="run-", dir=temp_root))
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
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    protected = {current.resolve()}
    removable = [
        path
        for path in run_dirs[keep:]
        if path.resolve() not in protected
    ]
    for path in removable:
        shutil.rmtree(path, ignore_errors=True)
