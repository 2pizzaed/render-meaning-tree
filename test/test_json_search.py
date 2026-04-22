from src.json_search import get_node_by_path, search_bfs, search_dfs, search_with_paths_dfs


def test_search_dfs_returns_nodes_from_deepest_to_root_left_to_right():
    data = {
        "type": "root",
        "left": {"type": "call", "name": "outer_left", "arg": {"type": "call", "name": "inner_left"}},
        "right": {"type": "call", "name": "outer_right"},
    }

    result = search_dfs(data, lambda node: isinstance(node, dict) and node.get("type") == "call")

    assert [node["name"] for node in result] == ["inner_left", "outer_left", "outer_right"]


def test_search_dfs_respects_max_results_globally():
    data = {
        "type": "root",
        "items": [
            {"type": "call", "name": "first"},
            {"type": "call", "name": "second"},
            {"type": "call", "name": "third"},
        ],
    }

    result = search_dfs(data, lambda node: isinstance(node, dict) and node.get("type") == "call", max_results=2)

    assert [node["name"] for node in result] == ["first", "second"]


def test_search_bfs_returns_nodes_level_by_level_and_stops_at_limit():
    data = {
        "type": "root",
        "left": {"type": "call", "name": "left", "child": {"type": "call", "name": "deep_left"}},
        "right": {"type": "call", "name": "right"},
    }

    result = search_bfs(data, lambda node: isinstance(node, dict) and node.get("type") == "call", max_results=2)

    assert [node["name"] for node in result] == ["left", "right"]


def test_search_with_paths_dfs_returns_tuple_paths():
    data = {
        "items": [
            {"type": "value", "payload": None},
            {"type": "target", "value": 42},
        ]
    }

    result = search_with_paths_dfs(data, lambda node: isinstance(node, dict) and node.get("type") == "target")

    assert result == [(("items", 1), {"type": "target", "value": 42})]


def test_get_node_by_path_supports_tuple_paths_and_distinguishes_missing_via_default():
    data = {"items": [{"value": None}, {"value": 42}]}
    missing = object()

    assert get_node_by_path(data, ("items", 0, "value")) is None
    assert get_node_by_path(data, ("items", 1, "value")) == 42
    assert get_node_by_path(data, ("items", 2, "value"), default=missing) is missing
