from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

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
