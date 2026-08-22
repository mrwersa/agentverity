"""Capture caller-visible members declared by AgentVerity's exported classes."""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import agentverity

AUDIT_SCHEMA = "agentverity.class-member-audit/v1"


def _value(value: Any) -> Any:
    """Return a stable JSON representation for reviewed field defaults."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _value(item) for key, item in sorted(value.items())}
    if isinstance(value, (set, frozenset)):
        return sorted(_value(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [_value(item) for item in value]
    if inspect.isclass(value):
        return f"{value.__module__}.{value.__qualname__}"
    return repr(value)


def _annotation(value: Any) -> str:
    """Render postponed and runtime annotations with one stable spelling."""
    if isinstance(value, str):
        return value
    return inspect.formatannotation(value)


def _signature(value: Any) -> str:
    return str(inspect.signature(value))


def _default(field: dataclasses.Field[Any]) -> dict[str, Any]:
    if field.default is not dataclasses.MISSING:
        return {"kind": "value", "value": _value(field.default)}
    if field.default_factory is not dataclasses.MISSING:
        factory = field.default_factory
        return {
            "kind": "factory",
            "factory": getattr(factory, "__qualname__", repr(factory)),
        }
    return {"kind": "required"}


def _field(field: dataclasses.Field[Any]) -> dict[str, Any]:
    return {
        "name": field.name,
        "type": _annotation(field.type),
        "init": field.init,
        "kw_only": field.kw_only,
        "default": _default(field),
    }


def _member(cls: type[Any], name: str, raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, property):
        assert raw.fget is not None
        return {
            "name": name,
            "kind": "property",
            "signature": _signature(raw.fget),
            "writable": raw.fset is not None,
        }
    if isinstance(raw, classmethod):
        return {
            "name": name,
            "kind": "classmethod",
            "signature": _signature(getattr(cls, name)),
        }
    if isinstance(raw, staticmethod):
        return {
            "name": name,
            "kind": "staticmethod",
            "signature": _signature(getattr(cls, name)),
        }
    if inspect.isfunction(raw):
        return {
            "name": name,
            "kind": "method",
            "signature": _signature(raw),
        }
    return None


def class_contract(cls: type[Any]) -> dict[str, Any]:
    """Describe fields and members declared as public by one exported class."""
    fields = list(dataclasses.fields(cls)) if dataclasses.is_dataclass(cls) else []
    field_names = {field.name for field in fields}
    members = []
    attributes = []
    for name, raw in sorted(vars(cls).items()):
        if name.startswith("_") or name in field_names:
            continue
        member = _member(cls, name, raw)
        if member is not None:
            members.append(member)
        else:
            attributes.append({"name": name, "value": _value(raw)})

    payload: dict[str, Any] = {
        "module": cls.__module__,
        "qualified_name": cls.__qualname__,
        "fields": [_field(field) for field in fields],
        "members": members,
        "attributes": attributes,
    }
    if dataclasses.is_dataclass(cls):
        params = cls.__dataclass_params__
        payload["dataclass"] = {
            "frozen": params.frozen,
            "order": params.order,
        }
    return payload


def collect_class_members() -> dict[str, Any]:
    """Collect every class in the explicit top-level export list."""
    classes = {
        name: class_contract(value)
        for name in sorted(agentverity.__all__)
        if inspect.isclass(value := getattr(agentverity, name))
    }
    return {"schema": AUDIT_SCHEMA, "classes": classes}


def main() -> None:
    """Write an audit fixture from the explicitly named installed release."""
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    if agentverity.__version__ != args.expected_version:
        raise SystemExit(
            f"expected agentverity {args.expected_version}, imported "
            f"{agentverity.__version__}; run outside the repository with the "
            "named wheel installed"
        )
    payload = {
        "producer": f"agentverity=={args.expected_version}",
        "surface": collect_class_members(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
