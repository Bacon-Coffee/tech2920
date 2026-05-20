"""Fixed-time pre-timed signal controller (baseline).

Switches every traffic light to a pre-generated static program
(``programID="ft"`` in ``sim/tll_static.add.xml``) at setup time and
then lets SUMO advance the schedule by itself.
"""

from __future__ import annotations

from .base import BaseController


class FixedTimeController(BaseController):
    name = "fixed_time"
    STATIC_PROGRAM_ID = "ft"

    def setup(self, traci_conn, tl_ids):
        super().setup(traci_conn, tl_ids)
        for tl in tl_ids:
            traci_conn.trafficlight.setProgram(tl, self.STATIC_PROGRAM_ID)

    def step(self, sim_time: float) -> None:
        return None
