import os
from pathlib import Path

import pytest

from src.meaning_tree.cli import convert, generate, to_tokens


def test_convert_supports_skip_errors_and_project_context(monkeypatch) -> None:
    calls: list[tuple[tuple[str, ...], str | None]] = []

    def fake_run_meaning_tree(*args: str, stdin_data: str | None = None) -> str:
        calls.append((args, stdin_data))
        return "converted"

    monkeypatch.setattr("src.meaning_tree.cli._run_meaning_tree", fake_run_meaning_tree)

    result = convert(
        "print(1)",
        "python",
        "python",
        skip_errors=True,
        project_root="/repo",
        project_file="src/main.py",
    )

    assert result == "converted"
    args, stdin_data = calls[0]
    assert args[:5] == ("translate", "--from", "python", "--to", "python")
    assert "--skip-errors" in args
    assert "--project" in args
    assert args[args.index("--project") + 1] == f"{Path('/repo')}{os.pathsep}{Path('src/main.py')}"
    assert stdin_data == "print(1)"


def test_to_tokens_supports_skip_errors_without_conversion(monkeypatch) -> None:
    calls: list[tuple[tuple[str, ...], str | None]] = []

    def fake_run_meaning_tree(*args: str, stdin_data: str | None = None) -> str:
        calls.append((args, stdin_data))
        return "{}"

    monkeypatch.setattr("src.meaning_tree.cli._run_meaning_tree", fake_run_meaning_tree)

    result = to_tokens("python", "print(1)", skip_errors=True)

    assert result == {}
    args, _stdin_data = calls[0]
    assert args[:3] == ("translate", "--from", "python")
    assert "--tokenize-noconvert" in args
    assert "--skip-errors" in args


def test_generate_supports_skip_errors(monkeypatch) -> None:
    calls: list[tuple[tuple[str, ...], str | None]] = []

    def fake_run_meaning_tree(*args: str, stdin_data: str | None = None) -> str:
        calls.append((args, stdin_data))
        return "generated"

    monkeypatch.setattr("src.meaning_tree.cli._run_meaning_tree", fake_run_meaning_tree)

    result = generate('{"root_node": {}}', "python", skip_errors=True)

    assert result == "generated"
    args, stdin_data = calls[0]
    assert args[:5] == ("generate", "--to", "python", "--format", "json")
    assert "--skip-errors" in args
    assert stdin_data == '{"root_node": {}}'


def test_convert_requires_both_project_root_and_project_file() -> None:
    with pytest.raises(
        ValueError, match="project_root and project_file must be provided together"
    ):
        convert("print(1)", "python", "python", project_root="/repo")
