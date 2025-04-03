from jinja2 import Environment, FileSystemLoader

from src.renderer import Renderer


environment = Environment(
    loader=FileSystemLoader("templates/")
)
r = Renderer()


@r.node(type="program_entry_point")
def program_entry_point(node):
    template = environment.get_template("base.html")
    body = [r.render(child) for child in node["body"]]
    return template.render(body=body)


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
    return [f"<div>{r.render(i)}</div>" for i in node["statements"]]


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
    save_as_html(
        {
        "type": "program_entry_point",
        "body": [
            {
                "type": "if_statement",
                "branches": [
                    {
                        "condition": {
                            "type": "lt_operator",
                            "left_operand": {
                                "type": "identifier",
                                "name": "a"
                            },
                            "right_operand": {
                                "type": "int_literal",
                                "value": 3,
                                "repr": "DECIMAL"
                            }
                        },
                        "body": {
                            "type": "compound_statement",
                            "statements": [
                                {
                                    "type": "assignment_statement",
                                    "target": {
                                        "type": "identifier",
                                        "name": "b"
                                    },
                                    "value": {
                                        "type": "add_operator",
                                        "left_operand": {
                                            "type": "identifier",
                                            "name": "b"
                                        },
                                        "right_operand": {
                                            "type": "int_literal",
                                            "value": 1,
                                            "repr": "DECIMAL"
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
)
