from src.cfg import CFG
from src.cfg.abstractions import load_constructs
from src.cfg.cfg_builder import CfgBuilder
from src.cfg_tools import *

# cfg = ControlFlowGraph()
cfg = CfgBuilder()
constructs = load_constructs(debug=True)


@cfg.node(type="program_entry_point")
def program_entry_point(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
    current_block = entry_block

    if "body" in node and isinstance(node["body"], list):
        for stmt in node["body"]:
            stmt_entry, stmt_exit = self._process_node(stmt, current_block, exit_block)
            current_block = stmt_exit

    if current_block != exit_block:
        self._add_edge(current_block, exit_block)

    return entry_block, exit_block


@cfg.node(type="compound_statement")
def compound_statement(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
    current_block = entry_block

    if "statements" in node and isinstance(node["statements"], list):
        for stmt in node["statements"]:
            stmt_entry, stmt_exit = self._process_node(stmt, current_block, exit_block)
            current_block = stmt_exit

    return entry_block, current_block


@cfg.node(type="if_statement")
def if_statement(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
    if entry_block.is_entry:
        condition_block = self._create_block()
        self._add_edge(entry_block, condition_block)
    else:
        condition_block = entry_block

    condition_block.add_instruction("if condition")

    after_if_block = self._create_block()

    if "branches" in node and isinstance(node["branches"], list):
        branch_exit_blocks = []

        for i, branch in enumerate(node["branches"]):
            branch_block = self._create_block()

            self._add_edge(condition_block, branch_block)

            _, branch_exit = self._process_node(branch["body"], branch_block, after_if_block)

            if branch_exit != after_if_block:
                self._add_edge(branch_exit, after_if_block)

            branch_exit_blocks.append(branch_exit)

    return entry_block, after_if_block


@cfg.node(type="while_loop")
def while_loop(self, node: Node) -> CFG:
    loop_header = self._create_block()
    loop_header.add_instruction("while condition")

    after_loop = self._create_block()

    if entry_block != loop_header:
        self._add_edge(entry_block, loop_header)

    if "body" in node:
        loop_body = self._create_block()
        self._add_edge(loop_header, loop_body, "true")

        _, body_exit = self._process_node(node["body"], loop_body, loop_header)

        if body_exit != loop_header:
            self._add_edge(body_exit, loop_header, "back")

    self._add_edge(loop_header, after_loop, "false")

    return entry_block, after_loop


@cfg.node(type="range_for_loop")
def for_loop(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
    init_block = self._create_block()
    init_block.add_instruction(f"for init: {node.get('identifier', '')}")

    cond_block = self._create_block()
    cond_block.add_instruction("for condition")

    incr_block = self._create_block()
    incr_block.add_instruction("for increment")

    after_loop = self._create_block()

    self._add_edge(entry_block, init_block)
    self._add_edge(init_block, cond_block)

    if "body" in node:
        body_block = self._create_block()
        self._add_edge(cond_block, body_block, "true")

        _, body_exit = self._process_node(node["body"], body_block, incr_block)

        if body_exit != incr_block:
            self._add_edge(body_exit, incr_block)

    self._add_edge(incr_block, cond_block, "back")

    self._add_edge(cond_block, after_loop, "false")

    return entry_block, after_loop


@cfg.node(type="assignment_statement")
def assignment_statement(self, node: Node, entry_block: BasicBlock, exit_block: BasicBlock) -> Tuple[BasicBlock, BasicBlock]:
    if "target" in node and "value" in node:
        target = node.get("target", {}).get("name", "var")
        content = f"{target} = expression"
    else:
        content = "assignment"

    if entry_block is not None and not entry_block.is_entry:
        entry_block.add_instruction(content)

    return entry_block, entry_block

