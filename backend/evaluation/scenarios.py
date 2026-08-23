"""Loading and hashing of version-controlled evaluation scenarios."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import TypeAdapter

from backend.evaluation.models import EvaluationScenario

SCENARIO_DIRECTORY = Path(__file__).with_name("scenario_files")
SCENARIO_ADAPTER = TypeAdapter(EvaluationScenario)


def load_scenario(path: Path) -> EvaluationScenario:
    return SCENARIO_ADAPTER.validate_json(path.read_text(encoding="utf-8"))


def load_scenarios(directory: Path = SCENARIO_DIRECTORY) -> list[EvaluationScenario]:
    return [load_scenario(path) for path in sorted(directory.glob("*.json"))]


def scenario_hash(scenario: EvaluationScenario) -> str:
    payload = scenario.model_dump(mode="json")
    payload["oracle_replan_event_ids"] = sorted(scenario.oracle_replan_event_ids)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
