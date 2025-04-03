from jinja2 import Environment, FileSystemLoader

from src.renderer import Renderer
from src.meaning_tree import to_dict


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
            lines.append("<div>if (%s) {</div>" % r.render(node["condition"]))
        elif "condition" in branch:
            lines.append("<div>} else if (%s) {</div>" % r.render(node["condition"]))
        else:
            lines.append("<div>} else {</div>")

        lines.append(r.render(node["body"]))
        lines.append("<div>}</div>")
    
    return "".join(lines)


@r.node(type="add_operator")
def add_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} + {right}"


@r.node(type="lt_operator")
def lt_operator(node):
    left = r.render(node["left_operand"])
    right = r.render(node["right_operand"])
    return f"{left} < {right}"


@r.node(type="identifier")
def identifier(node):
    return node["name"]


@r.node(type="int_literal")
def int_literal(node):
    return node["value"]


@r.node(type="compound_statement")
def compound_statement(node):
    return "".join(f"<div>{r.render(i)}</div>" for i in node["statements"])


@r.node(type="assignment_statement")
def assignment_statement(node):
    target = r.render(node["target"])
    value = r.render(node["value"])
    return f"{target} = {value}"


def save_as_html(node):
    content = r.render(node)
    with open("result.html", "w") as output_file:
        output_file.write(content)


if __name__ == '__main__':
    code = """
    if (a < 3) {
        b = b + 6;
    }
    """
    
    save_as_html(to_dict("java", code))
