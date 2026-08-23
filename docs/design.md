# ForgeOps system design

## What we are building

ForgeOps is a small manufacturing operations system built around a simulated
factory. It starts with a production schedule, introduces disruptions such as a
machine failure or late shipment, and decides whether the schedule should
change.

The project is meant to test a specific architecture, not to model every part of
a real plant. The simulator keeps the facts, a constraint solver does the
scheduling math, and an AI agent decides what to inspect and whether replanning
is worth doing. A separate evaluation runner checks whether that combination
actually reduces late orders or cost.

The main rule is: **the agent can propose an action, but it cannot make an
invalid action true.** Every candidate schedule must pass deterministic
validation before it can replace the current schedule.

## Scope

The first version models machines, products, customer orders, component
inventory, incoming shipments, production jobs, and a simulation clock. The
initial disruptions are machine failures, supplier delays, urgent orders, and
low inventory.

Labor rosters, multiple plants, transport networks, ERP integration, and real
machine telemetry are out of scope. They may be useful later, but adding them
now would obscure the scheduling and decision boundaries this project is meant
to demonstrate.

## Architecture

```text
React UI ──HTTP──► FastAPI
                     ├──► Simulator ──► factory state
                     ├──► AI agent ───► typed read tools
                     │       └────────► Optimizer
                     └──► Evaluation runner
                              └───────► Simulator + Agent + Optimizer
```

| Component | Responsibility |
| --- | --- |
| Simulator | Own factory state and apply physical rules deterministically |
| Optimizer | Calculate schedules under explicit constraints and objectives |
| AI agent | Investigate events, decide whether action is warranted, and explain why |
| FastAPI | Validate transport data and coordinate application workflows |
| React UI | Present factory state, schedules, decisions, and evaluation results |
| Evaluations | Replay scenarios and compare outcomes with reproducible baselines |

The API coordinates the simulator and agent. The agent reads simulator state
through typed tools and can request an optimization. The simulator and optimizer
never import the API or agent, so both can be tested without a model provider,
network, or web server.

## Domain and state ownership

The initial domain contains machines, products, orders, inventory, suppliers,
shipments, and production jobs. `FactoryState` is the single owner of the active
simulation snapshot.

The simulator advances an explicit simulation clock. It applies scheduled
events, produces units on active machines, consumes components, receives
shipments, updates orders, and records actual cost. It never reads wall-clock
time. Collections are processed in sorted identifier order, and calculated
floats are rounded at state-write boundaries. Identical initial state and event
streams must produce identical snapshots and event logs.

## Decision flow

A disruption follows this path:

1. The API validates and submits an event to the simulator.
2. The simulator applies the event and records the new source-of-truth state.
3. The agent investigates through read-only, typed tools.
4. If replanning is warranted, the optimizer returns a candidate schedule.
5. Deterministic validation checks the candidate against factory constraints.
6. Policy determines whether the validated candidate can be committed
   automatically or requires human approval.
7. The simulator atomically commits an approved candidate and preserves the
   previous schedule otherwise.

The agent never calculates schedule feasibility or operational metrics. It may
explain validator and evaluator outputs, but deterministic systems remain the
source of those facts.

## Scheduling correctness

Validation covers at least:

- machine and product compatibility;
- machine downtime and overlapping jobs;
- inventory availability and bill-of-material consumption;
- required production quantities;
- hard deadlines and explicitly authorized constraint relaxation.

Correctness and quality are separate. A schedule is feasible when it satisfies
all hard constraints. Among feasible schedules, the objective compares late
delivery penalties, overtime, and changeover cost.

Every scheduling operation has an explicit result status:

| Status | Meaning |
| --- | --- |
| `optimal` | Feasible and proven best for the configured objective |
| `feasible` | Valid, but not proven optimal within the search limit |
| `partial` | A validated subset is schedulable; every omission has a reason |
| `infeasible` | The solver proved that all constraints cannot be satisfied together |
| `unknown` | Search ended without proving feasibility or infeasibility |
| `error` | The scheduling operation failed |

An `unknown` result must never be presented as `infeasible`. Feasible results
report the solver's optimality gap when available. Partial results identify all
unscheduled orders, assumptions, warnings, and required actions. A partial plan
is commit-eligible only when its scheduled subset is independently valid and
business policy permits partial execution.

## Failure handling and escalation

Candidate generation and validation may form a bounded repair loop. Attempt
limits, solver time limits, and overall request deadlines prevent infinite agent
loops. State is not mutated during this loop.

When no acceptable candidate is found, ForgeOps retains the last valid schedule,
continues unaffected work when safe, and communicates the precise outcome:

