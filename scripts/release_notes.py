#!/usr/bin/env python3
"""Extract one version's section from the changelog.

The release notes and the changelog were written twice, by hand, and drifted.
This makes the changelog the only place the prose lives: the release workflow
reads the section for the version being released and uses it as the GitHub
Release body.

A missing or undated section is an error rather than an empty release note,
because publishing a version nobody described is worse than not publishing.

The version comes from ``pyproject.toml``, which is the single source here:
``agentverity.__version__`` reads the installed distribution metadata rather
than carrying a second literal, so the two cannot disagree.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import tomllib

# "## [0.14.0] - 2026-07-31". Keep a Changelog brackets the version; the
# brackets are optional here so a section written either way is found.
HEADING = re.compile(
    r"^## \[?(?P<version>\d+\.\d+\.\d+)\]?"
    r" - (?P<date>\d{4}-\d{2}-\d{2})\s*$"
)
ANY_HEADING = re.compile(r"^## ")


class ChangelogError(Exception):
    """The changelog does not describe the version being released."""


def extract(text: str, version: str) -> str:
    """Return the body of the section for ``version``."""
    lines = text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if match and match.group("version") == version:
            start = index + 1
            break

    if start is None:
        if re.search(rf"^## \[?{re.escape(version)}\]?\b", text, flags=re.MULTILINE):
            raise ChangelogError(
                f"the changelog section for {version} has no release date. "
                f"Use '## [{version}] - YYYY-MM-DD'."
            )
        raise ChangelogError(
            f"the changelog has no section for {version}. Add one before "
            f"releasing, because the section is the release note."
        )

    end = len(lines)
    for index in range(start, len(lines)):
        if ANY_HEADING.match(lines[index]):
            end = index
            break

    body = "\n".join(lines[start:end]).strip()
    if not body:
        raise ChangelogError(
            f"the changelog section for {version} is empty, so the release "
            f"would describe no change"
        )
    return body


def read_version(pyproject: Path) -> str:
    """Read the packaged version, the single source of the number."""
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ChangelogError(f"cannot read {pyproject}: {exc}") from exc
    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not version.strip():
        raise ChangelogError(f"{pyproject} declares no project.version")
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", help="version to extract, e.g. 0.14.0")
    parser.add_argument(
        "--print-version",
        action="store_true",
        help="print the packaged version instead of a changelog section",
    )
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    args = parser.parse_args(argv)

    if args.print_version:
        try:
            print(read_version(args.pyproject))
        except ChangelogError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.version is None:
        parser.error("give a version, or use --print-version")

    try:
        body = extract(args.changelog.read_text(encoding="utf-8"), args.version)
    except (OSError, ChangelogError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(body)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
