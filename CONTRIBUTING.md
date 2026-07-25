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
