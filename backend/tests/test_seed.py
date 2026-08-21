import pytest

from backend.simulator.seed import HORIZON_HOURS, factory_01, load_factory


def test_factory_01_has_consistent_demo_data() -> None:
    state = factory_01()

    assert HORIZON_HOURS == 72
    assert len(state.machines) == 5
    assert len(state.products) == 5
    assert len(state.orders) == 12
    assert len(state.inventory) == 5
    assert len(state.suppliers) == 3
    assert len(state.shipments) == 2

    assert all(order.product_id in state.products for order in state.order_list())
    assert all(
        shipment.supplier_id in state.suppliers
        and shipment.component_id in state.inventory
        for shipment in state.shipment_list()
    )


def test_loading_factory_returns_fresh_state() -> None:
    first = load_factory("factory_01")
    second = load_factory("factory_01")

    first.orders["ORD-001"].produced = 100
    first.inventory["C1"].on_hand = 0

    assert second.orders["ORD-001"].produced == 0
    assert second.inventory["C1"].on_hand == 1800
    assert first is not second


def test_loading_unknown_factory_reports_known_names() -> None:
    with pytest.raises(KeyError, match="missing_factory"):
        load_factory("missing_factory")
