from jinja2 import Environment, FileSystemLoader

from src.renderer import Renderer, CodeBlock
from src.meaning_tree import to_dict
from src.html_utils import add_indent_lines, syntax_highlight
from src.cfg import cfg
import argparse


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
    from main import program_entry_point

    html = program_entry_point(node)
    with open("result.html", "w") as f:
        f.write(html)


def save_cfg(node, output_file="cfg.png"):
    graph = cfg.generate_cfg(node)
    return cfg.visualize(output_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process code into meaning tree and generate visualizations")
    parser.add_argument("--file", "-f", help="Java source file to process")
    parser.add_argument("--code", "-c", help="Java code string to process")
    parser.add_argument("--cfg", "-g", action="store_true", help="Generate control flow graph")
    parser.add_argument("--output", "-o", default="result", help="Output filename (without extension)")
    parser.add_argument("--analyze", "-a", action="store_true", help="Print CFG analysis information")
    
    args = parser.parse_args()
    
    if args.file:
        with open(args.file, "r") as f:
            code = f.read()
    elif args.code:
        code = args.code
    else:
        parser.print_help()
        exit(1)
    
    ast = to_dict("java", code)
    
    if not ast:
        print("Failed to parse the code")
        exit(1)
    
    html_output = f"{args.output}.html"
    save_as_html(ast)
    print(f"HTML output saved to {html_output}")
    
    if args.cfg:
        cfg_output = f"{args.output}_cfg.png"
        cfg_graph = cfg.generate_cfg(ast)
        cfg.visualize(cfg_output)
        print(f"Control flow graph saved to {cfg_output}")
        
        if args.analyze:
            print("\nCFG Analysis:")
            print(f"- Number of basic blocks: {len(cfg.blocks)}")
            print(f"- Reducible: {cfg.is_reducible()}")
            print(f"- Loop headers: {len(cfg.loop_headers)}")
            print(f"- Loop connectedness: {cfg.get_loop_connectedness()}")
            print(f"- Back edges: {len(cfg.back_edges)}")
            print(f"- Critical edges: {len(cfg.critical_edges)}")
            print(f"- Impossible edges: {len(cfg.impossible_edges)}")
    
    from src.serializers.compprehension_serializer import serialize
    from pprint import pprint
    pprint(serialize(ast)) 
    
    
    
