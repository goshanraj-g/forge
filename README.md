# Forge

Forge is an agentic manufacturing ERP prototype; it models a production floor, introduces
disruptions such as machine failures and late shipments, and measures whether
replanning improves delivery performance and cost.

The project separates four jobs that are easy to blur together:

- the simulator owns factory state and applies production rules;
- the optimizer calculates schedules under explicit constraints;
- the agent investigates disruptions and decides when replanning is useful;
- the evaluation runner checks those decisions against repeatable baselines.

The agent cannot change factory state directly. Candidate schedules are checked
by deterministic validation before they can be committed.


## System Architecture

<img width="841" height="1203" alt="Event-Driven Factory-2026-08-23-214954" src="https://github.com/user-attachments/assets/90f3669c-9d1f-40c8-a170-f2a76c7118d4" />

## Sequence Diagram
<img width="819" height="781" alt="Event-Driven Factory-2026-08-23-235001" src="https://github.com/user-attachments/assets/b394fedb-22c9-47cf-ae57-0d7957485a74" />

## Project Planning

The [system design](docs/design.md) describes the component boundaries, failure
handling, evaluation plan, and the completion criteria for each stage.

## Local setup

Forge requires Python 3.11 or newer.

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

The baseline table uses the production CP-SAT scheduler. In the web application,
the evaluation page also offers an explicit **Run real agent evaluation** action.
It adds an agent policy to the same scenarios and scheduler; the action is opt-in
because it makes live model calls and its output may vary between runs.

For the PostgreSQL/pgvector deployment, copy `.env.example` to `.env`, add the
required secrets, and start the database, migrations, and API together:

```bash
docker compose up --build
```

Open the complete application at `http://localhost:3000`. Nginx serves the Vite
build and proxies API requests to FastAPI over the internal Compose network.

Dagster can materialize and persist the repeatable evaluation suite with:

```bash
dagster asset materialize -m backend.orchestration
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
