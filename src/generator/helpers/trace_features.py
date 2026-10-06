"""Read-only views of an AST and the supplied execution trace."""

from collections import defaultdict
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field

from src.ast_managers import ASTNodeManager, NodePathElement
from src.model.situation import Construct, TraceAct

type TracePredicate = Callable[[ASTNodeManager, Sequence[TraceAct]], bool]

_CONTAINER_TYPES = frozenset(
    {
        "program_entry_point",
        "compound_statement",
        "if_statement",
        "condition_branch",
        "switch_statement",
        "basic_case_block",
        "default_case_block",
        "fallthrough_case_block",
        "general_for_loop",
        "range_for_loop",
        "for_each_loop",
        "while_loop",
        "while_else_loop",
        "do_while_loop",
        "infinite_loop",
        "exception_catch_statement",
        "catch_clause",
        "function_definition",
        "method_definition",
        "class_definition",
        "interface_definition",
        "structure_definition",
        "object_constructor_definition",
        "object_destructor_definition",
    }
)
_FUNCTION_TYPES = frozenset(
    {
        "function_definition",
        "method_definition",
        "object_constructor_definition",
        "object_destructor_definition",
    }
)


def active_node_paths(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> list[NodePathElement]:
    """Include traced nodes, their context, and unconditional atomic operands.

    Control-flow bodies are visited only through their own acts. Conditional
    operands need separate trace evidence; an enclosing expression is not proof
    that both operands of short-circuit or ternary evaluation ran.
    """
    paths: dict[int, NodePathElement] = {path.id: path for _, (path, _) in ast}
    children: dict[int, list[NodePathElement]] = defaultdict(list)
    for path in paths.values():
        if path.parent is not None:
            children[path.parent.id].append(path)

    active: set[int] = set()
    operands: list[int] = []
    for act in trace:
        action = act.action
        for ast_id in (action.ast_id, action.parent.ast_id):
            path = ast.get_path(ast_id) if ast_id is not None else None
            while path is not None:
                active.add(path.id)
                path = path.parent
        if (
            action.ast_id is not None
            and action.ast_id in paths
            and action.rule.role not in {"BEGIN", "END"}
        ):
            operands.append(action.ast_id)

    expanded: set[int] = set()
    while operands:
        ast_id = operands.pop()
        if ast_id in expanded:
            continue
        expanded.add(ast_id)
        parent = paths[ast_id]
        if parent.type in _CONTAINER_TYPES:
            continue
        for child in children[ast_id]:
            if (
                parent.type
                in {
                    "short_circuit_and_operator",
                    "short_circuit_or_operator",
                }
                and child.field_name == "right_operand"
            ):
                continue
            if parent.type == "ternary_operator" and child.field_name in {
                "true_expression",
                "false_expression",
            }:
                continue
            if child.type in _CONTAINER_TYPES:
                continue
            active.add(child.id)
            operands.append(child.id)
    return [path for ast_id, path in paths.items() if ast_id in active]


def has_node_types(
    ast: ASTNodeManager, trace: Sequence[TraceAct], *node_types: str
) -> bool:
    return any(
        path.instanceof(node_type)
        for path in active_node_paths(ast, trace)
        for node_type in node_types
    )


@dataclass(slots=True)
class ConstructRun:
    construct: Construct
    begin: int
    end: int | None = None
    acts: list[TraceAct] = field(default_factory=list)
    parent: "ConstructRun | None" = None


def construct_runs(trace: Sequence[TraceAct]) -> list[ConstructRun]:
    """Separate activations even when recursion reuses one Construct object."""
    runs: list[ConstructRun] = []
    stack: list[ConstructRun] = []
    for index, act in enumerate(trace):
        if act.action.rule.role == "BEGIN":
            run = ConstructRun(
                act.action.parent,
                index,
                acts=[act],
                parent=stack[-1] if stack else None,
            )
            runs.append(run)
            stack.append(run)
            continue
        for offset in range(len(stack) - 1, -1, -1):
            run = stack[offset]
            if run.construct is act.action.parent:
                run.acts.append(act)
                if act.action.rule.role == "END":
                    run.end = index
                    del stack[offset]
                break
    return runs


def function_entries(
    ast: ASTNodeManager, trace: Sequence[TraceAct]
) -> Iterator[tuple[Construct, ...]]:
    """Yield the active function stack at each function-body entry."""
    stack: list[Construct] = []
    for act in trace:
        construct = act.action.parent
        node = ast.get(construct.ast_id)
        if node is None or node["type"] not in _FUNCTION_TYPES:
            continue
        if act.action.rule.role == "BEGIN":
            stack.append(construct)
            yield tuple(stack)
        elif act.action.rule.role == "END" and stack and stack[-1] is construct:
            stack.pop()


def is_function_construct(ast: ASTNodeManager, construct: Construct) -> bool:
    node = ast.get(construct.ast_id)
    return node is not None and node["type"] in _FUNCTION_TYPES


def is_within(construct: Construct, ancestor: Construct) -> bool:
    current: Construct | None = construct
    while current is not None:
        if current is ancestor:
            return True
        current = current.parent
    return False
