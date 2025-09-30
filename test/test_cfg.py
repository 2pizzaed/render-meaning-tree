import json
import unittest

from src.cfg import ASTNodeWrapper
from src.cfg import CFGBuilder
from src.cfg import load_constructs

class TestCfgBuilder(unittest.TestCase):

    def test_cfg_builder(self):

        with open("ast.json") as f:
           ast_json = json.load(f)

        root = ASTNodeWrapper(ast_node=ast_json["body"][1])

        constructs = load_constructs(debug=True)
        b = CFGBuilder(constructs)

        cfg = b.make_cfg_for_ast(root)

        cfg.debug()


