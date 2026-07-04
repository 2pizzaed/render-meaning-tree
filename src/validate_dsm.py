from __future__ import annotations

import argparse
from pathlib import Path

from src.tpg_domain import validate_domain_solving_model


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a DomainSolvingModel directory."
    )
    parser.add_argument(
        "model_dir",
        nargs="?",
        type=Path,
        default=_project_root() / "domain",
        help="DomainSolvingModel directory to validate. Defaults to ./domain.",
    )
    parser.add_argument(
        "--build-method",
        choices=["LOQI", "DICT_RDF"],
        default="LOQI",
        help="Domain build method passed to its_DomainModel.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable its_DomainModel debug mode.",
    )
    args = parser.parse_args()

    valid = validate_domain_solving_model(
        args.model_dir,
        build_method=args.build_method,
        debug_enabled=args.debug,
    )
    return 0 if valid else 1


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    raise SystemExit(main())
