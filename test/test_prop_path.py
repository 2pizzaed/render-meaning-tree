import json
from typing import Dict, Any

from src.cfg import ASTNodeWrapper
from src.meaning_tree import to_dict

def test_astnodewrapper_1():
    with open("ast.json") as f:
       ast_json = json.load(f)

    root = ASTNodeWrapper(value=ast_json["body"][1])

    res = root.get('branches', {'property_path':'branches/[0]/condition'})
    assert res is not None, "Result should not be None"
    assert res.value == ast_json["body"][1]["branches"][0]["condition"]

    res2 = res.get('branches', {'property_path':'^ / [next] / condition'})
    assert res2.value == ast_json["body"][1]["branches"][1]["condition"]

    res3 = res2.get('branches', {'property_path':'^ / [next] / condition'})
    assert res3.value == ast_json["body"][1]["branches"][1]["condition"]

