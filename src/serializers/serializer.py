from typing import Dict, Any, List

from src.types import Node, NodeType


class SerializerNotFoundError(Exception):
    pass


class Serializer:
    def __init__(self) -> None:
        self.serialize_funcs: Dict[NodeType, Any] = {}

    def node(self, *, type: NodeType):
        def decorator(func):
            self.serialize_funcs[type] = func
            return func

        return decorator

    def nodes(self, *, types: List[NodeType]):
        def decorator(func):
            [self.node(type=type)(func) for type in types]
            return func

        return decorator

    def serialize(self, node: Node) -> Any:
        node_type = node.get("type")
        if node_type in self.serialize_funcs:
            return self.serialize_funcs[node_type](node)

        raise SerializerNotFoundError(f"No serializer function found for '{node_type}'")
