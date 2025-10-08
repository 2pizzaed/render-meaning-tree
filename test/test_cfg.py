import json
import unittest

from src.cfg import ASTNodeWrapper
from src.cfg import CFGBuilder
from src.cfg.abstractions import load_constructs

import os
os.chdir("..")

class TestCfgBuilder(unittest.TestCase):

    def test_cfg_builder1(self):

        with open("ast.json") as f:
           ast_json = json.load(f)

        # Create the full AST hierarchy
        program_root = ASTNodeWrapper(ast_node=ast_json)
        root = ASTNodeWrapper(ast_node=ast_json["body"][1], parent=program_root)

        constructs = load_constructs(debug=0)
        b = CFGBuilder(constructs)

        cfg = b.make_cfg_for_ast(root)

        # # Test that CFG was built correctly
        # self.assertIsNotNone(cfg)
        # self.assertEqual(cfg.name, "if_statement")
        #
        # # Test that we have the expected number of nodes and edges
        # self.assertEqual(len(cfg.nodes), 12)
        # self.assertEqual(len(cfg.edges), 12)
        #
        # # Test that we have BEGIN and END nodes
        # begin_nodes = [n for n in cfg.nodes.values() if n.role == "BEGIN"]
        # end_nodes = [n for n in cfg.nodes.values() if n.role == "END"]
        # self.assertEqual(len(begin_nodes), 3)  # Main CFG + 2 subgraphs
        # self.assertEqual(len(end_nodes), 3)    # Main CFG + 2 subgraphs
        #
        # # Test that we have a condition node
        # condition_nodes = [n for n in cfg.nodes.values() if n.role == "first_cond"]
        # self.assertEqual(len(condition_nodes), 1)
        #
        # # Test that we have if_branch and else_branch nodes
        # if_branch_nodes = [n for n in cfg.nodes.values() if n.role == "if_branch"]
        # else_branch_nodes = [n for n in cfg.nodes.values() if n.role == "else_branch"]
        # self.assertEqual(len(if_branch_nodes), 2)  # One for TRUE branch, one for FALSE branch
        # self.assertEqual(len(else_branch_nodes), 2)  # One for each branch
        #
        # # Test that we have transitions with constraints
        # transitions_with_constraints = [e for e in cfg.edges if e.metadata.abstract_transition and e.metadata.abstract_transition.constraints]
        # self.assertGreater(len(transitions_with_constraints), 0)
        #
        # # Test that we have transitions with condition_value constraints
        # condition_transitions = [e for e in cfg.edges
        #                        if e.metadata.abstract_transition and
        #                        e.metadata.abstract_transition.constraints and
        #                        e.metadata.abstract_transition.constraints.condition_value is not None]
        # self.assertEqual(len(condition_transitions), 2)  # TRUE and FALSE transitions
        #
        # # Test that condition transitions have correct values
        # true_transitions = [e for e in condition_transitions
        #                   if e.metadata.abstract_transition.constraints.condition_value == True]
        # false_transitions = [e for e in condition_transitions
        #                    if e.metadata.abstract_transition.constraints.condition_value == False]
        # self.assertEqual(len(true_transitions), 1)
        # self.assertEqual(len(false_transitions), 1)
        
        cfg.debug()

    def test_cfg_builder4(self):

        with open("ast4.json") as f:
           ast_json = json.load(f)

        # Create the full AST hierarchy
        program_root = ASTNodeWrapper(ast_node=ast_json)
        root = ASTNodeWrapper(ast_node=ast_json["body"][1], parent=program_root)

        constructs = load_constructs(debug=True)
        b = CFGBuilder(constructs)

        cfg = b.make_cfg_for_ast(root)

        # Test that CFG was built correctly
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.name, "if_statement")

        # Test that we have the expected number of nodes and edges
        self.assertEqual(len(cfg.nodes), 12)
        self.assertEqual(len(cfg.edges), 12)

        # Test that we have BEGIN and END nodes
        begin_nodes = [n for n in cfg.nodes.values() if n.role == "BEGIN"]
        end_nodes = [n for n in cfg.nodes.values() if n.role == "END"]
        self.assertEqual(len(begin_nodes), 3)  # Main CFG + 2 subgraphs
        self.assertEqual(len(end_nodes), 3)    # Main CFG + 2 subgraphs

        # Test that we have a condition node
        condition_nodes = [n for n in cfg.nodes.values() if n.role == "first_cond"]
        self.assertEqual(len(condition_nodes), 1)

        # Test that we have if_branch and else_branch nodes
        if_branch_nodes = [n for n in cfg.nodes.values() if n.role == "if_branch"]
        else_branch_nodes = [n for n in cfg.nodes.values() if n.role == "else_branch"]
        self.assertEqual(len(if_branch_nodes), 2)  # One for TRUE branch, one for FALSE branch
        self.assertEqual(len(else_branch_nodes), 2)  # One for each branch

        # Test that we have transitions with constraints
        transitions_with_constraints = [e for e in cfg.edges if e.metadata.abstract_transition and e.metadata.abstract_transition.constraints]
        self.assertGreater(len(transitions_with_constraints), 0)

        # Test that we have transitions with condition_value constraints
        condition_transitions = [e for e in cfg.edges
                               if e.metadata.abstract_transition and
                               e.metadata.abstract_transition.constraints and
                               e.metadata.abstract_transition.constraints.condition_value is not None]
        self.assertEqual(len(condition_transitions), 2)  # TRUE and FALSE transitions

        # Test that condition transitions have correct values
        true_transitions = [e for e in condition_transitions
                          if e.metadata.abstract_transition.constraints.condition_value == True]
        false_transitions = [e for e in condition_transitions
                           if e.metadata.abstract_transition.constraints.condition_value == False]
        self.assertEqual(len(true_transitions), 1)
        self.assertEqual(len(false_transitions), 1)

        cfg.debug()

    def test_cfg_builder5(self):

        with open("ast5.json") as f:
           ast_json = json.load(f)

        # Create the full AST hierarchy
        program_root = ASTNodeWrapper(ast_node=ast_json)
        root = ASTNodeWrapper(ast_node=ast_json["body"][1], parent=program_root)

        constructs = load_constructs(debug=True)
        b = CFGBuilder(constructs)

        cfg = b.make_cfg_for_ast(root)

        # Test that CFG was built correctly
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.name, "if_statement")

        # Test that CFG was built successfully
        self.assertGreater(len(cfg.nodes), 0)
        self.assertGreater(len(cfg.edges), 0)
        
        # Test that we have BEGIN and END nodes
        begin_nodes = [n for n in cfg.nodes.values() if n.role == "BEGIN"]
        end_nodes = [n for n in cfg.nodes.values() if n.role == "END"]
        self.assertGreater(len(begin_nodes), 0)
        self.assertGreater(len(end_nodes), 0)

        # Test that we have a condition node
        condition_nodes = [n for n in cfg.nodes.values() if n.role == "first_cond"]
        self.assertEqual(len(condition_nodes), 1)

        # Test that we have if_branch and else_branch nodes
        if_branch_nodes = [n for n in cfg.nodes.values() if n.role == "if_branch"]
        else_branch_nodes = [n for n in cfg.nodes.values() if n.role == "else_branch"]
        self.assertGreater(len(if_branch_nodes), 0)  # At least one if_branch
        self.assertGreater(len(else_branch_nodes), 0)  # At least one else_branch

        # Test that we have transitions with constraints
        transitions_with_constraints = [e for e in cfg.edges if e.metadata.abstract_transition and e.metadata.abstract_transition.constraints]
        self.assertGreater(len(transitions_with_constraints), 0)

        # Test that we have transitions with condition_value constraints
        condition_transitions = [e for e in cfg.edges
                               if e.metadata.abstract_transition and
                               e.metadata.abstract_transition.constraints and
                               e.metadata.abstract_transition.constraints.condition_value is not None]
        self.assertGreater(len(condition_transitions), 0)  # At least one condition transition

        cfg.debug()


