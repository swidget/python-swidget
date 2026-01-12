Contributing
============

Setup
-----
- Install Poetry: https://python-poetry.org/docs/#installation
- Install deps (including dev/tools): `poetry install --with dev`

Checks to run locally
---------------------
- Format: `poetry run black --check .`
- Type check: `poetry run mypy --strict swidget`
- Tests: `poetry run pytest --cov=swidget --cov-report=term-missing`
- Docs: `cd docs && poetry run sphinx-build -b html . _build`

Git hooks
---------
- Enable project hook (runs black, pytest+coverage, mypy): `git config core.hooksPath githooks`

Style
-----
- Keep code typed; prefer `dict[str, Any]` over bare `dict`
- Avoid network calls in unit tests; use mocks
- Prefer explicit imports over wildcards

Reporting issues / PRs
----------------------
- Describe the change and expected behavior
- Include repro steps for bugs
- Note any new dependencies or breaking changes
