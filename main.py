from jinja2 import Environment, FileSystemLoader

from src.renderer import Renderer
from src.meaning_tree import to_dict
from src.html_utils import make_codeline


environment = Environment(
    loader=FileSystemLoader("templates/")
)
r = Renderer()


@r.node(type="program_entry_point")
def program_entry_point(node):
    template = environment.get_template("base.html")
    body = [r.render(child) for child in node["body"]]
    return template.render(body=body)


@r.node(type="if_statement")
def if_statement(node):
    lines = []

    for i, branch in enumerate(node["branches"]):
        if i == 0:
            lines.append(
                make_codeline("if (%s) {") % r.render(branch["condition"]))
        elif "condition" in branch:
            lines.append(
                make_codeline("else if (%s) {") % r.render(branch["condition"]))
        else:
            lines.append(
                make_codeline("} else {"))

        lines.append(r.render(branch["body"]))
        lines.append(make_codeline("}"))
    
    return "".join(lines)


@r.node(type="while_statement")
def while_statement(node):
    lines = [
        make_codeline("while (%s) {") % r.render(node["condition"]),
        r.render(node["body"]),
        make_codeline("}")
    ]
    return "".join(lines)


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
    
    lines = [
        make_codeline("for (%s; %s; %s) {" % (initialization, condition, increment)),
        r.render(node["body"]),
        make_codeline("}")
    ]
    return "".join(lines)


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


@r.node(type="compound_statement")
def compound_statement(node):
    return "".join(r.render(i) for i in node["statements"])


@r.node(type="assignment_statement")
def assignment_statement(node):
    target = r.render(node["target"])
    value = r.render(node["value"])
    return make_codeline(f"{target} = {value};")


def save_as_html(node):
    content = r.render(node)
    with open("result.html", "w") as output_file:
        output_file.write(content)


if __name__ == '__main__':
    code = """
    for (int i = 0; i < 10; i++) {
        b = i + 20;

        if (a < b) {
            a = b + 10;
        }
    }
    """
    
    save_as_html(to_dict("java", code))
