import tempfile
from pathlib import Path

from src.env import load_project_env

load_project_env()


def pytest_configure(config):
    project_root = Path(__file__).resolve().parents[1]
    base_temp = project_root / ".pytest-tmp"
    base_temp.mkdir(exist_ok=True)
    tempfile.tempdir = str(base_temp)
    config.option.basetemp = str(base_temp)
