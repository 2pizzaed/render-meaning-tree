from jinja2 import Environment, FileSystemLoader

from src.renderer import Renderer, CodeBlock
from src.meaning_tree import to_dict
from src.html_utils import add_indent_lines, syntax_highlight


environment = Environment(loader=FileSystemLoader("templates/"))
r = Renderer()

JAVA_SYNTAX_HIGHTLIGHT = {
    "keywords": ("if", "else", "for", "while"),
    "special": "{}()=<>;+-/*",
    "comment": ("//",),
    "string": ('"', "'"),
    "multiline_comments": (("/*", "*/"),),
}


@r.node(type="program_entry_point")
def program_entry_point(node):
    template = environment.get_template("base.html")

    block = CodeBlock(r.indenter)
    for child in node["body"]:
        block.add(r.render(child))

    lines = syntax_highlight(block.lines, **JAVA_SYNTAX_HIGHTLIGHT)

    lines = add_indent_lines(lines)

    codeline_template = environment.get_template("utils/codeline.html")
    codelines = [codeline_template.render(line=line) for line in lines]
    return template.render(body=codelines)


@r.node(type="if_statement")
def if_statement(node):
    block = CodeBlock(r.indenter)

    for i, branch in enumerate(node["branches"]):
        if i == 0:
            header = "if (%s) {" % r.render(branch["condition"])
        elif "condition" in branch:
            header = "} else if (%s) {" % r.render(branch["condition"])
        else:
            header = "} else {"

        block.add(header)
        block.add_with_indent(r.render(branch["body"]))

    block.add("}")
    return block.lines


@r.node(type="while_loop")
def while_statement(node):
    header = "while (%s) {" % r.render(node["condition"])
    footer = "}"

    block = CodeBlock(r.indenter)
    block.add(header)
    block.add_with_indent(r.render(node["body"]))
    block.add(footer)

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
        # Если неизвестен тип, по умолчанию считаем, что инкремент идёт вверх
        condition = f"{identifier} < {stop}"
        increment = f"{identifier} += {step}"
    elif range_type == "down":
        condition = f"{identifier} > {stop}"
        increment = f"{identifier} -= {step}"
    else:
        # На случай непредвиденного значения
        condition = f"{identifier} < {stop}"
        increment = f"{identifier} += {step}"

    initialization = f"int {identifier} = {start}"
    header = "for (%s; %s; %s) {" % (initialization, condition, increment)
    footer = "}"

    block = CodeBlock(r.indenter)
    block.add(header)
    block.add_with_indent(r.render(node["body"]))
    block.add(footer)

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
    return f"{left} / {right}"


@r.node(type="mod_operator")
def mod_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} % {right}"


@r.node(type="floor_div_operator")
def floor_div_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    # В Java деление с округлением вниз выглядит как: Math.floorDiv(a, b)
    return f"Math.floorDiv({left}, {right})"


@r.node(type="pow_operator")
def pow_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    # В Java возведение в степень реализуется через Math.pow(a, b)
    return f"Math.pow({left}, {right})"


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
    # Для проверки ссылочной эквивалентности в Java обычно используется ==.
    return f"{left} == {right}"


@r.node(type="short_circuit_and_operator")
def short_circuit_and_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} && {right}"


@r.node(type="short_circuit_or_operator")
def short_circuit_or_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} || {right}"


@r.node(type="unary_operator")
def not_operator(node):
    operand = r.render(node["operand"])
    return f"!{operand}"


@r.node(type="unary_minus_operator")
def unary_minus_operator(node):
    operand = r.render(node["operand"])
    return f"-{operand}"


@r.node(type="unary_plus_operator")
def unary_plus_operator(node):
    operand = r.render(node["operand"])
    return f"+{operand}"


@r.node(type="unary_postfix_inc_operator")
def postfix_increment_operator(node):
    operand = r.render(node["operand"])
    return f"{operand}++"


@r.node(type="unary_postfix_dec_operator")
def postfix_decrement_operator(node):
    operand = r.render(node["operand"])
    return f"{operand}--"


@r.node(type="unary_prefix_inc_operator")
def prefix_increment_operator(node):
    operand = r.render(node["operand"])
    return f"++{operand}"


@r.node(type="unary_prefix_dec_operator")
def prefix_decrement_operator(node):
    operand = r.render(node["operand"])
    return f"--{operand}"


@r.node(type="identifier")
def identifier(node):
    return node["name"]


@r.node(type="int_literal")
def int_literal(node):
    return node["value"]


@r.node(type="assignment_statement")
def assignment_statement(node):
    target = r.render(node["target"])
    value = r.render(node["value"])
    return f"{target} = {value};"


def save_as_html(node):
    content = r.render(node)
    with open("result.html", "w") as output_file:
        output_file.write(content)


if __name__ == "__main__":
    code = """
    while (a == 10)
    if (a < 3) {
        b = b + 6;
    } else if (a < 12) {
        if (b < 13) {
            a = a + 2;
        } else {
            a = a + 1;
        }
    } else {
        a = a + 1;
    }
    """

    save_as_html(to_dict("java", code))
