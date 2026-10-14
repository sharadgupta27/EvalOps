"""openapi.yaml is the source of truth. This test fails when the backend drifts from it.

It compares paths, methods, operation ids, parameters, success status codes, request and
response schema names, and every component schema's properties, required fields and enums.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import FastAPI

from app.main import API_PREFIX

CONTRACT = Path(__file__).resolve().parents[3] / "openapi.yaml"
GENERATED_ONLY = ("Body_", "HTTPValidationError", "ValidationError")
METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture(scope="module")
def contract() -> dict[str, Any]:
    spec: dict[str, Any] = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    return spec


@pytest.fixture
def generated(app: FastAPI) -> dict[str, Any]:
    return app.openapi()


def _ops(spec: dict[str, Any], prefix: str = "") -> dict[tuple[str, str], dict[str, Any]]:
    ops = {}
    for path, item in spec["paths"].items():
        if prefix and not path.startswith(prefix):
            continue
        shared = item.get("parameters", [])
        for method, op in item.items():
            if method in METHODS:
                ops[(path.removeprefix(prefix), method)] = {**op, "_shared": shared}
    return ops


def _resolve_param(spec: dict[str, Any], p: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in p:
        return spec["components"]["parameters"][p["$ref"].rsplit("/", 1)[-1]]  # type: ignore[no-any-return]
    return p


def _params(spec: dict[str, Any], op: dict[str, Any]) -> set[tuple[str, str]]:
    params = [_resolve_param(spec, p) for p in op["_shared"] + op.get("parameters", [])]
    return {(p["name"], p["in"]) for p in params if p["in"] in ("path", "query")}


def _schema_name(schema: dict[str, Any] | None) -> str | None:
    if not schema:
        return None
    if "$ref" in schema:
        return f"{schema['$ref'].rsplit('/', 1)[-1]}"
    if schema.get("type") == "array" and "items" in schema:
        return f"list[{_schema_name(schema['items'])}]"
    return schema.get("type")


def _success(op: dict[str, Any]) -> tuple[str, str | None]:
    code = next(c for c in op["responses"] if str(c).startswith("2"))
    content = op["responses"][code].get("content", {})
    schema = content.get("application/json", {}).get("schema")
    return str(code), _schema_name(schema)


def _body(op: dict[str, Any]) -> str | None:
    content = op.get("requestBody", {}).get("content", {})
    if "application/json" in content:
        return _schema_name(content["application/json"]["schema"])
    return "multipart" if "multipart/form-data" in content else None


def test_same_operations(contract: dict[str, Any], generated: dict[str, Any]) -> None:
    assert set(_ops(contract)) == set(_ops(generated, API_PREFIX))


def test_operation_details_match(contract: dict[str, Any], generated: dict[str, Any]) -> None:
    gen = _ops(generated, API_PREFIX)
    problems = []
    for key, c_op in _ops(contract).items():
        g_op = gen[key]
        checks = {
            "operationId": (c_op["operationId"], g_op["operationId"]),
            "params": (_params(contract, c_op), _params(generated, g_op)),
            "success": (_success(c_op), _success(g_op)),
            "body": (_body(c_op), _body(g_op)),
        }
        problems += [
            f"{key} {name}: contract={c} backend={g}" for name, (c, g) in checks.items() if c != g
        ]
    assert not problems, "\n".join(problems)


def _props(schema: dict[str, Any]) -> tuple[set[str], set[str], list[Any] | None]:
    return set(schema.get("properties", {})), set(schema.get("required", [])), schema.get("enum")


def test_component_schemas_match(contract: dict[str, Any], generated: dict[str, Any]) -> None:
    c_schemas = contract["components"]["schemas"]
    g_schemas = generated["components"]["schemas"]
    extra = {n for n in g_schemas if n not in c_schemas and not n.startswith(GENERATED_ONLY)}
    missing = set(c_schemas) - set(g_schemas)
    assert not extra, f"backend has schemas missing from openapi.yaml: {sorted(extra)}"
    assert not missing, f"openapi.yaml has schemas the backend never uses: {sorted(missing)}"
    problems = []
    for name, c in c_schemas.items():
        cp, cr, ce = _props(c)
        gp, gr, ge = _props(g_schemas[name])
        if cp != gp:
            problems.append(f"{name}.properties: contract-only={cp - gp} backend-only={gp - cp}")
        if cr != gr:
            problems.append(f"{name}.required: contract-only={cr - gr} backend-only={gr - cr}")
        if ce != ge and sorted(ce or []) != sorted(ge or []):
            problems.append(f"{name}.enum: contract={ce} backend={ge}")
    assert not problems, "\n".join(problems)
