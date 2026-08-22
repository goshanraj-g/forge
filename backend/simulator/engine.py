"""Deterministic factory simulation engine."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from backend.simulator import events as ev
from backend.simulator.models import (
    MachineStatus,
    Order,
    OrderStatus,
    Product,
    ShipmentStatus,
    q,
)
from backend.simulator.state import FactoryState

DEFAULT_STEP_HOURS = 0.25
NOMINAL_SHIFT_HOURS = 16.0
HOURS_PER_DAY = 24.0

OVERTIME_COST_PER_HOUR = 120.0
CHANGEOVER_COST_PER_HOUR = 80.0


@dataclass
class SimulationContext:
    """Values and utilities owned by one simulation run"""

    seed: int = 0
    step_hours: float = DEFAULT_STEP_HOURS
    rng: random.Random = field(init=False)
    _counter: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.step_hours <= 0:
            raise ValueError("step_hours must be positive")

        self.rng = random.Random(self.seed)

    def next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter:05d}"


def overtime_overlap(
    start: float,
    end: float,
    shift_hours: float = NOMINAL_SHIFT_HOURS,
    day_hours: float = HOURS_PER_DAY,
) -> float:
    """Return the part of an interval that falls outside nominal shifts"""

    if end <= start:
        return 0.0

    total = 0.0
    first_day = int(start // day_hours)
    last_day = int((end - 1e-9) // day_hours)

    for day in range(first_day, last_day + 1):
        overtime_start = day * day_hours + shift_hours
        overtime_end = (day + 1) * day_hours

        overlap_start = max(start, overtime_start)
        overlap_end = min(end, overtime_end)

        if overlap_end > overlap_start:
            total += overlap_end - overlap_start
    return q(total)


class FactorySimulator:
    """Own factory state and apply all simulation state changes"""

    def __init__(
        self,
        state: FactoryState,
        context: SimulationContext | None = None,
        pending_events: list[ev.BaseEvent] | None = None,
    ) -> None:
        self.state = state
        self.context = context or SimulationContext()
        self.pending = ev.sort_events(list(pending_events or []))
        self.log: list[ev.BaseEvent] = []
        self._low_inventory_components: set[str] = set()

    def schedule(self, event: ev.BaseEvent) -> None:
        """Schedule an event for a future simulation time"""
        if not event.id:
            event.id = self.context.next_id("evt")

        self.pending = ev.sort_events([*self.pending, event])

    def _emit(self, event: ev.BaseEvent) -> None:
        """Add an event to the audit log"""
        if not event.id:
            event.id = self.context.next_id("evt")

        self.log.append(event)

    def _due_events(self, upto_hour: float) -> list[ev.BaseEvent]:
        """Remove and return events due by the supplied hour"""
        due = [event for event in self.pending if event.sim_hour <= upto_hour]

        if due:
            self.pending = [
                event for event in self.pending if event.sim_hour > upto_hour
            ]
        return ev.sort_events(due)

    def apply_event(self, event: ev.BaseEvent) -> None:
        """Apply one external event and record it in the audit log."""
        if isinstance(event, ev.MachineFailureEvent):
            self._on_machine_failure(event)
        elif isinstance(event, ev.MachineRepairEvent):
            self._on_machine_repair(event)
        elif isinstance(event, ev.SupplierDelayEvent):
            self._on_supplier_delay(event)
        elif isinstance(event, ev.UrgentOrderEvent):
            self._on_urgent_order(event)

        self._emit(event)

    def _on_machine_failure(
        self,
        event: ev.MachineFailureEvent,
    ) -> None:
        machine = self.state.machines.get(event.machine_id)

        if machine is None:
            return

        machine.status = MachineStatus.DOWN
        machine.down_until_hour = q(
            event.sim_hour + event.duration_hours,
        )

    def _on_machine_repair(
        self,
        event: ev.MachineRepairEvent,
    ) -> None:
        machine = self.state.machines.get(event.machine_id)

        if machine is None:
            return

        machine.status = MachineStatus.IDLE
        machine.down_until_hour = None

    def _on_supplier_delay(
        self,
        event: ev.SupplierDelayEvent,
    ) -> None:
        shipment = self.state.shipments.get(event.shipment_id)

        if shipment is None:
            return

        if shipment.status == ShipmentStatus.RECEIVED:
            return

        shipment.eta_hour = q(
            shipment.eta_hour + event.delay_hours,
        )
        shipment.status = ShipmentStatus.DELAYED

    def _on_urgent_order(
        self,
        event: ev.UrgentOrderEvent,
    ) -> None:
        order_id = event.order_id or self.context.next_id("ORD")

        self.state.orders[order_id] = Order(
            id=order_id,
            product_id=event.product_id,
            quantity=event.quantity,
            due_hour=event.due_hour,
            priority=event.priority,
            late_penalty_per_hour=event.late_penalty_per_hour,
        )

    def _restore_repaired_machines(self) -> None:
        for machine in self.state.machine_list():
            if (
                machine.status == MachineStatus.DOWN
                and machine.down_until_hour is not None
                and self.state.sim_hour >= machine.down_until_hour
            ):
                machine.status = MachineStatus.IDLE
                machine.down_until_hour = None
                self._emit(
                    ev.MachineRepairEvent(
                        sim_hour=self.state.sim_hour,
                        machine_id=machine.id,
                    ),
                )

    def _receive_shipments(self) -> None:
        for shipment in self.state.shipment_list():
            if shipment.status == ShipmentStatus.RECEIVED:
                continue
            if shipment.eta_hour > self.state.sim_hour:
                continue

            item = self.state.inventory.get(shipment.component_id)
            if item is not None:
                item.on_hand = q(item.on_hand + shipment.quantity)

            shipment.status = ShipmentStatus.RECEIVED
            self._emit(
                ev.ShipmentReceivedEvent(
                    sim_hour=self.state.sim_hour,
                    shipment_id=shipment.id,
                    component_id=shipment.component_id,
                    quantity=shipment.quantity,
                ),
            )

    def _buildable_quantity(
        self,
        product: Product,
        wanted: float,
    ) -> float:
        """Return how much requested production the inventory can support."""
        if not product.bom:
            return q(wanted)

        limit = wanted
        for component_id in sorted(product.bom):
            quantity_per_unit = product.bom[component_id]
            if quantity_per_unit <= 0:
                continue

            item = self.state.inventory.get(component_id)
            on_hand = item.on_hand if item is not None else 0.0
            limit = min(limit, on_hand / quantity_per_unit)

        return q(max(0.0, limit))

    def _consume_components(
        self,
        product: Product,
        quantity: float,
    ) -> None:
        for component_id in sorted(product.bom):
            item = self.state.inventory.get(component_id)
            if item is None:
                continue

            consumed = product.bom[component_id] * quantity
            item.on_hand = q(max(0.0, item.on_hand - consumed))

    def _run_production(self, step: float) -> None:
        for machine in self.state.machine_list():
            if not machine.is_available():
                continue

            active_jobs = [
                job
                for job in self.state.jobs_for_machine(machine.id)
                if (
                    job.is_active_at(self.state.sim_hour)
                    and job.produced < job.quantity
                )
            ]
            if not active_jobs:
                machine.status = MachineStatus.IDLE
                continue

            job = active_jobs[0]
            product = self.state.products.get(job.product_id)
            if product is None or not machine.can_produce(job.product_id):
                continue

            effective_step = step
            if machine.current_family != product.family:
                if machine.changeover_target_family != product.family:
                    machine.changeover_target_family = product.family
                    machine.changeover_remaining_hours = q(
                        machine.changeover_minutes / 60,
                    )

                changeover = min(
                    step,
                    machine.changeover_remaining_hours,
                )
                effective_step = q(step - changeover)
                machine.changeover_remaining_hours = q(
                    machine.changeover_remaining_hours - changeover,
                )
                self.state.changeover_hours = q(
                    self.state.changeover_hours + changeover,
                )
                self.state.production_cost = q(
                    self.state.production_cost + changeover * CHANGEOVER_COST_PER_HOUR,
                )

                if machine.changeover_remaining_hours == 0:
                    machine.current_family = product.family
                    machine.changeover_target_family = None

                if effective_step <= 0 or machine.current_family != product.family:
                    machine.status = MachineStatus.RUNNING
                    continue

            wanted = min(
                machine.capacity_per_hour * effective_step,
                job.quantity - job.produced,
            )
            buildable = self._buildable_quantity(product, wanted)
            if buildable <= 0:
                machine.status = MachineStatus.IDLE
                continue

            self._consume_components(product, buildable)
            job.produced = q(job.produced + buildable)
            machine.status = MachineStatus.RUNNING
            self.state.production_cost = q(
                self.state.production_cost + buildable * product.unit_cost,
            )

            order = self.state.orders.get(job.order_id)
            if order is not None and order.is_open():
                order.produced = q(order.produced + buildable)
                order.status = OrderStatus.IN_PROGRESS

            overtime = overtime_overlap(
                self.state.sim_hour - step,
                self.state.sim_hour,
            )
            if overtime > 0 and step > 0:
                worked = q(overtime * (effective_step / step))
                self.state.overtime_hours = q(
                    self.state.overtime_hours + worked,
                )
                self.state.production_cost = q(
                    self.state.production_cost + worked * OVERTIME_COST_PER_HOUR,
                )

    def _settle_orders(self) -> None:
        for order in self.state.order_list():
            if not order.is_open():
                continue

            if order.produced >= order.quantity:
                order.status = OrderStatus.COMPLETE
                order.completed_hour = self.state.sim_hour
                hours_late = q(max(0.0, self.state.sim_hour - order.due_hour))
                if hours_late > 0:
                    self.state.late_penalty_cost = q(
                        self.state.late_penalty_cost
                        + hours_late * order.late_penalty_per_hour,
                    )
                self._emit(
                    ev.OrderCompleteEvent(
                        sim_hour=self.state.sim_hour,
                        order_id=order.id,
                        hours_late=hours_late,
                    ),
                )
                continue

            if self.state.sim_hour <= order.due_hour:
                continue

            already_reported = any(
                isinstance(event, ev.OrderLateEvent) and event.order_id == order.id
                for event in self.log
            )
            if not already_reported:
                self._emit(
                    ev.OrderLateEvent(
                        sim_hour=self.state.sim_hour,
                        order_id=order.id,
                        due_hour=order.due_hour,
                    ),
                )

    def _check_inventory(self) -> None:
        for item in self.state.inventory_list():
            below_threshold = item.on_hand < item.reorder_point
            if (
                below_threshold
                and item.component_id not in self._low_inventory_components
            ):
                self._emit(
                    ev.LowInventoryEvent(
                        sim_hour=self.state.sim_hour,
                        component_id=item.component_id,
                        on_hand=item.on_hand,
                        reorder_point=item.reorder_point,
                    ),
                )
                self._low_inventory_components.add(item.component_id)
            elif not below_threshold:
                self._low_inventory_components.discard(item.component_id)

    def tick(self, step: float | None = None) -> list[ev.BaseEvent]:
        """Advance the simulation by one fixed step."""
        actual_step = self.context.step_hours if step is None else step
        if actual_step <= 0:
            raise ValueError("step must be positive")

        log_start = len(self.log)
        self.state.sim_hour = q(self.state.sim_hour + actual_step)
        for event in self._due_events(self.state.sim_hour):
            self.apply_event(event)

        self._restore_repaired_machines()
        self._receive_shipments()
        self._run_production(actual_step)
        self._settle_orders()
        self._check_inventory()
        return self.log[log_start:]

    def run_until(
        self,
        hour: float,
        step: float | None = None,
    ) -> list[ev.BaseEvent]:
        """Advance in fixed steps until the requested hour."""
        actual_step = self.context.step_hours if step is None else step
        if actual_step <= 0:
            raise ValueError("step must be positive")
        if hour < self.state.sim_hour:
            raise ValueError("cannot run backwards")

        log_start = len(self.log)
        remaining = hour - self.state.sim_hour
        steps = round(remaining / actual_step)
        for _ in range(steps):
            self.tick(actual_step)
        return self.log[log_start:]

    def finalize(self) -> None:
        """Charge final lateness for unfinished orders."""
        for order in self.state.order_list():
            if order.is_open() and self.state.sim_hour > order.due_hour:
                order.status = OrderStatus.LATE
                hours_late = q(self.state.sim_hour - order.due_hour)
                self.state.late_penalty_cost = q(
                    self.state.late_penalty_cost
                    + hours_late * order.late_penalty_per_hour,
                )
