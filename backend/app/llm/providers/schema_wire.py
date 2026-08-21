"""Preserve open option dictionaries through closed provider JSON schemas.

Provider-native JSON schemas forbid arbitrary object keys. Encode only these maps
as JSON strings on the wire, then restore them before validating the domain model.
"""

import json
from typing import Any


def _open_map(node: dict) -> bool:
    additional = node.get("additionalProperties")
    return (
        node.get("type") == "object"
        and not node.get("properties")
        and (additional is True or isinstance(additional, dict))
    )


def wire_schema(node: Any) -> Any:
    if isinstance(node, list):
        return [wire_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    if _open_map(node):
        return {
            "type": "string",
            "description": "A JSON object encoded as a JSON string, for example {}. "
            + node.get("description", ""),
        }
    return {key: wire_schema(value) for key, value in node.items()}


def restore_maps(value: Any, node: dict, root: dict | None = None) -> Any:
    root = root or node
    if "$ref" in node:
        reference = node["$ref"]
        if not reference.startswith("#/$defs/"):
            raise ValueError("Only local schema references are supported")
        return restore_maps(value, root["$defs"][reference.removeprefix("#/$defs/")], root)
    alternatives = node.get("anyOf", [])
    if alternatives:
        if value is None and any(item.get("type") == "null" for item in alternatives):
            return None
        for item in alternatives:
            if item.get("type") != "null":
                return restore_maps(value, item, root)
    if _open_map(node):
        if not isinstance(value, str):
            raise ValueError("A wire options map must be a JSON string")
        decoded = json.loads(value)
        if not isinstance(decoded, dict):
            raise ValueError("An options map must decode to an object")
        return decoded
    if isinstance(value, list) and node.get("type") == "array":
        return [restore_maps(item, node.get("items", {}), root) for item in value]
    if isinstance(value, dict):
        properties = node.get("properties", {})
        return {
            key: restore_maps(item, properties[key], root) if key in properties else item
            for key, item in value.items()
        }
    return value
