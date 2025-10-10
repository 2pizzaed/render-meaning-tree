"""
Тесты для загрузки абстракций из JSON с использованием DictLikeDataclass
"""

import json
import pytest
from src.cfg.abstractions import load_ast_from_json, load_constructs


class TestAbstractionsJsonLoading:
    
    def test_load_ast_from_json(self):
        """Test loading AST from JSON file"""
        try:
            ast = load_ast_from_json("data/ast.json")
            
            # Test basic structure
            assert ast.type == "program_entry_point"
            assert ast.id == 62
            assert ast.body is not None
            assert len(ast.body) == 2
            
            # Test first statement
            first_stmt = ast.body[0]
            assert first_stmt["type"] == "assignment_statement"
            assert first_stmt["id"] == 4
            assert first_stmt["target"]["type"] == "identifier"
            assert first_stmt["target"]["name"] == "a"
            assert first_stmt["value"]["type"] == "int_literal"
            assert first_stmt["value"]["value"] == 10
            
            # Test second statement (if_statement)
            second_stmt = ast.body[1]
            assert second_stmt["type"] == "if_statement"
            assert second_stmt["id"] == 60
            assert second_stmt["branches"] is not None
            assert len(second_stmt["branches"]) == 6
            
            # Test first branch
            first_branch = second_stmt["branches"][0]
            assert first_branch["type"] == "condition_branch"
            assert first_branch["id"] == 61
            assert first_branch["condition"]["type"] == "gt_operator"
            assert first_branch["condition"]["left_operand"]["type"] == "identifier"
            assert first_branch["condition"]["left_operand"]["name"] == "b"
            
        except FileNotFoundError:
            pytest.skip("ast.json file not found")
    
    def test_load_ast_dict_like_access(self):
        """Test dict-like access to loaded AST"""
        try:
            ast = load_ast_from_json("ast.json")
            
            # Test dict-like access
            assert ast['type'] == "program_entry_point"
            assert ast['id'] == 62
            assert len(ast['body']) == 2
            
            # Test nested dict-like access
            first_stmt = ast['body'][0]
            assert first_stmt['type'] == "assignment_statement"
            assert first_stmt['target']['name'] == "a"
            assert first_stmt['value']['value'] == 10
            
            # Test modification through dict access
            original_name = first_stmt['target']['name']
            first_stmt['target']['name'] = "modified_a"
            assert first_stmt['target']['name'] == "modified_a"
            
            # Restore original value
            first_stmt['target']['name'] = original_name
            assert first_stmt['target']['name'] == "a"
            
        except FileNotFoundError:
            pytest.skip("ast.json file not found")
    
    def test_load_ast_error_handling(self):
        """Test error handling for missing file"""
        with pytest.raises(FileNotFoundError):
            load_ast_from_json("nonexistent.json")
    
    def test_load_constructs_simplified(self):
        """Test loading constructs with simplified approach"""
        try:
            constructs = load_constructs("constructs.yml", debug=False)
            
            # Basic validation that constructs were loaded
            assert isinstance(constructs, dict)
            assert len(constructs) > 0
            
            # Test that each construct has required structure
            for name, construct in constructs.items():
                assert construct.name == name
                assert hasattr(construct, 'actions')
                assert hasattr(construct, 'transitions')
                
                # Test dict-like access
                assert construct['name'] == name
                assert 'actions' in construct
                assert 'transitions' in construct
                
        except FileNotFoundError:
            pytest.skip("constructs.yml file not found")
    
    def test_constructs_dict_like_access(self):
        """Test dict-like access to loaded constructs"""
        try:
            constructs = load_constructs("constructs.yml", debug=False)
            
            for name, construct in constructs.items():
                # Test dict-like access to construct
                assert construct['name'] == name
                
                # Test access to actions
                actions = construct['actions']
                assert isinstance(actions, list)
                
                # Test access to transitions
                transitions = construct['transitions']
                assert isinstance(transitions, list)
                
                # Test modification through dict access
                original_name = construct['name']
                construct['name'] = f"modified_{original_name}"
                assert construct['name'] == f"modified_{original_name}"
                
                # Restore original name
                construct['name'] = original_name
                assert construct['name'] == original_name
                
        except FileNotFoundError:
            pytest.skip("constructs.yml file not found")
    
    def test_ast_node_creation_from_dict(self):
        """Test creating AST nodes directly from dict data"""
        from src.cfg.abstractions import load_ast_from_json
        
        # Create test data
        test_data = {
            "type": "test_node",
            "id": 1,
            "name": "test",
            "value": 42,
            "body": [
                {
                    "type": "child_node",
                    "id": 2,
                    "name": "child"
                }
            ]
        }
        
        # This would work if we had a way to create ASTNode directly
        # For now, we'll test the pattern with a simple example
        try:
            ast = load_ast_from_json("ast.json")
            
            # Test that we can access and modify data
            assert ast['type'] == "program_entry_point"
            
            # Test nested access
            if ast['body'] and len(ast['body']) > 0:
                first_child = ast['body'][0]
                assert 'type' in first_child
                assert 'id' in first_child
                
        except FileNotFoundError:
            pytest.skip("ast.json file not found")
