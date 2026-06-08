"""Cross-language parity: Zod-generated JSON Schema vs Pydantic model schema.

For each of the 28 models we reduce both JSON Schemas to a shallow shape
{field_name: (type_category, is_required)} and assert they match. The
normalization is deliberately forgiving on structure (it resolves $refs,
collapses int/number, and unwraps nullable unions) so the only thing that can
break parity is a field's name, coarse type, or required-ness.

The Zod schemas live in packages/shared/schema/<Name>.json and are produced by
`pnpm --filter @deepinterview/shared gen:schema`. If that directory is empty
(schemas not yet generated) the parity tests are skipped rather than failed.
"""

import json
from pathlib import Path

import pytest

from deepinterview_agent.shared_models import MODELS

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "packages/shared/schema"


def _defs(schema: dict) -> dict:
    defs = {}
    defs.update(schema.get("$defs", {}) or {})
    defs.update(schema.get("definitions", {}) or {})
    return defs


def _resolve(node: dict, defs: dict) -> dict:
    """Follow $ref chains until a concrete node is reached."""
    seen = set()
    while isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if ref in seen:
            break
        seen.add(ref)
        key = ref.split("/")[-1]
        node = defs.get(key, {})
    return node


def _type_category(node: dict, defs: dict):
    node = _resolve(node, defs)

    branches = node.get("anyOf") or node.get("oneOf")
    if branches:
        non_null = []
        for branch in branches:
            resolved = _resolve(branch, defs)
            if resolved.get("type") != "null":
                non_null.append(resolved)
        if len(non_null) == 1:
            return _type_category(non_null[0], defs)
        return "union"

    node_type = node.get("type")
    # Encoding-agnostic nullable: Pydantic emits anyOf:[X, null] (handled above),
    # but Zod 4 may emit the compact JSON Schema form type:["string","null"].
    # Collapse the array form to the single non-null type so both agree.
    if isinstance(node_type, list):
        non_null = [t for t in node_type if t != "null"]
        if len(non_null) == 1:
            node_type = non_null[0]
        else:
            return "union"

    if "enum" in node:
        return ("enum", frozenset(node["enum"]))

    if node_type == "array":
        return "array"
    if node_type in ("integer", "number"):
        return "number"
    if node_type == "object" or "properties" in node or "additionalProperties" in node:
        return "object"
    return node_type


def _normalize(schema: dict) -> dict:
    defs = _defs(schema)
    root = _resolve(schema, defs)
    props = root.get("properties", {}) or {}
    required = set(root.get("required", []) or [])
    out = {}
    for field, node in props.items():
        out[field] = (_type_category(node, defs), field in required)
    return out


_SCHEMAS_PRESENT = SCHEMA_DIR.exists() and any(SCHEMA_DIR.glob("*.json"))


@pytest.mark.skipif(
    not _SCHEMAS_PRESENT,
    reason="Zod JSON Schemas not generated; run `pnpm --filter @deepinterview/shared gen:schema`",
)
@pytest.mark.parametrize("name", list(MODELS.keys()))
def test_schema_parity(name: str) -> None:
    model = MODELS[name]
    zod_path = SCHEMA_DIR / f"{name}.json"
    assert zod_path.exists(), f"Missing generated Zod schema for {name}: {zod_path}"

    zod_schema = json.loads(zod_path.read_text(encoding="utf-8"))
    pyd_schema = model.model_json_schema()

    zod_norm = _normalize(zod_schema)
    pyd_norm = _normalize(pyd_schema)

    differing = sorted(
        set(zod_norm) ^ set(pyd_norm)
        | {k for k in (set(zod_norm) & set(pyd_norm)) if zod_norm[k] != pyd_norm[k]}
    )
    assert zod_norm == pyd_norm, (
        f"Schema parity mismatch for {name} on fields {differing}:\n"
        f"  zod={ {k: zod_norm.get(k) for k in differing} }\n"
        f"  pydantic={ {k: pyd_norm.get(k) for k in differing} }"
    )
