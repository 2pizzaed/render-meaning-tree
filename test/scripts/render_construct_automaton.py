from __future__ import annotations

import argparse
from pathlib import Path

from src.generator.automaton import ConstructTransitionAutomaton
from src.model.rules import ConstructDeclaration, load_construct_declarations
from test.helpers.env import open_file_and_wait, resolve_project_root

DEFAULT_OUTPUT_DIR = Path("test") / "output"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project_root = resolve_project_root()
    constructs_path = _resolve_path(args.constructs, project_root)
    output_dir = _resolve_path(args.output_dir, project_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    construct = _load_construct(constructs_path, args.construct)
    automaton = ConstructTransitionAutomaton(construct)
    dot_path, png_path = render_construct_automaton(
        automaton,
        output_dir,
        filename_stem=args.filename_stem or construct.name,
    )

    print(dot_path)
    print(png_path)
    if args.open:
        open_file_and_wait(png_path, enabled=True)
    return 0


def render_construct_automaton(
    automaton: ConstructTransitionAutomaton,
    output_dir: Path,
    *,
    filename_stem: str,
) -> tuple[Path, Path]:
    dot_text = automaton.to_dot()
    dot_path = output_dir / f"{filename_stem}.dot"
    png_path = output_dir / f"{filename_stem}.png"
    dot_path.write_text(dot_text, encoding="utf-8", newline="")
    automaton.write_png(png_path)
    return dot_path, png_path


def _load_construct(path: Path, construct_name: str) -> ConstructDeclaration:
    declarations = load_construct_declarations(path)
    for declaration in declarations:
        if declaration.name == construct_name:
            return declaration
    available = ", ".join(declaration.name for declaration in declarations)
    raise LookupError(
        f"Construct {construct_name!r} was not found in {path}. Available: {available}"
    )


def _resolve_path(path: Path, project_root: Path) -> Path:
    path = path.expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render compiled transition automaton DOT/PNG for one construct "
            "from constructs.yml."
        )
    )
    parser.add_argument(
        "construct",
        help="Construct name from constructs.yml, for example if_structure.",
    )
    parser.add_argument(
        "--constructs",
        type=Path,
        default=Path("src") / "resources" / "constructs.yml",
        help="Path to constructs.yml.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated DOT and PNG files.",
    )
    parser.add_argument(
        "--filename-stem",
        help="Output filename without extension. Defaults to construct name.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated PNG with the system viewer.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
