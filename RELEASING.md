# Releasing AgentVerity

AgentVerity publishes from a GitHub Release through PyPI Trusted Publishing.
No long-lived PyPI token is stored in GitHub.

## One-time PyPI setup

Done on 2026-07-25, when v0.2.0 was published. The trusted publisher is:

- PyPI project: `agentverity`
- GitHub owner: `mrwersa`
- Repository: `agentverity`
- Workflow: `release.yml`
- Environment: `pypi`

It was registered as a *pending* publisher, because the project did not exist
on PyPI yet. Publishing v0.2.0 created the project and promoted it to a normal
publisher, so this step does not need repeating.

Protect the `pypi` GitHub environment against unreviewed deployment where the
account plan permits it.

## Prepare a release

1. Create a release branch from current `main`.
2. Set the version in `pyproject.toml`.
3. Move the relevant entries from `Unreleased` into a dated changelog section.
4. Run the local checks:

   ```bash
   python -m pytest -q
   ruff check .
   python -m pip install build twine
   python -m build
   python -m twine check dist/*
   ```

5. Open a pull request and merge it only after every required CI check passes.

## Publish

1. Create a GitHub Release targeting the merged `main` commit.
2. Use a tag matching the package version, such as `v0.2.0`.
3. Copy the matching changelog section into the release notes.
4. Publish the GitHub Release.

Publishing the release starts `.github/workflows/release.yml`. The workflow
verifies that the tag matches `pyproject.toml`, builds the wheel and source
distribution, checks their metadata, and publishes them to PyPI using OIDC.

## Verify

After the workflow succeeds, install the release in a clean environment:

```bash
python -m venv /tmp/agentverity-release
/tmp/agentverity-release/bin/pip install "agentverity==0.2.0"
/tmp/agentverity-release/bin/agentverity --help
```

Confirm the GitHub Release and PyPI project page show the same version. PyPI
versions are immutable. If publication is wrong, fix forward with a new version
rather than moving or reusing the tag.
