from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

from backend.api.app import app
from backend.api.dependencies import get_agent_model, get_agent_timeout, get_repository
from backend.api.store import factory_store
from backend.persistence.repository import PersistenceBatch
from backend.simulator.events import MachineFailureEvent
from backend.simulator.models import Machine, Order, Product, ProductionJob
from backend.simulator.state import FactoryState

client = TestClient(app)


class RecordingRepository:
    def __init__(self) -> None:
        self.batches: list[PersistenceBatch] = []

    def save(self, batch: PersistenceBatch) -> None:
        self.batches.append(batch)

    def latest_snapshot(self, factory_name: str) -> FactoryState | None:
        return None

    def recover_factory(self, factory_name: str) -> None:
        return None


test_repository = RecordingRepository()
app.dependency_overrides[get_repository] = lambda: test_repository
app.dependency_overrides[get_agent_timeout] = lambda: 30.0


def get_test_agent_model() -> TestModel:
    return TestModel()


def test_app_configures_agent_observability_at_startup() -> None:
    with (
        patch("backend.api.app.configure_agent_observability") as configure,
        TestClient(app) as lifespan_client,
    ):
        response = lifespan_client.get("/health")

    assert response.status_code == 200
    configure.assert_called_once_with()


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "forgeops",
    }


def test_get_factory() -> None:
    response = client.get("/factories/factory_01")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "factory_01"
    assert body["sim_hour"] == 0
    assert len(body["machines"]) == 5
    assert len(body["orders"]) == 12


def test_get_unknown_factory_returns_404() -> None:
    response = client.get("/factories/missing")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "unknown factory 'missing'",
    }


def test_tick_advances_factory_clock() -> None:
    factory_store.clear()

    response = client.post(
        "/factories/factory_01/tick",
        json={"step_hours": 0.5},
    )

    assert response.status_code == 200
    assert response.json()["state"]["sim_hour"] == 0.5


def test_tick_does_not_publish_state_when_persistence_fails() -> None:
    class FailingRepository(RecordingRepository):
        def save(self, batch: PersistenceBatch) -> None:
            raise RuntimeError("database unavailable")

    factory_store.clear()
    simulator = factory_store.get("factory_01")
    original_hash = simulator.state.snapshot_hash()
    app.dependency_overrides[get_repository] = FailingRepository
    try:
        response = client.post(
            "/factories/factory_01/tick",
            json={"step_hours": 0.5},
        )
    finally:
        app.dependency_overrides[get_repository] = lambda: test_repository

    assert response.status_code == 503
    assert simulator.state.snapshot_hash() == original_hash


def test_tick_rejects_nonpositive_step() -> None:
    response = client.post(
        "/factories/factory_01/tick",
        json={"step_hours": 0},
    )

    assert response.status_code == 422


def test_run_until_advances_to_requested_hour() -> None:
    factory_store.clear()

    response = client.post(
        "/factories/factory_01/run-until",
        json={
            "hour": 2,
            "step_hours": 0.25,
        },
    )

    assert response.status_code == 200
    assert response.json()["state"]["sim_hour"] == 2


def test_run_until_rejects_backwards_time() -> None:
    factory_store.clear()
    simulator = factory_store.get("factory_01")
    simulator.tick(1)

    response = client.post(
        "/factories/factory_01/run-until",
        json={"hour": 0.5},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "cannot run backwards",
    }


def test_schedule_and_apply_machine_failure() -> None:
    factory_store.clear()

    scheduled = client.post(
        "/factories/factory_01/events",
        json={
            "type": "machine_failure",
            "sim_hour": 0.5,
            "machine_id": "M1",
            "duration_hours": 2,
        },
    )

    assert scheduled.status_code == 202
    assert scheduled.json()["event"]["id"] == "evt-00001"
    assert scheduled.json()["pending_event_count"] == 1

    ticked = client.post(
        "/factories/factory_01/tick",
        json={"step_hours": 0.5},
    )

    assert ticked.status_code == 200
    assert ticked.json()["state"]["machines"]["M1"]["status"] == "down"


