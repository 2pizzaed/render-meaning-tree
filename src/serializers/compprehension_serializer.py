from typing import List
from dataclasses import dataclass

from src.types import Node
from src.serializers.types import StatementFact, CompPrehensionQuestion
from renderer import Serializer


s = Serializer()


def serialize(node: Node) -> CompPrehensionQuestion:
    return CompPrehensionQuestion(
        type="", # TODO
        name="", # TODO
        statement_facts=s.serialize(node)
    )


@s.node(type="program_entry_point")
def program_entry_point(node: Node) -> List[StatementFact]:
    children = node["body"]
    
    stmt_facts = [StatementFact(node, "parent_of", child)
                  for child in children]
    
    stmt_facts += [StatementFact(sub, "next_sibling", obj) 
                   for sub, obj in zip(children, children[1:])]
    
    stmt_facts += [s.serialize(child) for child in children]
    
    return stmt_facts


@s.node(type="compound_statement")
def compound_stmt(node: Node) -> List[StatementFact]:
    children = node["statements"]
    
    stmt_facts = [StatementFact(node, "parent_of", child)
                  for child in children]
    
    stmt_facts += [StatementFact(sub, "next_sibling", obj)
                   for sub, obj in zip(children, children[1:])]
    
    return stmt_facts
    