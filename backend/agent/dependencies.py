"""Dependencies available during an agent investigation"""

from dataclasses import dataclass

from backend.simulator.state import FactoryState


@dataclass(frozen=True)
class AgentDependencies:
    state: FactoryState

    @classmethod
    def from_state(cls, state: FactoryState) -> "AgentDependencies":
        return cls(state=state.clone())
