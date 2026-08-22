import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "docs" / "design-partners.md"
PLAYBOOK = ROOT / "docs" / "design-partner-playbook.md"
ISSUE_FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "design-partner.yml"
FUNNEL = ROOT / "docs" / "templates" / "design-partner-funnel.csv"


def test_the_design_partner_pilot_is_discoverable() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")

    assert "docs/design-partners.md" in readme
    assert "docs/design-partners.md" in roadmap
    assert "docs/design-partner-playbook.md" in roadmap
    assert "design-partner.yml" in BRIEF.read_text(encoding="utf-8")


def test_the_public_form_warns_against_sensitive_data() -> None:
    issue_form = ISSUE_FORM.read_text(encoding="utf-8")

    for sensitive in ("prompts", "outputs", "credentials", "trace identifiers"):
        assert sensitive in issue_form
    assert "This issue is public" in issue_form


def test_the_funnel_schema_contains_no_direct_identifiers() -> None:
    with FUNNEL.open(encoding="utf-8", newline="") as handle:
        fields = next(csv.reader(handle))

    assert fields[0] == "record_id"
    assert {"status", "source_segment", "rejection_reason"} <= set(fields)
    assert not {"name", "email", "handle", "phone"} & set(fields)


def test_the_acquisition_gate_is_consistent_with_the_roadmap() -> None:
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    playbook = PLAYBOOK.read_text(encoding="utf-8")

    for target in ("20 relevant teams", "six discovery", "three qualified pilot"):
        assert target in roadmap
        assert target in playbook
