import pytest

from backend.api.store import FactoryStore


def test_store_reuses_and_resets_active_simulator() -> None:
    store = FactoryStore()

    first = store.get("factory_01")
    second = store.get("factory_01")
    reset = store.reset("factory_01")

    assert first is second
    assert reset is not first
    assert store.get("factory_01") is reset


def test_store_rejects_unknown_factory() -> None:
    store = FactoryStore()

    with pytest.raises(KeyError, match="missing"):
        store.get("missing")
