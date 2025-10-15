import json
import unittest

from src.cfg import ASTNodeWrapper
from src.cfg import CFGBuilder
from src.cfg.abstractions import load_constructs
from src.cfg.cfg_visualizer import visualize_cfg


class TestCfgBuilder(unittest.TestCase):

    def test_cfg_builder1(self):

        with open("data/ast.json") as f:
           ast_json = json.load(f)

        # Create the full AST hierarchy
        program_root = ASTNodeWrapper(ast_node=ast_json)
        root = ASTNodeWrapper(ast_node=ast_json["body"][1], parent=program_root)

        constructs = load_constructs("../constructs.yml", debug=0)
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

        with open("data/ast4.json") as f:
           ast_json = json.load(f)

        # Create the full AST hierarchy
        program_root = ASTNodeWrapper(ast_node=ast_json)
        root = ASTNodeWrapper(ast_node=ast_json["body"][1], parent=program_root)

        constructs = load_constructs("../constructs.yml", debug=0)
        b = CFGBuilder(constructs)

        cfg = b.make_cfg_for_ast(root)

        print()

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

    def test_cfg_builder5(self):

        with open("data/ast5.json") as f:
           ast_json = json.load(f)

        # Create the full AST hierarchy
        program_root = ASTNodeWrapper(ast_node=ast_json)
        root = ASTNodeWrapper(ast_node=ast_json["body"][0], parent=program_root)

        constructs = load_constructs("../constructs.yml")
        b = CFGBuilder(constructs)

        cfg = b.make_cfg_for_ast(root)

        cfg.debug()

    def test_cfg_builder6(self):

        with open("data/ast6.json") as f:
           ast_json = json.load(f)

        # Create the full AST hierarchy
        program_root = ASTNodeWrapper(ast_node=ast_json)
        root = ASTNodeWrapper(ast_node=ast_json["body"][0], parent=program_root)

        constructs = load_constructs("../constructs.yml")
        b = CFGBuilder(constructs)

        cfg = b.make_cfg_for_ast(root)

        cfg.debug()

    def test_cfg_builder7(self):

        with open("data/ast7.json") as f:
           ast_json = json.load(f)

        # Create the full AST hierarchy
        program_root = ASTNodeWrapper(ast_node=ast_json)

        constructs = load_constructs("../constructs.yml")
        b = CFGBuilder(constructs)

      # # Process all statements in the program body
        cfg = b.make_cfg_for_ast(program_root)
        # Debug print CFG
        # cfg.debug()

        # Test that func_cfgs contains function 'g'
        self.assertIn('g', b.func_cfgs, "Function 'g' should be stored in func_cfgs")

        # Test that we have a function call in one of the CFGs (for_each_loop contains function_call)
        # The function call is embedded as a condition in the for_each_loop, so we need to check
        # if the function 'g' is being called somewhere in the CFG
        func_call_found = False
        # Check if any node has a function_call AST type
        for node in cfg.nodes.values():
            if (hasattr(node, 'metadata') and
                hasattr(node.metadata, 'wrapped_ast') and
                node.metadata.wrapped_ast and
                isinstance(node.metadata.wrapped_ast.ast_node, dict) and
                node.metadata.wrapped_ast.ast_node.get('type') == 'function_call'):
                func_call_found = True
                print(f"Found function_call node: {node.id} with AST type: {node.metadata.wrapped_ast.ast_node.get('type')}")
                break

        self.assertTrue(func_call_found, "Should have function call nodes in one of the CFGs")

        # Test that we have edges with call_stack effects
        # Note: Currently function calls embedded in other constructs (like for_each_loop)
        # are not processed with call_stack effects. This is a limitation of the current implementation.
        call_stack_edges = []
        for edge in cfg.edges:
            if (edge.metadata.abstract_transition and
                edge.metadata.abstract_transition.effects):
                for effect in edge.metadata.abstract_transition.effects:
                    if hasattr(effect, 'call_stack') and effect.call_stack:
                        call_stack_edges.append(edge)

        print(f"Found {len(call_stack_edges)} edges with call_stack effects")

        assert len(call_stack_edges) == 2

        # For now, we just verify that the function definition and call detection work
        # The call_stack effects would be present if we had a standalone function call
        # instead of one embedded in a for_each_loop

        # Also check for function_call nodes in any subgraphs
        print(f"\n=== Checking for function_call nodes in CFG and subgraphs ===")
        for node_id, node in cfg.nodes.items():
            if node.metadata.abstract_action and node.metadata.abstract_action.kind == 'function_call':
                print(f"      *** Found function_call node! ***")

            # if hasattr(node, 'subgraph') and node.subgraph:
            #     print(f"  Node {node_id} has subgraph with {len(node.subgraph.nodes)} nodes")
            #     for sub_node_id, sub_node in node.subgraph.nodes.items():
            #         print(f"    Sub-node {sub_node_id}: kind={sub_node.kind}, role={sub_node.role}")
            #         if sub_node.kind == 'function_call':
            #             print(f"      *** Found function_call node! ***")


    def test_cfg_builder8(self):

        with open("data/ast8.json") as f:
           ast_json = json.load(f)

        # Create the full AST hierarchy
        program_root = ASTNodeWrapper(ast_node=ast_json)

        constructs = load_constructs("../constructs.yml")
        b = CFGBuilder(constructs)

        # Process all statements in the program body
        cfg = b.make_cfg_for_ast(program_root)
        # Debug print CFG
        cfg.debug()

    def test_cfg_builder3(self):

        with open("data/ast3.json") as f:
           ast_json = json.load(f)

        # Create the full AST hierarchy
        program_root = ASTNodeWrapper(ast_node=ast_json)

        constructs = load_constructs("../constructs.yml")
        b = CFGBuilder(constructs)

        # Process all statements in the program body
        cfg = b.make_cfg_for_ast(program_root)
        # Debug print CFG
        cfg.debug()

    def test_cfg_builder9(self):

        with open("test/data/ast9.json") as f:  # no `test/` prefix used
           ast_json = json.load(f)

        # Create the full AST hierarchy
        program_root = ASTNodeWrapper(ast_node=ast_json)

        constructs = load_constructs("constructs.yml")
        b = CFGBuilder(constructs)

        # Process all statements in the program body
        cfg = b.make_cfg_for_ast(program_root)
        # Debug print CFG
        cfg.debug()

        print()
        print("CFG!")
        visualize_cfg(
            cfg,
            "cfg_9.png",
            figsize=(20, 15),
            layout='hierarchical',
        )


