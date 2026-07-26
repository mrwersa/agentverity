# Contributing

AgentVerity uses a pull-request-only workflow for `main`.

1. Create a branch from the latest `main`:

   ```bash
   git switch main
   git pull --ff-only
   git switch -c feature/short-description
   ```

2. Keep the change focused and add tests for behavioural changes.

3. Run the local quality gate:

   ```bash
   python -m pytest -q
   ruff check .
   ```

4. Push the branch and open a pull request:

   ```bash
   git push -u origin feature/short-description
   ```

Direct pushes, force pushes, and deletion of `main` are blocked. Merge only
after CI passes and all review conversations are resolved.

Maintainers should follow [RELEASING.md](RELEASING.md) when publishing a
version.

## Useful first contributions

Independent use is more valuable than another bundled metric. Good first
contributions include:

- running AgentVerity against a real router, policy gate, or supervisor and
  reporting where the callable interface did not fit
- adding a thin adapter for a framework you already operate
- contributing a compatibility fixture from an older report or snapshot
- improving an error message after reproducing the confusing path in a test

Open an issue before a large adapter. Describe the target's decision contract,
whether trials can be isolated, and the expected call budget. Do not include
customer prompts, model outputs, credentials, or trace identifiers.
