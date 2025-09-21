from typing import Any

from src.serializers.serializer import Serializer, SerializerNotFoundError
from src.types import Node


class CfgBuilder(Serializer):
    """Строит CFG из узлов meaning-tree, представленных в json-форме.
    """

    def __init__(self) -> None:
        super().__init__()

    def build(self, node: Node) -> Any:
        try:
            return self.serialize(node)
        except SerializerNotFoundError:
            print(f"Notice: no CFG made for node: {node}")
            return None

