from typing import Literal, List
from dataclasses import dataclass

from src.types import NodeType, Node


Verb = Literal[
    "parent_of", "type", "body", "cond", "branches_item", "next_sibling"
]


@dataclass(init=False)
class StatementFact:
    subject_id: str
    subject_type: NodeType
    verb: Verb
    object_id: str
    object_type: NodeType

    def __init__(self, subject: Node, verb: Verb, object: Node):
        self.subject_id = subject["id"]
        self.subject_type = subject["type"]
        self.verb = verb
        self.object_id = object["id"]
        self.object_type = object["type"]


@dataclass
class CompPrehensionQuestion:
    type: str
    name: str
    statement_facts: List[StatementFact]
