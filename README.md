# ForgeOps

ForgeOps is a factory scheduling demo; it models a production floor, introduces
disruptions such as machine failures and late shipments, and measures whether
replanning improves delivery performance and cost.

The project separates four jobs that are easy to blur together:

- the simulator owns factory state and applies production rules;
- the optimizer calculates schedules under explicit constraints;
- the agent investigates disruptions and decides when replanning is useful;
- the evaluation runner checks those decisions against repeatable baselines.

The agent cannot change factory state directly. Candidate schedules are checked
by deterministic validation before they can be committed.

## Project planning

The [system design](docs/design.md) describes the component boundaries, failure
handling, evaluation plan, and the completion criteria for each stage.

## Local setup

ForgeOps requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Regenerate the baseline evaluation table from clean factory snapshots with:

```bash
python -m backend.evaluation
```

## Checks

Continuous integration runs these checks on every pull request, across Python
3.11, 3.12, and 3.13:

```bash
ruff check .          # lint
ruff format --check . # formatting
mypy                  # strict type checking
pytest --cov          # tests and coverage
python -m backend.evaluation # evaluation smoke test (Python 3.12 CI job)
```

Installing the pre-commit hooks runs the lint and format steps before each
commit, so the same failures surface locally rather than in CI:

```bash
pre-commit install
```
