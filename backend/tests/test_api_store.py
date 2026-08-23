from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep

import pytest

from backend.api.store import FactoryStore
from backend.simulator.engine import FactorySimulator
from backend.simulator.seed import factory_01


def test_store_reuses_and_resets_active_simulator() -> None:
    store = FactoryStore()

    first = store.get("factory_01")
    second = store.get("factory_01")
    reset = store.reset("factory_01")

    assert first is second
    assert reset is not first
    assert store.get("factory_01") is reset


def test_store_recovers_snapshot_on_first_activation() -> None:
    store = FactoryStore()
    recovered = factory_01()
    recovered.sim_hour = 12

    recovered_simulator = FactorySimulator(recovered)
    simulator = store.get("factory_01", lambda _: recovered_simulator)

    assert simulator.state.sim_hour == 12
    assert simulator.state is recovered


def test_store_rejects_unknown_factory() -> None:
    store = FactoryStore()

    with pytest.raises(KeyError, match="missing"):
        store.get("missing")


def test_store_serializes_mutations_for_one_factory() -> None:
    store = FactoryStore()
    barrier = Barrier(2)

    def increment_version() -> None:
        barrier.wait()
        with store.locked("factory_01") as simulator:
            version = simulator.state.schedule_version
            sleep(0.01)
            simulator.state.schedule_version = version + 1

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(increment_version) for _ in range(2)]
        for future in futures:
            future.result()

    assert store.get("factory_01").state.schedule_version == 2
