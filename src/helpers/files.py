"""Project-root paths, project-local temp dirs and opening files in a system viewer."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import uuid
from pathlib import Path


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


def make_project_temp_dir(prefix: str, root: Path | None = None) -> Path:
    """Create a writable project-local temporary directory under .tmp by default."""
    temp_root = root or resolve_project_root() / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    path = temp_root / f"{prefix}{uuid.uuid4().hex}"
    path.mkdir()
    return path


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
