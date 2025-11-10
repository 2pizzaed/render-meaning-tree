from enum import Enum

from src.cfg.abstractions import KindChain


class NodeConstruction(Enum):
    """Classification of CFG nodes constructed from AST actions."""

    NONE = "none"  # skip this AST node in CFG.
    ATOM = "atom"
    COMPOUND = "compound"


def _has(kind: KindChain | None, value: str) -> bool:
    return bool(kind and kind.has(value))


def determine_node_construction(
    *,
    action_kind: KindChain | None,
    construct_kind: KindChain | None,
) -> NodeConstruction:
    """Convert action/construct kinds and AST characteristics to a node construction type."""

    if _has(construct_kind, "noop"):
        return NodeConstruction.NONE

    if _has(action_kind, "compound"):
        return NodeConstruction.COMPOUND

    if _has(action_kind, "inline") or _has(action_kind, "condition"):
        return NodeConstruction.ATOM

    if _has(action_kind, "auto"):
        if _has(construct_kind, "compound"):
            return NodeConstruction.COMPOUND
        if _has(construct_kind, "inline"):
            return NodeConstruction.ATOM
        if construct_kind is None:
            return NodeConstruction.ATOM

    if _has(construct_kind, "compound"):
        return NodeConstruction.COMPOUND

    if _has(construct_kind, "inline") or _has(construct_kind, "condition"):
        return NodeConstruction.ATOM

    return NodeConstruction.ATOM
