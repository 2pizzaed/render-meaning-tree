from typing import Dict, Any

from src.types import Node, NodeType


class SerializerNotFoundError(Exception):
    pass


class Serializer:
    def __init__(self) -> None:
        self.serizlize_funcs: Dict[NodeType, Any] = {}

    def node(self, *, type: NodeType):
        def decorator(func):
            self.serizlize_funcs[type] = func
            return func

        return decorator

    def serialize(self, node: Node) -> Any:
        node_type = node.get("type")
        if node_type in self.serizlize_funcs:
            return self.serizlize_funcs[node_type](node)

        raise SerializerNotFoundError(f"No serializer function found for '{node_type}'")
