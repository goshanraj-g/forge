"""Seed factory states used by simulations and evaluations."""

from __future__ import annotations

from backend.simulator.models import (
    InventoryItem,
    Machine,
    Order,
    Product,
    Shipment,
    Supplier,
)
from backend.simulator.state import FactoryState

HORIZON_HOURS = 72.0


def _machines() -> list[Machine]:
    return [
        Machine(
            id="M1",
            name="Assembly Line 1",
            capacity_per_hour=20,
            supported_products=["P1", "P2"],
            changeover_minutes=45,
        ),
        Machine(
            id="M2",
            name="Assembly Line 2",
            capacity_per_hour=18,
            supported_products=["P1", "P2", "P3"],
            changeover_minutes=45,
        ),
        Machine(
            id="M3",
            name="Battery Cell 1",
            capacity_per_hour=25,
            supported_products=["P3", "P4"],
            changeover_minutes=30,
        ),
        Machine(
            id="M4",
            name="Battery Cell 2",
            capacity_per_hour=22,
            supported_products=["P3", "P4"],
            changeover_minutes=30,
        ),
        Machine(
            id="M5",
            name="Finishing",
            capacity_per_hour=30,
            supported_products=["P1", "P2", "P3", "P4", "P5"],
            changeover_minutes=20,
        ),
    ]


def _products() -> list[Product]:
    return [
        Product(
            id="P1",
            name="Drive Motor",
            family="motor",
            bom={"C1": 2, "C2": 1},
            unit_cost=48,
        ),
        Product(
            id="P2",
            name="Steering Actuator",
            family="motor",
            bom={"C1": 1, "C3": 2},
            unit_cost=36,
        ),
        Product(
            id="P3",
            name="Battery Pack",
            family="battery",
            bom={"C4": 4, "C5": 1},
            unit_cost=92,
        ),
        Product(
            id="P4",
            name="Battery Module",
            family="battery",
            bom={"C4": 2},
            unit_cost=41,
        ),
        Product(
            id="P5",
            name="Wiring Harness",
            family="harness",
            bom={"C2": 1, "C3": 1},
            unit_cost=18,
        ),
    ]


def _orders() -> list[Order]:
    rows = [
        ("ORD-001", "P1", 240, 18, 2, 180),
        ("ORD-002", "P3", 180, 22, 1, 320),
        ("ORD-003", "P2", 150, 26, 3, 90),
        ("ORD-004", "P4", 300, 30, 2, 150),
        ("ORD-005", "P1", 200, 34, 2, 180),
        ("ORD-006", "P5", 400, 38, 3, 60),
        ("ORD-007", "P3", 220, 42, 1, 320),
        ("ORD-008", "P2", 160, 46, 3, 90),
        ("ORD-009", "P4", 260, 50, 2, 150),
        ("ORD-010", "P1", 180, 56, 2, 180),
        ("ORD-011", "P3", 140, 62, 1, 320),
        ("ORD-012", "P5", 320, 68, 3, 60),
    ]

    return [
        Order(
            id=order_id,
            product_id=product_id,
            quantity=quantity,
            due_hour=due_hour,
            priority=priority,
            late_penalty_per_hour=penalty,
        )
        for order_id, product_id, quantity, due_hour, priority, penalty in rows
    ]


def _inventory() -> list[InventoryItem]:
    rows = [
        ("C1", 1800, 300),
        ("C2", 1400, 250),
        ("C3", 1600, 250),
        ("C4", 2600, 500),
        ("C5", 700, 150),
    ]

    return [
        InventoryItem(
            component_id=component_id,
            on_hand=on_hand,
            reorder_point=reorder_point,
        )
        for component_id, on_hand, reorder_point in rows
    ]


def _suppliers() -> list[Supplier]:
    return [
        Supplier(
            id="S1",
            component_id="C1",
            lead_time_hours=24,
            reliability=0.95,
        ),
        Supplier(
            id="S2",
            component_id="C4",
            lead_time_hours=36,
            reliability=0.90,
        ),
        Supplier(
            id="S3",
            component_id="C5",
            lead_time_hours=12,
            reliability=0.98,
        ),
    ]


def _shipments() -> list[Shipment]:
    return [
        Shipment(
            id="SH-001",
            supplier_id="S2",
            component_id="C4",
            quantity=1200,
            eta_hour=20,
        ),
        Shipment(
            id="SH-002",
            supplier_id="S3",
            component_id="C5",
            quantity=400,
            eta_hour=28,
        ),
    ]


def factory_01() -> FactoryState:
    """Return a fresh instance of the demo factory."""
    return FactoryState(
        name="factory_01",
        machines={machine.id: machine for machine in _machines()},
        products={product.id: product for product in _products()},
        orders={order.id: order for order in _orders()},
        inventory={item.component_id: item for item in _inventory()},
        suppliers={supplier.id: supplier for supplier in _suppliers()},
        shipments={shipment.id: shipment for shipment in _shipments()},
    )


FACTORY_REGISTRY = {
    "factory_01": factory_01,
}


def load_factory(name: str) -> FactoryState:
    """Load a fresh factory state by name"""
    if name not in FACTORY_REGISTRY:
        known = sorted(FACTORY_REGISTRY)
        # Modify f string to see any weird input
        raise KeyError(f"unknown factory {name!r}; known factories: {known}")

    # Find the factory and call it immediately
    return FACTORY_REGISTRY[name]()
