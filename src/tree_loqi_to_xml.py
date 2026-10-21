from __future__ import annotations

import argparse
from pathlib import Path

from src.tpg_domain import tree_loqi_to_xml


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert a LOQI tree file to tree.tmp.xml next to the input file."
    )
    parser.add_argument(
        "tree",
        help="Tree LOQI/TPG path or name. Names are resolved in ./domain and may omit the extension.",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=None,
        help="Optional DomainSolvingModel directory for validation.",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Optional model tag. Valid only with --model-dir.",
    )
    parser.add_argument(
        "--no-cdata-expressions",
        action="store_true",
        help="Do not write LOQI expressions as XML CDATA.",
    )
    args = parser.parse_args()

    tree_path = _resolve_tree_path(args.tree)
    output_path = tree_path.with_name("test.xml")

    converted = tree_loqi_to_xml(
        tree_path,
        output=output_path,
        model_dir=args.model_dir,
        tag=args.tag,
        cdata_expressions=not args.no_cdata_expressions,
    )
    if converted is not True:
        return 1

    print(output_path)
    return 0


def _resolve_tree_path(value: str) -> Path:
    project_root = Path(__file__).resolve().parents[1]
    requested = Path(value)
    candidates = [requested]

    if requested.suffix not in {".loqi", ".tpg"}:
        candidates.extend(requested.with_suffix(suffix) for suffix in [".loqi", ".tpg"])

    domain_dir = project_root / "domain"
    candidates.append(domain_dir / requested)
    if requested.suffix not in {".loqi", ".tpg"}:
        candidates.extend(
            (domain_dir / requested).with_suffix(suffix) for suffix in [".loqi", ".tpg"]
        )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Could not find tree LOQI/TPG file. Searched: {searched}")


if __name__ == "__main__":
    raise SystemExit(main())
