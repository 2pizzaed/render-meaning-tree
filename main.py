from jinja2 import Environment, FileSystemLoader

from renderer import Renderer


environment = Environment(
    loader=FileSystemLoader("templates/")
)
r = Renderer()


@r.node(type="program_entry_point")
def program_entry_point(node):
    template = environment.get_template("base.html")
    return template.render()


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
