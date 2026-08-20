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

## Project status

The repository is being built in reviewable stages. Stage 1, the factory domain
model, is currently in progress. The simulator, optimizer, API, UI, agent, and
evaluation harness will be added in later pull requests.

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
