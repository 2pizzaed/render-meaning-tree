from functools import wraps


class Renderer:
    """Рендер узлов meaning-tree в json-форме.

    Пример использования:

    renderer = HtmlRenderer()

    @renderer.node(type="if")
    def if_stmt(node):
        return f"<h1>{node['condition']}</h1>"

    print(renderer.render({"type": "if", "condition": "True"}))
    """

    def __init__(self) -> None:
        self.render_funcs = {}

    def node(self, **node_attrs):
        
        def decorator(func):
            node_type = node_attrs.get("type")
            if node_type is None:
                raise ValueError("You need to provide node type")
            self.render_funcs[node_type] = func

            return func

        return decorator

    def render(self, node) -> str:
        node_type = node.get("type")
        if node_type in self.render_funcs:
            return self.render_funcs[node_type](node)
        
        raise ValueError(f"No renderer found for '{node_type}'")