def test_investigates_processed_factory_event() -> None:
    factory_store.clear()
    simulator = factory_store.get("factory_01")
    simulator.schedule(
        MachineFailureEvent(
            id="evt-investigate",
            sim_hour=0,
            machine_id="M1",
            duration_hours=2,
        )
    )
    simulator.tick(0.25)
    app.dependency_overrides[get_agent_model] = get_test_agent_model

    try:
        response = client.post(
            "/factories/factory_01/investigations",
            json={"event_id": "evt-investigate"},
        )
    finally:
        app.dependency_overrides.pop(get_agent_model, None)

    assert response.status_code == 200
    body = response.json()
    assert body["factory_name"] == "factory_01"
    assert body["trigger_event_id"] == "evt-investigate"
    assert body["trigger_event_type"] == "machine_failure"
    assert body["state_snapshot_hash"] == simulator.state.snapshot_hash()
    assert body["decision"]["status"] == "no_action"


def test_investigation_rejects_unknown_event() -> None:
    factory_store.clear()
    app.dependency_overrides[get_agent_model] = get_test_agent_model

    try:
        response = client.post(
            "/factories/factory_01/investigations",
            json={"event_id": "missing"},
        )
    finally:
        app.dependency_overrides.pop(get_agent_model, None)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "processed event 'missing' was not found",
    }


def test_rejects_event_in_the_past() -> None:
    factory_store.clear()
    factory_store.get("factory_01").tick(1)

    response = client.post(
        "/factories/factory_01/events",
        json={
            "type": "machine_failure",
            "sim_hour": 0.5,
            "machine_id": "M1",
            "duration_hours": 2,
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "cannot schedule an event in the past",
    }


def test_rejects_noninjectable_event_type() -> None:
    factory_store.clear()

    response = client.post(
        "/factories/factory_01/events",
        json={
            "type": "order_complete",
            "sim_hour": 1,
            "order_id": "ORD-001",
            "hours_late": 0,
        },
    )

    assert response.status_code == 422


def test_optimize_returns_candidate_without_changing_factory() -> None:
    factory_store.clear()
    simulator = factory_store.get("factory_01")
    original_hash = simulator.state.snapshot_hash()

    response = client.post(
        "/factories/factory_01/optimize",
        json={
            "horizon_hours": 72,
            "bucket_hours": 1,
            "time_limit_seconds": 10,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"optimal", "feasible"}
    assert len(body["jobs"]) == 12
    assert body["validation"]["violations"] == []
    assert simulator.state.snapshot_hash() == original_hash


def test_commit_schedule_revalidates_and_updates_version() -> None:
    factory_store.clear()
    simulator = factory_store.get("factory_01")
    simulator.state = FactoryState(
        machines={
            "M1": Machine(
                id="M1",
                name="Line 1",
                capacity_per_hour=10,
                supported_products=["P1"],
            ),
        },
        products={
            "P1": Product(id="P1", name="Widget", family="widget"),
        },
        orders={
            "O1": Order(id="O1", product_id="P1", quantity=10, due_hour=2),
        },
    )
    job = ProductionJob(
        id="J1",
        order_id="O1",
        machine_id="M1",
        product_id="P1",
        start_hour=0,
        end_hour=1,
        quantity=10,
        schedule_version=1,
    )

    response = client.post(
        "/factories/factory_01/schedules/commit",
        json={
            "expected_version": 0,
            "jobs": [job.model_dump(mode="json")],
        },
    )

    assert response.status_code == 200
    assert response.json()["state"]["schedule_version"] == 1
    assert len(response.json()["state"]["jobs"]) == 1
    assert simulator.state.schedule_version == 1


def test_commit_rejects_stale_version() -> None:
    factory_store.clear()
    simulator = factory_store.get("factory_01")
    simulator.state.schedule_version = 1

    response = client.post(
        "/factories/factory_01/schedules/commit",
        json={"expected_version": 0, "jobs": []},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "stale schedule version 0; current version is 1"
    )


def test_commit_rejects_incomplete_schedule() -> None:
    factory_store.clear()

    response = client.post(
        "/factories/factory_01/schedules/commit",
        json={"expected_version": 0, "jobs": []},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == (
        "schedule does not cover every open order"
    )
