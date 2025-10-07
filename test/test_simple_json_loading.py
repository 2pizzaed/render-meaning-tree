"""
Простой тест для загрузки JSON с использованием DictLikeDataclass
"""

import json
import pytest
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.common_utils import DictLikeDataclass, SelfValidatedEnum


class TestSimpleJsonLoading:
    
    def test_load_ast_from_json_simple(self):
        """Test loading AST from JSON file using simple approach"""
        try:
            with open("ast.json", "r") as f:
                ast_data = json.load(f)
            
            # Create a simple AST node dataclass
            @dataclass
            class ASTNode(DictLikeDataclass):
                type: str
                id: Optional[int] = None
                name: Optional[str] = None
                value: Optional[Any] = None
                body: Optional[List[Dict[str, Any]]] = None
                branches: Optional[List[Dict[str, Any]]] = None
                condition: Optional[Dict[str, Any]] = None
                target: Optional[Dict[str, Any]] = None
                left_operand: Optional[Dict[str, Any]] = None
                right_operand: Optional[Dict[str, Any]] = None
                operand: Optional[Dict[str, Any]] = None
                statements: Optional[List[Dict[str, Any]]] = None
                elseBranch: Optional[Dict[str, Any]] = None
                repr: Optional[str] = None
            
            # Load AST using DictLikeDataclass
            ast = ASTNode.make(ast_data)
            
            # Test basic structure
            assert ast.type == "program_entry_point"
            assert ast.id == 62
            assert ast.body is not None
            assert len(ast.body) == 2
            
            # Test dict-like access
            assert ast['type'] == "program_entry_point"
            assert ast['id'] == 62
            assert len(ast['body']) == 2
            
            # Test first statement
            first_stmt = ast.body[0]
            assert first_stmt["type"] == "assignment_statement"
            assert first_stmt["id"] == 4
            assert first_stmt["target"]["type"] == "identifier"
            assert first_stmt["target"]["name"] == "a"
            assert first_stmt["value"]["type"] == "int_literal"
            assert first_stmt["value"]["value"] == 10
            
            # Test dict-like access to nested data
            assert ast['body'][0]['type'] == "assignment_statement"
            assert ast['body'][0]['target']['name'] == "a"
            assert ast['body'][0]['value']['value'] == 10
            
            # Test modification through dict access
            original_name = ast['body'][0]['target']['name']
            ast['body'][0]['target']['name'] = "modified_a"
            assert ast['body'][0]['target']['name'] == "modified_a"
            assert ast.body[0]['target']['name'] == "modified_a"  # Should be synced
            
            # Restore original value
            ast['body'][0]['target']['name'] = original_name
            assert ast['body'][0]['target']['name'] == "a"
            
        except FileNotFoundError:
            pytest.skip("ast.json file not found")
    
    def test_load_complex_nested_structure(self):
        """Test loading complex nested JSON structure"""
        try:
            with open("ast.json", "r") as f:
                ast_data = json.load(f)
            
            @dataclass
            class ASTNode(DictLikeDataclass):
                type: str
                id: Optional[int] = None
                name: Optional[str] = None
                value: Optional[Any] = None
                body: Optional[List[Dict[str, Any]]] = None
                branches: Optional[List[Dict[str, Any]]] = None
                condition: Optional[Dict[str, Any]] = None
                target: Optional[Dict[str, Any]] = None
                left_operand: Optional[Dict[str, Any]] = None
                right_operand: Optional[Dict[str, Any]] = None
                operand: Optional[Dict[str, Any]] = None
                statements: Optional[List[Dict[str, Any]]] = None
                elseBranch: Optional[Dict[str, Any]] = None
                repr: Optional[str] = None
            
            ast = ASTNode.make(ast_data)
            
            # Test complex nested access
            if_statement = ast.body[1]  # Second statement should be if_statement
            assert if_statement["type"] == "if_statement"
            
            # Test branches access
            branches = if_statement["branches"]
            assert len(branches) == 6
            
            # Test first branch
            first_branch = branches[0]
            assert first_branch["type"] == "condition_branch"
            assert first_branch["condition"]["type"] == "gt_operator"
            
            # Test dict-like access to deeply nested data
            assert ast['body'][1]['branches'][0]['condition']['left_operand']['name'] == "b"
            assert ast['body'][1]['branches'][0]['condition']['right_operand']['value'] == 10
            
            # Test modification of deeply nested data
            original_value = ast['body'][1]['branches'][0]['condition']['right_operand']['value']
            ast['body'][1]['branches'][0]['condition']['right_operand']['value'] = 999
            assert ast['body'][1]['branches'][0]['condition']['right_operand']['value'] == 999
            
            # Restore original value
            ast['body'][1]['branches'][0]['condition']['right_operand']['value'] = original_value
            assert ast['body'][1]['branches'][0]['condition']['right_operand']['value'] == 10
            
        except FileNotFoundError:
            pytest.skip("ast.json file not found")
    
    def test_error_handling_missing_file(self):
        """Test error handling for missing file"""
        with pytest.raises(FileNotFoundError):
            with open("nonexistent.json", "r") as f:
                json.load(f)
    
    def test_dict_like_operations(self):
        """Test various dict-like operations on loaded data"""
        try:
            with open("ast.json", "r") as f:
                ast_data = json.load(f)
            
            @dataclass
            class ASTNode(DictLikeDataclass):
                type: str
                id: Optional[int] = None
                name: Optional[str] = None
                value: Optional[Any] = None
                body: Optional[List[Dict[str, Any]]] = None
                branches: Optional[List[Dict[str, Any]]] = None
                condition: Optional[Dict[str, Any]] = None
                target: Optional[Dict[str, Any]] = None
                left_operand: Optional[Dict[str, Any]] = None
                right_operand: Optional[Dict[str, Any]] = None
                operand: Optional[Dict[str, Any]] = None
                statements: Optional[List[Dict[str, Any]]] = None
                elseBranch: Optional[Dict[str, Any]] = None
                repr: Optional[str] = None
            
            ast = ASTNode.make(ast_data)
            
            # Test __contains__ (in operator)
            assert 'type' in ast
            assert 'id' in ast
            assert 'body' in ast
            assert 'nonexistent' not in ast
            
            # Test get() method
            assert ast.get('type') == "program_entry_point"
            assert ast.get('id') == 62
            assert ast.get('nonexistent') is None
            assert ast.get('nonexistent', 'default') == 'default'
            
            # Test __setitem__ and __getitem__
            original_type = ast['type']
            ast['type'] = "modified_program"
            assert ast['type'] == "modified_program"
            assert ast.type == "modified_program"  # Should be synced
            
            # Restore original value
            ast['type'] = original_type
            assert ast['type'] == "program_entry_point"
            
        except FileNotFoundError:
            pytest.skip("ast.json file not found")
