from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
PYPROJECT = ROOT / "pyproject.toml"

_spec = importlib.util.spec_from_file_location(
    "release_notes", ROOT / "scripts" / "release_notes.py"
)
assert _spec is not None and _spec.loader is not None
release_notes = importlib.util.module_from_spec(_spec)
sys.modules["release_notes"] = release_notes
_spec.loader.exec_module(release_notes)

SAMPLE = """# Changelog

## [Unreleased]

## [0.14.0] - 2026-07-31

### Added

- something worth saying

## [0.13.2] - 2026-07-30

### Added

- an older thing
"""


def test_extract_returns_only_the_requested_section() -> None:
    body = release_notes.extract(SAMPLE, "0.14.0")

    assert "something worth saying" in body
    assert "an older thing" not in body
    assert "Unreleased" not in body


def test_the_keep_a_changelog_brackets_are_optional() -> None:
    body = release_notes.extract("## 1.2.3 - 2026-01-01\n\n- plain\n", "1.2.3")

    assert body == "- plain"


def test_extract_reads_the_last_section_to_the_end_of_the_file() -> None:
    assert release_notes.extract(SAMPLE, "0.13.2").endswith("- an older thing")


def test_extract_refuses_a_version_with_no_section() -> None:
    with pytest.raises(release_notes.ChangelogError, match="no section for 9.9.9"):
        release_notes.extract(SAMPLE, "9.9.9")


def test_extract_refuses_an_undated_section() -> None:
    # An undated heading is a draft, and releasing a draft publishes prose
    # that was never finished.
    with pytest.raises(release_notes.ChangelogError, match="no release date"):
        release_notes.extract("# Changelog\n\n## [1.2.3]\n\n- drafted\n", "1.2.3")


def test_extract_refuses_an_empty_section() -> None:
    text = "## [1.2.3] - 2026-01-01\n\n## [1.2.2] - 2025-01-01\n"

    with pytest.raises(release_notes.ChangelogError, match="is empty"):
        release_notes.extract(text, "1.2.3")


def test_read_version_reads_pyproject(tmp_path: Path) -> None:
    assert release_notes.read_version(PYPROJECT)

    bad = tmp_path / "pyproject.toml"
    bad.write_text("[project]\nname = 'x'\n", encoding="utf-8")
    with pytest.raises(release_notes.ChangelogError, match="no project.version"):
        release_notes.read_version(bad)

    with pytest.raises(release_notes.ChangelogError, match="cannot read"):
        release_notes.read_version(tmp_path / "absent.toml")


def test_main_prints_the_section(capsys, tmp_path: Path) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(SAMPLE, encoding="utf-8")

    assert release_notes.main(["0.14.0", "--changelog", str(path)]) == 0
    assert "something worth saying" in capsys.readouterr().out


def test_main_reports_a_missing_section(capsys, tmp_path: Path) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(SAMPLE, encoding="utf-8")

    assert release_notes.main(["9.9.9", "--changelog", str(path)]) == 1
    assert "no section for 9.9.9" in capsys.readouterr().err


def test_main_reports_an_unreadable_changelog(capsys, tmp_path: Path) -> None:
    argv = ["0.1.0", "--changelog", str(tmp_path / "absent.md")]

    assert release_notes.main(argv) == 1
    assert "error:" in capsys.readouterr().err


def test_main_prints_the_packaged_version(capsys) -> None:
    # The release workflow reads the version this way, so the flag it calls is
    # covered rather than assumed.
    assert release_notes.main(["--print-version", "--pyproject", str(PYPROJECT)]) == 0
    assert capsys.readouterr().out.strip() == release_notes.read_version(PYPROJECT)


def test_main_reports_an_unreadable_pyproject(capsys, tmp_path: Path) -> None:
    argv = ["--print-version", "--pyproject", str(tmp_path / "absent.toml")]

    assert release_notes.main(argv) == 1
    assert "cannot read" in capsys.readouterr().err


def test_main_requires_a_version_or_the_flag() -> None:
    with pytest.raises(SystemExit):
        release_notes.main([])


def test_the_current_version_is_described_in_the_changelog() -> None:
    # The guard the manual process did not have: this fails the release pull
    # request when the version moved and its section was never written.
    version = release_notes.read_version(PYPROJECT)

    assert release_notes.extract(CHANGELOG.read_text(encoding="utf-8"), version)


def test_the_package_carries_no_second_version_literal() -> None:
    # The number lives in pyproject.toml alone. Asserting the *value* here
    # would fail whenever a developer's editable install lagged behind the
    # working tree, which is a fact about their venv rather than about the
    # code. CI builds a wheel and checks all three agree, which is where that
    # belongs. What is stable to assert here is the mechanism.
    source = (ROOT / "agentverity" / "__init__.py").read_text(encoding="utf-8")

    assert 'version("agentverity")' in source
    assert not re.search(r'^__version__ = "\d', source, flags=re.MULTILINE)
