from typing import Dict, Any
from src.meaning_tree import to_dict


def test_java_to_dict_conversion():
    code = """
    if (a < 3) {
        b = b + 6;
    }
    """
    
    result = to_dict("java", code)
    
    assert result is not None, "Result should not be None"
    
    tree: Dict[str, Any] = result
    
    assert tree["type"] == "program_entry_point"
    assert "body" in tree
    
    if_statement = tree["body"][0]
    assert if_statement["type"] == "if_statement"
    assert "branches" in if_statement
    
    branch = if_statement["branches"][0]
    assert "condition" in branch
    condition = branch["condition"]
    assert condition["type"] == "lt_operator"
    
    assert "body" in branch
    body = branch["body"]
    assert body["type"] == "compound_statement"
    
    assignment = body["statements"][0]
    assert assignment["type"] == "assignment_statement"
    assert "target" in assignment
    assert "value" in assignment
    
    addition = assignment["value"]
    assert addition["type"] == "add_operator"
    assert "left_operand" in addition
    assert "right_operand" in addition
    
    literal = addition["right_operand"]
    assert literal["type"] == "int_literal"
    assert literal["value"] == 6


def test_invalid_language():
    result = to_dict("nonexistent_language", "some code")
    assert result is None


def test_empty_code():
    result = to_dict("java", "")
    
    assert result is not None, "Empty code should produce a result"
    
    tree: Dict[str, Any] = result
    
    assert tree["type"] == "program_entry_point"
    assert "body" in tree
    assert len(tree["body"]) == 0 