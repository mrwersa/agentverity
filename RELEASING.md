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

## When to cut one

Documented because the history says it was not. This project let seventeen
merged pull requests pile up and then published four minor versions inside
twenty-eight hours, and the sibling project let an API fix sit unreleased for
four days. Both are the same missing rule rather than two different mistakes,
which is why the wording below is identical in both repositories.

Cut a release when any of these is true:

- **A user-visible change has merged.** The public API or the command-line
  surface. A name that is importable but missing from `__all__` counts: it is
  reachable and unnameable, which is a defect a user meets.
- **The README started describing something different.** It is the PyPI
  description, so a reader there sees the last release's copy. This means a
  README change that documents a user-visible change, or one that corrects a
  description which now materially misleads, since a misleading description is
  itself a defect a user meets. A wording pass, a typo, or a restructure that
  says the same thing better is not a reason on its own. Copy edits are the
  most frequent change here, and treating each as a release is the same
  missing rule in a third shape.
- **A roadmap item finished and changed the package.** That is the unit a
  reader tracks, so it is the unit worth publishing against, but only when
  something in the wheel moved. An item whose whole output is evidence or
  documentation has already reached its reader on merge, and this trigger and
  the documentation entry below would otherwise fire against each other. That
  collision is not hypothetical: the first item finished after this section
  was written produced a directory of evidence and nothing else.
- **A defect that reaches a user is fixed.** Wrong output, a misleading
  message, a refused input that should be accepted.

Do not cut one when:

- Only internal documentation moved. `ROADMAP.md`, `DESIGN.md` and evidence
  directories are read on GitHub and reach a reader the moment they merge.
- The changelog would read as tidying. A release nobody can act on spends
  attention and returns nothing.
- One landed today already, unless the second fixes the first. Batch within a
  day and let the changelog carry the whole of it.

The version follows what changed rather than how long it has been. A patch
preserves the public Python API and the command-line contract, and anything
that refuses input it used to accept is a minor, however small the diff.

## Cut a release

Releases are cut by merging a pull request. Nothing is typed by hand at
release time.

1. Create a release branch from current `main`.
2. Set the version in `pyproject.toml`. That is the only place the number
   lives: `agentverity.__version__` reads the installed distribution metadata
   rather than carrying a second literal, so the two cannot drift apart.
3. Move the relevant entries from `Unreleased` into a dated section:

   ```markdown
   ## [0.14.0] - 2026-07-31
   ```

   That section becomes the GitHub Release notes verbatim, so write it for
   someone deciding whether to upgrade. A missing, undated, or empty section
   fails the release rather than publishing a version nobody described.

4. Run the local checks:

   ```bash
   python -m pytest -q
   ruff check .
   python -m build && python -m twine check dist/*
   ```

5. Open a pull request and merge it once every required check passes.

Merging does the rest, once CI has passed on the merged commit. The workflow
runs when CI finishes on `main`, and only when it succeeded. It reads the
version from the exact commit CI passed on, stops if that version is already
released, extracts the changelog section, builds and checks the artefacts, and
only then creates the tag and the GitHub Release before publishing to PyPI.

The order matters. Tagging first would leave a public release behind whenever
a build or an upload failed, which is a version users can see and cannot
install.

## What the automation refuses to do

- Publish a commit whose CI run did not succeed.
- Publish a commit that is no longer the tip of `main`. CI runs finish in
  whatever order they finish, not commit order, so releasing a commit that
  something has landed on top of would publish an older version after a newer
  one. Whatever is on top releases itself.
- Publish a version with no dated changelog section.
- Publish a wheel or sdist whose filename does not match the tag.
- Re-release a version that already has a GitHub Release.
- Run two releases at once. The workflow takes a repository-wide lock.

Two bumps merged in quick succession release the second one only. The first
version is never the tip long enough to release, and its changes ship inside
the second. Merge one release at a time if each needs its own version on PyPI.

## When something fails partway

The decision is keyed on whether the **release** exists, not the tag, so a run
that pushed the tag and then died recreates only what is missing rather than
reading as finished.

If the PyPI upload is what failed, re-run the failed job from the Actions
page. The artefacts are already built and attached, and the publish step
uploads those exact files.

## Publishing from the GitHub UI

Creating a release by hand still publishes, which is the path to use for a
re-run after an infrastructure failure. Tag it `v<version>`, matching
`pyproject.toml` exactly.

Note that a release created by the workflow's own token does not trigger
another workflow run. That is why tagging and publishing live in the same
workflow file rather than in two files that chain.

## Verify

After the workflow succeeds, install the release in a clean environment:

```bash
python -m venv /tmp/agentverity-release
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)"
/tmp/agentverity-release/bin/pip install "agentverity==$VERSION"
/tmp/agentverity-release/bin/agentverity --help
```

Confirm the GitHub Release and PyPI project page show the same version. PyPI
versions are immutable. If publication is wrong, fix forward with a new version
rather than moving or reusing the tag.
