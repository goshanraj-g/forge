import pytest
from pydantic import ValidationError

from backend.simulator.models import (
    InventoryItem,
    Machine,
    MachineStatus,
    Order,
    OrderStatus,
    Product,
    ProductionJob,
    Shipment,
    ShipmentStatus,
    Supplier,
    q,
)

def test_q_rounds_to_storage_precision() -> None:
    assert q(1.12345678) == 1.123457

def test_machine_defaults_to_available_and_idle() -> None:
    machine = Machine(
        id="M1",
        name="Assembly Line 1",
        capacity_per_hour=20,
        supported_products=["P1", "P2"],
    )

    assert machine.status == MachineStatus.IDLE
    assert machine.is_available()
    assert machine.can_produce("P1")
    assert not machine.can_produce("P3")

def test_down_machine_is_not_available() -> None:
    machine = Machine(
        id="M1",
        name="Assembly Line 1",
        capacity_per_hour=20,
        supported_products=["P1"],
        status=MachineStatus.DOWN,
        down_until_hour=8,
    )

    assert not machine.is_available()

def test_machine_rejects_negative_capacity() -> None:
    with pytest.raises(ValidationError):
        Machine(
            id="M1",
            name="Assembly Line 1",
            capacity_per_hour=-1,
            supported_products=["P1"],
        )

def test_products_do_not_share_bom_dictionaries() -> None:
    first = Product(id="P1", name="Motor", family="drive")
    second = Product(id="P2", name="Battery", family="energy")

    first.bom["steel"] = 2.0

    assert second.bom == {}

def test_order_calculates_remaining_quantity() -> None:
    order = Order(
        id="O1",
        product_id="P1",
        quantity=100,
        due_hour=24,
        produced=35.5,
    )

    assert order.remaining == 64.5
    assert order.is_open()

def test_completed_order_is_not_open() -> None:
    order = Order(
        id="O1",
        product_id="P1",
        quantity=100,
        due_hour=24,
        produced=100,
        status=OrderStatus.COMPLETE,
        completed_hour=20,
    )

    assert order.remaining == 0
    assert not order.is_open()

def test_inventory_calculates_available_quantity() -> None:
    inventory = InventoryItem(
        component_id="steel",
        on_hand=100,
        reserved=35.5,
        reorder_point=20,
    )

    assert inventory.available == 64.5

def test_available_inventory_never_becomes_negative() -> None:
    inventory = InventoryItem(
        component_id="steel",
        on_hand=10,
        reserved=12,
    )

    assert inventory.available == 0

def test_supplier_rejects_negative_lead_time() -> None:
    with pytest.raises(ValidationError):
        Supplier(
            id="S1",
            component_id="steel",
            lead_time_hours=-1,
        )


def test_shipment_defaults_to_in_transit() -> None:
    shipment = Shipment(
        id="SH1",
        supplier_id="S1",
        component_id="steel",
        quantity=100,
        eta_hour=12,
    )

    assert shipment.status == ShipmentStatus.IN_TRANSIT

def test_production_job_uses_half_open_interval() -> None:
    job = ProductionJob(
        id="J1",
        order_id="O1",
        machine_id="M1",
        product_id="P1",
        start_hour=2,
        end_hour=5,
        quantity=60,
    )

    assert not job.is_active_at(1.99)
    assert job.is_active_at(2)
    assert job.is_active_at(4.99)
    assert not job.is_active_at(5)


def test_production_job_rejects_negative_quantity() -> None:
    with pytest.raises(ValidationError):
        ProductionJob(
            id="J1",
            order_id="O1",
            machine_id="M1",
            product_id="P1",
            start_hour=2,
            end_hour=5,
            quantity=-1,
        )
