"""Tests for the top-level public API surface documented in README.md.

Guards against the README's Quickstart and API-surface sections silently
drifting out of sync with what agentverity/__init__.py actually exports.
"""

from __future__ import annotations

from importlib.metadata import version


class TestPublicAPI:
    def test_readme_quickstart_imports(self):
        """The exact import line shown in the README Quickstart must work."""
        from agentverity import run, from_callable  # noqa: F401, I001

    def test_readme_api_surface_imports(self):
        """Every name listed in the README's "API surface" section must be
        importable from the top-level agentverity package."""
        from agentverity import (  # noqa: F401, I001
            run,
            from_callable,
            measure,
            detect,
            Observation,
            Relation,
            builtin_relations,
            RunConfig,
            record_otel_run,
            run_result_to_junit_xml,
            run_result_to_otel_attributes,
            write_junit_xml,
        )

    def test_dunder_all_matches_exports(self):
        """Every name in __all__ must actually be an attribute of the package."""
        import agentverity

        for name in agentverity.__all__:
            assert hasattr(agentverity, name), f"{name!r} in __all__ but not importable"

    def test_package_version_matches_installed_metadata(self):
        """Keep the runtime version on the packaging metadata's single source."""
        import agentverity

        assert agentverity.__version__ == version("agentverity")


def test_py_typed_marker_is_shipped():
    """PEP 561: without this file, type checkers ignore our annotations.

    The package is fully annotated, but a consuming project's mypy or pyright
    silently treats an unmarked package as untyped, so the annotations would
    do nothing outside this repository.
    """
    import importlib.resources

    marker = importlib.resources.files("agentverity") / "py.typed"
    assert marker.is_file(), "agentverity/py.typed is missing from the package"
