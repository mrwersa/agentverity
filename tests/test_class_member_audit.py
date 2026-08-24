"""Exported class members change only through an explicit fixture diff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_class_members import AUDIT_SCHEMA, collect_class_members, main
from scripts.audit_public_surface import collect_surface

FIXTURES = Path(__file__).parent / "fixtures" / "compatibility" / "v0.21.0"
CLASS_FIXTURE = FIXTURES / "class-members.json"
SURFACE_FIXTURE = FIXTURES / "public-surface.json"


def test_current_class_members_match_the_published_release():
    """The checkout matches the class structure published in 0.21.0."""
    fixture = json.loads(CLASS_FIXTURE.read_text(encoding="utf-8"))

    assert fixture["producer"] == "agentverity==0.21.0"
    assert fixture["surface"]["schema"] == AUDIT_SCHEMA
    assert collect_class_members() == fixture["surface"]


def test_every_exported_class_is_in_the_member_inventory():
    """The narrower audit cannot silently omit a class in the top-level surface."""
    members = json.loads(CLASS_FIXTURE.read_text(encoding="utf-8"))["surface"]
    public = json.loads(SURFACE_FIXTURE.read_text(encoding="utf-8"))["surface"]
    published_exported = {
        entry["name"] for entry in public["python"] if entry["kind"] == "class"
    }
    current = collect_class_members()["classes"]
    current_exported = {
        entry["name"]
        for entry in collect_surface()["python"]
        if entry["kind"] == "class"
    }
    assert set(members["classes"]) == published_exported
    assert published_exported == current_exported
    assert set(current) == current_exported
    assert len(current_exported) == 36
    for contract in members["classes"].values():
        field_names = [field["name"] for field in contract["fields"]]
        member_names = [member["name"] for member in contract["members"]]
        assert len(field_names) == len(set(field_names))
        assert len(member_names) == len(set(member_names))


def test_documented_inventory_counts_match_the_fixture():
    """Exact scope claims cannot drift from the reviewed inventory."""
    classes = collect_class_members()["classes"]
    document = (Path(__file__).parents[1] / "docs" / "class-member-audit.md").read_text(
        encoding="utf-8"
    )

    assert f"all {len(classes)} classes" in document
    assert (
        f"all {sum(len(value['fields']) for value in classes.values())} fields"
        in document
    )
    assert (
        f"{sum('dataclass' in value for value in classes.values())} exported dataclasses"
        in document
    )
    assert (
        f"all {sum(len(value['members']) for value in classes.values())} public methods"
        in document
    )


def test_the_auditor_refuses_to_mislabel_the_current_checkout(monkeypatch, tmp_path):
    """A later checkout cannot silently replace the published-release record."""
    output = tmp_path / "members.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "audit_class_members.py",
            str(output),
            "--expected-version",
            "0.18.0",
        ],
    )

    with pytest.raises(SystemExit, match="expected agentverity 0.18.0"):
        main()

    assert not output.exists()
