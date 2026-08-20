import pytest
from pydantic import ValidationError

from backend.simulator.models import (
    Machine,
    MachineStatus,
    Product,
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