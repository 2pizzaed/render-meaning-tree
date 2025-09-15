from jinja2 import Environment, FileSystemLoader

from src.html_utils import syntax_highlight, add_indent_lines
from src.renderer import Renderer, CodeBlock

environment = Environment(loader=FileSystemLoader("templates/"))
r = Renderer()
PYTHON_SYNTAX_HIGHLIGHT = {
    "keywords": ("if", "else", "for", "while", "in", "range", "True", "False", "None"),
    "special": "{}()=<>:+-*/",
    "comment": ("#",),
    "string": ('"', "'", '"""', "'''"),
    "multiline_comments": (('"""', '"""'), ("'''", "'''")),
}


@r.node(type="program_entry_point")
def program_entry_point(node):
    template = environment.get_template("base.html")

    # Collect & render statements
    block = CodeBlock(r.indenter)
    for child in node["body"]:
        block.add(r.render(child))

    # Add HTML styling
    lines = syntax_highlight(block.lines, **PYTHON_SYNTAX_HIGHLIGHT)
    lines = add_indent_lines(lines)

    codeline_template = environment.get_template("utils/codeline.html")
    codelines = [codeline_template.render(line=line) for line in lines]
    return template.render(body=codelines)


@r.node(type="if_statement")
def if_statement(node):
    block = CodeBlock(r.indenter)

    for i, branch in enumerate(node["branches"]):
        if i == 0:
            header = "if %s:" % r.render(branch["condition"])
        elif "condition" in branch:
            header = "elif %s:" % r.render(branch["condition"])
        else:
            header = "else:"

        block.add(header)
        block.add_with_indent(r.render(branch["body"]))

    return block.lines


@r.node(type="while_loop")
def while_statement(node):
    header = "while %s:" % r.render(node["condition"])

    block = CodeBlock(r.indenter)
    block.add(header)
    block.add_with_indent(r.render(node["body"]))

    return block.lines


@r.node(type="range_for_loop")
def for_statement(node):
    identifier = r.render(node["identifier"])
    range_obj = node["range"]
    
    start = r.render(range_obj["start"])
    stop = r.render(range_obj["stop"])
    step = r.render(range_obj["step"])
    range_type = range_obj["rangeType"]

    if range_type == "up" or range_type == "unknown":
        # For forward ranges, we use range(start, stop, step)
        range_expr = f"range({start}, {stop}, {step})"
    elif range_type == "down":
        # For backward ranges, we still use range() but with negative step
        range_expr = f"range({start}, {stop}, -{step})"
    else:
        # Default case
        range_expr = f"range({start}, {stop}, {step})"

    header = f"for {identifier} in {range_expr}:"

    block = CodeBlock(r.indenter)
    block.add(header)
    block.add_with_indent(r.render(node["body"]))

    return block.lines


@r.node(type="compound_statement")
def compound_statement(node):
    block = CodeBlock(r.indenter)
    for statement in node["statements"]:
        block.add(r.render(statement))
    return block.lines


@r.node(type="add_operator")
def add_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} + {right}"


@r.node(type="sub_operator")
def sub_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} - {right}"


@r.node(type="mul_operator")
def mul_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} * {right}"


@r.node(type="div_operator")
def div_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} / {right}"  # In Python 3, / is true division


@r.node(type="mod_operator")
def mod_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} % {right}"


@r.node(type="floor_div_operator")
def floor_div_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} // {right}"  # Python's floor division operator


@r.node(type="pow_operator")
def pow_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} ** {right}"  # Python's power operator


@r.node(type="eq_operator")
def eq_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} == {right}"


@r.node(type="ge_operator")
def ge_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} >= {right}"


@r.node(type="gt_operator")
def gt_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} > {right}"


@r.node(type="le_operator")
def le_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} <= {right}"


@r.node(type="lt_operator")
def lt_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} < {right}"


@r.node(type="not_eq_operator")
def not_eq_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} != {right}"


@r.node(type="reference_eq_operator")
def reference_eq_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} is {right}"  # Python's identity comparison operator


@r.node(type="short_circuit_and_operator")
def short_circuit_and_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} and {right}"


@r.node(type="short_circuit_or_operator")
def short_circuit_or_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} or {right}"


@r.node(type="not_operator")
def not_operator(node):
    operand = r.render(node["operand"])
    return f"not {operand}"


@r.node(type="unary_minus_operator")
def unary_minus_operator(node):
    operand = r.render(node["operand"])
    return f"-{operand}"


@r.node(type="unary_plus_operator")
def unary_plus_operator(node):
    operand = r.render(node["operand"])
    return f"+{operand}"


@r.node(type="postfix_increment_operator")
def postfix_increment_operator(node):
    # Python doesn't have increment operators, so we'll use += 1
    operand = r.render(node["operand"])
    return f"{operand} += 1"


@r.node(type="postfix_decrement_operator")
def postfix_decrement_operator(node):
    # Python doesn't have decrement operators, so we'll use -= 1
    operand = r.render(node["operand"])
    return f"{operand} -= 1"


@r.node(type="prefix_increment_operator")
def prefix_increment_operator(node):
    # Python doesn't have increment operators, so we'll use += 1
    operand = r.render(node["operand"])
    return f"{operand} += 1"


@r.node(type="prefix_decrement_operator")
def prefix_decrement_operator(node):
    # Python doesn't have decrement operators, so we'll use -= 1
    operand = r.render(node["operand"])
    return f"{operand} -= 1"


@r.node(type="identifier")
def identifier(node):
    return node["name"]


@r.node(type="int_literal")
def int_literal(node):
    return str(node["value"])


@r.node(type="assignment_statement")
def assignment_statement(node):
    target = r.render(node["target"])
    value = r.render(node["value"])
    return f"{target} = {value};"
