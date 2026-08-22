"""Complete State for one factory simulation"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, Field

from backend.simulator.models import (
    InventoryItem,
    Machine,
    Order,
    Product,
    ProductionJob,
    Shipment,
    Supplier,
)


class FactoryState(BaseModel):
    name: str = "factory_01"
    sim_hour: float = 0.0
    schedule_version: int = 0

    machines: dict[str, Machine] = Field(default_factory=dict)
    products: dict[str, Product] = Field(default_factory=dict)
    orders: dict[str, Order] = Field(default_factory=dict)
    inventory: dict[str, InventoryItem] = Field(default_factory=dict)
    suppliers: dict[str, Supplier] = Field(default_factory=dict)
    shipments: dict[str, Shipment] = Field(default_factory=dict)
    jobs: dict[str, ProductionJob] = Field(default_factory=dict)

    overtime_hours: float = 0.0
    changeover_hours: float = 0.0
    production_cost: float = 0.0
    late_penalty_cost: float = 0.0

    def machine_list(self) -> list[Machine]:
        return [self.machines[key] for key in sorted(self.machines)]

    def product_list(self) -> list[Product]:
        return [self.products[key] for key in sorted(self.products)]

    def order_list(self) -> list[Order]:
        return [self.orders[key] for key in sorted(self.orders)]

    def inventory_list(self) -> list[InventoryItem]:
        return [self.inventory[key] for key in sorted(self.inventory)]

    def supplier_list(self) -> list[Supplier]:
        return [self.suppliers[key] for key in sorted(self.suppliers)]

    def shipment_list(self) -> list[Shipment]:
        return [self.shipments[key] for key in sorted(self.shipments)]

    def job_list(self) -> list[ProductionJob]:
        return [self.jobs[key] for key in sorted(self.jobs)]

    def open_orders(self) -> list[Order]:
        return [order for order in self.order_list() if order.is_open()]

    def jobs_for_machine(self, machine_id: str) -> list[ProductionJob]:
        return [job for job in self.job_list() if job.machine_id == machine_id]

    def total_cost(self) -> float:
        return round(
            self.production_cost + self.late_penalty_cost,
            6,
        )

    def canonical(self) -> str:
        """Return a stable JSON representation of the complete state"""
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    def snapshot_hash(self) -> str:
        """Return a content hash used to compare simulation runs"""
        return hashlib.sha256(self.canonical().encode()).hexdigest()

    def clone(self) -> FactoryState:
        """Returns a deep copy that shares no mutable entity state"""
        return self.model_copy(deep=True)
