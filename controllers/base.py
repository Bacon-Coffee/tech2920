"""Abstract base class for all traffic signal controllers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class BaseController(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self._traci = None
        self._tl_ids: List[str] = []

    def setup(self, traci_conn, tl_ids: List[str]) -> None:
        self._traci = traci_conn
        self._tl_ids = list(tl_ids)

    @abstractmethod
    def step(self, sim_time: float) -> None:
        """Called once per simulation second after traci.simulationStep."""

    def teardown(self) -> None:
        return None
