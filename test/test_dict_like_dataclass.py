import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import pytest

from src.common_utils import DictLikeDataclass, SelfValidatedEnum


class SampleEnum(SelfValidatedEnum):
    VALUE1 = "value1"
    VALUE2 = "value2"


@dataclass
class SimpleNode(DictLikeDataclass):
    id: int
    name: str
    value: Optional[float] = None


@dataclass
class ComplexNode(DictLikeDataclass):
    id: int
    name: str
    children: List[SimpleNode] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    node_type: Optional[SampleEnum] = None
    parent: Optional['ComplexNode'] = None

    _static_field = ('b', 'x')


@dataclass
class RootNode(DictLikeDataclass):
    type: str
    body: List[ComplexNode] = field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class TestDictLikeDataclass:
    
    def test_simple_node_creation(self):
        """Test creating a simple node from JSON data"""
        data = {
            "id": 1,
            "name": "test_node",
            "value": 3.14
        }
        
        result = SimpleNode.make(data)
        
        assert result.id == 1
        assert result.name == "test_node"
        assert result.value == 3.14
        
        # Test dict-like access
        assert result['id'] == 1
        assert result['name'] == "test_node"
        assert result['value'] == 3.14
    
    def test_simple_node_with_optional_field(self):
        """Test creating a simple node with optional field missing"""
        data = {
            "id": 1,
            "name": "test_node"
        }
        
        result = SimpleNode.make(data)
        
        assert result.id == 1
        assert result.name == "test_node"
        assert result.value is None
        assert result['id'] == 1
        assert result['name'] == "test_node"
        assert result['value'] is None

    def test_simple_node_missing_mandatory_field(self):
        """Test error when mandatory field is missing"""
        data = {
            "id": 1
            # name is missing
        }
        
        with pytest.raises(ValueError, match="Mandatory field 'name' is missing"):
            SimpleNode.make(data)
    
    def test_simple_node_unknown_field(self):
        """Test error when unknown field is present"""
        data = {
            "id": 1,
            "name": "test_node",
            "unknown_field": "value"
        }
        
        with pytest.raises(ValueError, match="Unknown keys in data"):
            SimpleNode.make(data)
    
    def test_complex_node_with_children(self):
        """Test creating a complex node with children"""
        data = {
            "id": 1,
            "name": "parent",
            "children": [
                {
                    "id": 2,
                    "name": "child1",
                    "value": 1.0
                },
                {
                    "id": 3,
                    "name": "child2",
                    "value": 2.0
                }
            ],
            "metadata": {
                "key1": "value1",
                "key2": 42
            },
            "node_type": "value1"
        }
        
        result = ComplexNode.make(data)
        
        assert result.id == 1
        assert result.name == "parent"
        assert len(result.children) == 2
        assert result.children[0].id == 2
        assert result.children[0].name == "child1"
        assert result.children[0].value == 1.0
        assert result.children[1].id == 3
        assert result.children[1].name == "child2"
        assert result.children[1].value == 2.0
        assert result.metadata["key1"] == "value1"
        assert result.metadata["key2"] == 42
        assert result.node_type == SampleEnum.VALUE1
        assert result._static_field == ('b', 'x')
        assert result['_static_field'] == ('b', 'x')
        assert '_static_field' in result

    def test_enum_conversion(self):
        """Test enum value conversion"""
        data = {
            "id": 1,
            "name": "test",
            "node_type": "value2"
        }
        
        result = ComplexNode.make(data)
        
        assert result.node_type == SampleEnum.VALUE2
    
    def test_invalid_enum_value(self):
        """Test error with invalid enum value"""
        data = {
            "id": 1,
            "name": "test",
            "node_type": "invalid_value"
        }
        
        with pytest.raises(ValueError, match="Invalid value for enum"):
            ComplexNode.make(data)
    
    def test_nested_dataclass_creation(self):
        """Test creating nested dataclass structures"""
        data = {
            "type": "program_entry_point",
            "body": [
                {
                    "id": 1,
                    "name": "statement1",
                    "children": [
                        {
                            "id": 2,
                            "name": "child1"
                        }
                    ]
                }
            ],
            "metadata": {
                "version": "1.0"
            }
        }
        
        result = RootNode.make(data)
        
        assert result.type == "program_entry_point"
        assert len(result.body) == 1
        assert result.body[0].id == 1
        assert result.body[0].name == "statement1"
        assert len(result.body[0].children) == 1
        assert result.body[0].children[0].id == 2
        assert result.body[0].children[0].name == "child1"
        assert result.metadata["version"] == "1.0"
    
    def test_ast_json_parsing(self):
        """Test parsing actual AST JSON data"""
        with open("ast.json") as f:
            ast_data = json.load(f)
        
        # Create a simple dataclass to represent AST nodes without forward references
        @dataclass
        class ASTNode(DictLikeDataclass):
            type: str
            id: Optional[int] = None
            name: Optional[str] = None
            value: Optional[Any] = None
            body: Optional[List[Any]] = None
            branches: Optional[List[Any]] = None
            condition: Optional[Any] = None
            target: Optional[Any] = None
            left_operand: Optional[Any] = None
            right_operand: Optional[Any] = None
            operand: Optional[Any] = None
            statements: Optional[List[Any]] = None
            elseBranch: Optional[Any] = None
            repr: Optional[str] = None
        
        result = ASTNode.make(ast_data)
        
        assert result.type == "program_entry_point"
        assert result.id == 62
        assert result.body is not None
        assert len(result.body) == 2
        
        # Check first statement (assignment)
        first_stmt = result.body[0]
        assert first_stmt["type"] == "assignment_statement"
        assert first_stmt["id"] == 4
        assert first_stmt["target"] is not None
        assert first_stmt["target"]["type"] == "identifier"
        assert first_stmt["target"]["name"] == "a"
        assert first_stmt["value"] is not None
        assert first_stmt["value"]["type"] == "int_literal"
        assert first_stmt["value"]["value"] == 10
        
        # Check second statement (if_statement)
        second_stmt = result.body[1]
        assert second_stmt["type"] == "if_statement"
        assert second_stmt["id"] == 60
        assert second_stmt["branches"] is not None
        assert len(second_stmt["branches"]) == 6
        
        # Check first branch
        first_branch = second_stmt["branches"][0]
        assert first_branch["type"] == "condition_branch"
        assert first_branch["id"] == 61
        assert first_branch["condition"] is not None
        assert first_branch["condition"]["type"] == "gt_operator"
        assert first_branch["condition"]["left_operand"] is not None
        assert first_branch["condition"]["left_operand"]["type"] == "identifier"
        assert first_branch["condition"]["left_operand"]["name"] == "b"
    
    def test_type_conversion_errors(self):
        """Test various type conversion error cases"""
        # Test wrong type for list field
        data = {
            "id": 1,
            "name": "test",
            "children": "not_a_list"  # Should be a list
        }
        
        with pytest.raises(ValueError, match="Expected list for field"):
            ComplexNode.make(data)
        
        # Test wrong type for dict field
        data = {
            "id": 1,
            "name": "test",
            "metadata": "not_a_dict"  # Should be a dict
        }
        
        with pytest.raises(ValueError, match="Expected dict for field"):
            ComplexNode.make(data)
        
        # Test wrong type for int field
        data = {
            "id": "not_an_int",  # Should be an int
            "name": "test"
        }
        
        with pytest.raises(ValueError, match="Cannot convert"):
            SimpleNode.make(data)
    
    def test_dict_like_behavior(self):
        """Test dict-like behavior of DictLikeDataclass instances"""
        data = {
            "id": 1,
            "name": "test_node",
            "value": 3.14
        }
        
        result = SimpleNode.make(data)
        
        # Test __getitem__ (dict access)
        assert result['id'] == 1
        assert result['name'] == "test_node"
        assert result['value'] == 3.14
        
        # Test __setitem__ (dict assignment)
        result['name'] = "updated_name"
        result['value'] = 2.71
        assert result['name'] == "updated_name"
        assert result['value'] == 2.71
        assert result.name == "updated_name"  # Should also update attribute
        assert result.value == 2.71
        
        # Test __delitem__ (dict deletion)
        # Note: dataclass fields cannot be completely deleted, they become None
        del result['value']
        assert result.value is None  # Field becomes None after deletion
        
        # Test get() method
        assert result.get('id') == 1
        assert result.get('name') == "updated_name"
        assert result.get('value') is None  # Deleted
        assert result.get('missing_key') is None
        assert result.get('missing_key', 'default') == 'default'
        
        # Test __contains__ (in operator)
        assert 'id' in result
        assert 'name' in result
        assert 'value' in result  # Field still exists, just set to None
        assert 'missing_key' not in result
        
        # Test KeyError for missing keys
        with pytest.raises(AttributeError):
            _ = result['missing_key']
    
    def test_dict_like_with_complex_objects(self):
        """Test dict-like behavior with complex nested objects"""
        data = {
            "id": 1,
            "name": "parent",
            "children": [
                {
                    "id": 2,
                    "name": "child1",
                    "value": 1.0
                },
                {
                    "id": 3,
                    "name": "child2",
                    "value": 2.0
                }
            ],
            "metadata": {
                "key1": "value1",
                "key2": 42
            }
        }
        
        result = ComplexNode.make(data)
        
        # Test dict access to nested objects
        assert result['id'] == 1
        assert result['name'] == "parent"
        assert len(result['children']) == 2
        assert result['children'][0]['id'] == 2
        assert result['children'][0]['name'] == "child1"
        assert result['metadata']['key1'] == "value1"
        
        # Test dict modification
        result['name'] = "updated_parent"
        assert result['name'] == "updated_parent"
        assert result.name == "updated_parent"
        
        # Test nested dict access
        result['metadata']['key1'] = "updated_value"
        assert result['metadata']['key1'] == "updated_value"
        assert result.metadata['key1'] == "updated_value"
        
        # Test dict access to children
        result['children'][0]['name'] = "updated_child1"
        assert result['children'][0]['name'] == "updated_child1"
        assert result.children[0].name == "updated_child1"
