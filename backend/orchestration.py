"""Dagster definitions for repeatable, durable evaluation runs."""

from dagster import AssetExecutionContext, Definitions, asset

from backend.evaluation.runner import compare_baselines
from backend.evaluation.scenarios import load_scenarios
from backend.persistence.database import session_factory
from backend.persistence.repository import PersistenceBatch, SQLRepository


@asset(group_name="evaluation")
def baseline_evaluation_results(context: AssetExecutionContext) -> int:
    """Regenerate baselines and persist each reproducible result."""
    repository = SQLRepository(session_factory)
    results = compare_baselines(load_scenarios())
    for result in results:
        repository.save(PersistenceBatch(evaluation=result))

    context.log.info("Persisted %s baseline evaluation results", len(results))
    return len(results)


defs = Definitions(assets=[baseline_evaluation_results])
