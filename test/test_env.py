from __future__ import annotations

import httpx

from src import env

_TOOL_ROUTES = {
    "its_DomainModel": "/rpc/domain",
    "its_Reasoner": "/rpc/reasoner",
    "meaning_tree": "/rpc/meaning-tree",
}


class _Response:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> object:
        return self._payload


def _health_payload(*tool_names: str, version: str | None = "0.1.0") -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "ok",
        "server": "compph-toolchain-server",
        "tools": [{"name": name, "route": _TOOL_ROUTES[name]} for name in tool_names],
    }
    if version is not None:
        payload["version"] = version
    return payload


def test_auto_backend_uses_one_health_probe_for_all_tool_selections(monkeypatch) -> None:
    calls: list[tuple[str, float]] = []

    def fake_get(url: str, *, timeout: float) -> _Response:
        calls.append((url, timeout))
        return _Response(
            _health_payload(
                "meaning_tree",
                "its_DomainModel",
                "its_Reasoner",
                version=None,
            )
        )

    monkeypatch.setenv("TOOLCHAIN_BACKEND", "auto")
    monkeypatch.setenv("JSON_RPC_TOOLCHAIN_SERVER", "http://localhost:9015")
    monkeypatch.setattr(env, "_auto_rpc_tools", None)
    monkeypatch.setattr(env.httpx, "get", fake_get)

    assert env.select_backend(required_rpc_tools=("meaning_tree",)) == "rpc"
    assert env.select_backend(required_rpc_tools=("its_DomainModel", "its_Reasoner")) == "rpc"
    assert calls == [("http://localhost:9015/health", env.AUTO_BACKEND_HEALTH_TIMEOUT_SECONDS)]


def test_auto_backend_falls_back_to_cli_when_rpc_is_unavailable(monkeypatch) -> None:
    def fake_get(url: str, *, timeout: float) -> _Response:
        raise httpx.ConnectError("connection refused", request=httpx.Request("GET", url))

    monkeypatch.setenv("TOOLCHAIN_BACKEND", "auto")
    monkeypatch.setattr(env, "_auto_rpc_tools", None)
    monkeypatch.setattr(env.httpx, "get", fake_get)

    assert env.select_backend(required_rpc_tools=("meaning_tree",)) == "cli"


def test_auto_backend_requires_the_requested_tool_in_the_health_registry(monkeypatch) -> None:
    calls = 0

    def fake_get(*_args: object, **_kwargs: object) -> _Response:
        nonlocal calls
        calls += 1
        return _Response(_health_payload("its_DomainModel", "its_Reasoner"))

    monkeypatch.setenv("TOOLCHAIN_BACKEND", "auto")
    monkeypatch.setattr(env, "_auto_rpc_tools", None)
    monkeypatch.setattr(env.httpx, "get", fake_get)

    assert env.select_backend(required_rpc_tools=("meaning_tree",)) == "cli"
    assert env.select_backend(required_rpc_tools=("its_DomainModel", "its_Reasoner")) == "rpc"
    assert calls == 1


def test_explicit_rpc_backend_does_not_probe_health(monkeypatch) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> _Response:
        raise AssertionError("explicit RPC mode must not probe /health")

    monkeypatch.setenv("TOOLCHAIN_BACKEND", "rpc")
    monkeypatch.setattr(env, "_auto_rpc_tools", None)
    monkeypatch.setattr(env.httpx, "get", fail_if_called)

    assert env.select_backend(required_rpc_tools=("meaning_tree",)) == "rpc"
