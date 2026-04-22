from src.json_property_path import (
    ResolvedJSONPath,
    get_json_by_property_path,
    parse_property_path,
    resolve_json_property_path,
)


def test_parse_property_path_normalizes_components():
    assert parse_property_path(" branches / [0] / condition ") == ("branches", "[0]", "condition")
    assert parse_property_path("") is None
    assert parse_property_path("   ") is None
    assert parse_property_path(None) is None


def test_resolve_json_property_path_supports_nested_access_and_parent_moves():
    data = {
        "branches": [
            {"condition": {"left": {"name": "a"}}},
            {"condition": {"left": {"name": "b"}}},
        ]
    }

    resolved = resolve_json_property_path(data, "branches/[0]/condition/left/^/^")

    assert resolved == ResolvedJSONPath(path=("branches", 0), value=data["branches"][0])


def test_resolve_json_property_path_supports_next_and_previous_origin():
    data = {
        "items": [
            {"name": "first"},
            {"name": "second"},
            {"name": "third"},
        ]
    }

    resolved = resolve_json_property_path(
        data,
        "[next]/name",
        current_path=("items", 0),
        previous_path=("items", 0),
        origin="previous",
    )

    assert resolved == ResolvedJSONPath(path=("items", 1, "name"), value="second")


def test_resolve_json_property_path_preserves_none_values():
    data = {"items": [{"value": None}]}

    resolved = resolve_json_property_path(data, "items/[0]/value")

    assert resolved == ResolvedJSONPath(path=("items", 0, "value"), value=None)


def test_get_json_by_property_path_returns_default_on_navigation_error():
    data = {"items": [{"value": 1}]}

    assert get_json_by_property_path(data, "items/[9]/value", default="missing") == "missing"