- missing data produces `needs_information` with the required fields;
- proven conflicting constraints produce `infeasible` with blocking reasons;
- exhausted search produces `unknown` rather than a false impossibility claim;
- execution failures produce `error` with an auditable failure record.

Low-risk, validated schedule changes may be committed by deterministic policy.
Material substitutions, hard-constraint relaxation, priority deadline misses,
and other high-risk tradeoffs require explicit human approval.

## Evaluation

The evaluation runner executes the core components without the API or UI. Each
scenario begins from a named factory snapshot, injects an ordered event stream,
runs a decision policy, completes the simulation, and calculates deterministic
metrics.

Every scenario is compared with three baselines:

1. **No-op:** preserve the original schedule.
2. **Always replan:** optimize after every event without agent selectivity.
3. **Oracle:** use scenario ground-truth labels to replan only for material
   events. The labels are written with advance knowledge of the complete event
   stream; the optimizer still receives only the state available at decision
   time.

Primary metrics include late orders, priority-weighted lateness, production and
penalty cost, overtime, constraint violations, replans, model calls, and model
cost. Repeated scenarios verify determinism before their metrics are considered
valid.

## Delivery plan

Each stage should fit into its own pull request. A stage is complete when its
tests pass and the behavior it introduces can be demonstrated without relying
on unfinished later stages.

### Stage 1: domain model

Define the vocabulary shared by the backend: machines, products, orders,
inventory, suppliers, shipments, production jobs, and their statuses. Add small
entity behaviors such as remaining order quantity, available inventory, machine
compatibility, and active job intervals.

Tests cover invalid negative quantities, defaults, calculated properties, and
job interval boundaries. At the end of this stage there is no simulation yet,
but factory data can be created and validated consistently.

### Stage 2: deterministic simulator

Add `FactoryState`, typed events, a seed factory, and the engine that advances
time. The engine applies failures and delays, runs scheduled jobs, consumes
inventory, receives shipments, completes orders, and records actual costs.

Tests cover event ordering, machine recovery, inventory consumption, shipment
arrival, order completion, lateness, and repeated runs. This stage is done when
the same seeded scenario produces the same event log and snapshot hash twice.

### Stage 3: optimizer and schedule validator

Add an initial scheduling policy for bootstrap schedules and an OR-Tools CP-SAT
model for replanning. Return typed outcomes for optimal, feasible, partial,
infeasible, unknown, and error results. Keep candidate generation separate from
commit-time validation.

Tests use small cases that can be checked by hand: incompatible machines,
overlapping jobs, insufficient inventory, downtime, an impossible deadline,
and a feasible problem with a known best result. This stage is done when no
candidate can be committed without passing validation.

### Stage 4: API and factory UI

Expose factory snapshots, clock controls, event injection, and schedule versions
through FastAPI. Build the Factory and Schedule pages first so the simulator and
optimizer can be exercised without an AI dependency.

API tests cover input validation, error responses, and state changes. A browser
smoke test covers loading the factory, advancing time, injecting a failure, and
viewing the revised schedule. This stage is done when that flow works manually
from the UI.

### Stage 5: agent decisions

Add typed, read-only tools for machines, orders, inventory, shipments, and the
current schedule. Add the optimization tool and a structured decision containing
severity, affected orders, whether to replan, and an explanation.

Tests use a deterministic test model to verify tool arguments, structured
output, and the rule that the agent cannot mutate state. This stage is done when
an injected disruption produces an auditable decision and every proposed
schedule still follows the normal validation and approval path.

### Stage 6: evaluation harness

Add scenario files, the headless runner, deterministic metrics, and the no-op,
always-replan, and oracle baselines. Record enough run metadata to reproduce a
result and trace a bad metric back to the decision that produced it.

Tests cover scenario validation, metric calculations, isolation between runs,
and repeatability. This stage is done when one command regenerates a comparison
table from clean initial states.

### Stage 7: persistence and operational hardening

Store durable events, schedules, decisions, and evaluation results behind a
repository interface backed by Postgres. Add migrations, CI, structured logs,
prompt and model versioning, request timeouts, and deployment configuration.

Tests cover repository behavior, migrations, transaction boundaries, and safe
recovery after a failed decision or optimization. This prepares the demo for
repeatable deployment; it does not turn the simulator into a production
manufacturing execution system.

## Open decisions

Things to consider during the implementation:

- simulation tick size;
- optimizer bucket size and time limit;
- which validated changes can be committed without human approval;
- whether partial schedules provide enough value to enable by default;
- whether retrieval of past decisions improves evaluation results;
- when active simulation state should move from memory to Postgres.

They are open on purpose; when we test and evaluate results, that info should
settle them
