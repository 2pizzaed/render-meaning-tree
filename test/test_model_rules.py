from src.json_property_path import ResolvedJSONPath
from src.model.rules import Identification
from src.types import JSON


def test_identification_resolve_json_ignores_parent_origin_for_property_path():
    data: JSON = {
        "root": {
            "body": [
                {"type": "first"},
                {"type": "second"},
            ]
        }
    }
    identification = Identification(origin="parent", property_path="body / [0]")

    resolved = identification.resolve_json(data, current_path=("root",))

    assert resolved == ResolvedJSONPath(path=("root", "body", 0), value=data["root"]["body"][0]) # type: ignore


def test_identification_resolve_json_supports_previous_origin_with_next_navigation():
    data: JSON = {
        "branches": [
            {"condition": {"name": "a"}},
            {"condition": {"name": "b"}},
        ]
    }
    identification = Identification(origin="previous", property_path="^ / [next] / condition")

    resolved = identification.resolve_json(data, previous_path=("branches", 0, "condition"))

    assert resolved == ResolvedJSONPath(path=("branches", 1, "condition"), value=data["branches"][1]["condition"]) # type: ignore


def test_identification_get_from_json_supports_direct_property_lookup():
    data: JSON = {
        "program": {
            "elseBranch": {"type": "compound_statement"}
        }
    }
    identification = Identification(origin="parent", property="elseBranch")

    value = identification.get_from_json(data, current_path=("program", "condition"))

    assert value == {"type": "compound_statement"}


def test_identification_resolve_json_supports_role_in_list_from_parent():
    data: JSON = {
        "branches": [
            {"condition": {"name": "a"}},
            {"condition": {"name": "b"}},
        ]
    }
    identification = Identification(origin="parent", role_in_list="first_in_list")

    resolved = identification.resolve_json(data, current_path=("branches", 1))

    assert resolved == ResolvedJSONPath(path=("branches", 0), value=data["branches"][0]) # type: ignore


def test_identification_resolve_json_supports_role_in_list_next_from_previous():
    data: JSON = {
        "branches": [
            {"condition": {"name": "a"}},
            {"condition": {"name": "b"}},
        ]
    }
    identification = Identification(role_in_list="next_in_list")

    resolved = identification.resolve_json(
        data,
        current_path=("branches",),
        previous_path=("branches", 0),
    )

    assert resolved == ResolvedJSONPath(path=("branches", 1), value=data["branches"][1]) # type: ignore
