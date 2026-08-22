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
