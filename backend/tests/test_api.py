from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.store import factory_store

client = TestClient(app)


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
