from typing import Literal, List, Any
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

    @classmethod
    def make(cls, subject_id: str, verb: Verb, object_id: str, subject_type: str = '', object_type: str = ''):
        return StatementFact(
            dict(id=subject_id, type=subject_type),
            verb,
            dict(id=object_id, type=object_type))

    @classmethod
    def make_relation(cls, subject_id: str, verb: Verb, object_id: str):
        return cls.make(subject_id, verb, object_id, object_type='owl:NamedIndividual')

    @classmethod
    def make_property(cls, subject_id: str, verb: Verb, object_id: Any):
        return cls.make(subject_id, verb, str(object_id), object_type='xsd:' + type(object_id).__name__)


@dataclass
class CompPrehensionQuestion:
    type: str
    name: str
    statement_facts: List[StatementFact]


class FactSerializable:
    def serialize(self) -> List[StatementFact]:
        """ Serialize the object to a list of StatementFacts.
         Attributes are specified in the _relation_attr_names and _property_attr_names class variables.
         """
        self_id = self.subject_id()
        facts = []
        if hasattr(self, "_relation_attr_names"):
            facts += [
                StatementFact.make_relation(
                    self_id,
                    attr,
                    getattr(self, attr)
                )
                for attr in self._relation_attr_names if hasattr(self, attr)
            ]
        if hasattr(self, "_property_attr_names"):
            facts += [
                StatementFact.make_property(
                    self_id,
                    attr,
                    getattr(self, attr)
                )
                for attr in self._property_attr_names if hasattr(self, attr)
            ]
        return facts

    def subject_id(self) -> str:
        """ Return the subject id of the object """
        if hasattr(self, "id"):
            return f'{type(self).__name__}#{self.id}'
        raise NotImplementedError
