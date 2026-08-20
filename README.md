# ForgeOps

ForgeOps is a factory decision-intelligence system that combines deterministic
simulation, mathematical optimization, and an AI operations agent. It is built
to answer a measurable question: when production is disrupted, can the system
recover service levels and cost without hiding uncertainty or violating factory
constraints?

The simulator owns factory truth, the optimizer computes schedules, the agent
investigates disruptions and recommends action, and the evaluation harness
measures the resulting operational outcomes.

## Status

ForgeOps is being built incrementally. The current stage establishes the domain
model and deterministic factory state; simulation, optimization, API, agent, and
evaluation layers follow as independently reviewable changes.

See [the system design](docs/design.md) for component boundaries, runtime flows,
correctness guarantees, and the implementation roadmap.

## Development

ForgeOps requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## Design principle

> The agent proposes, the optimizer calculates, the validator checks, and the
> simulator enforces.

No AI-generated action directly mutates factory state.
