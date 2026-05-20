"""Generate a static signal program file from the network's actuated logic.

Reads ``sim/grid4x4.net.xml``, collects every ``<tlLogic>`` block and
writes ``sim/tll_static.add.xml`` containing the SAME phase state
strings but with:

  * ``type="static"`` (instead of ``actuated``)
  * ``programID="ft"`` (the FixedTimeController switches to this)
  * fixed phase durations: green=30s, yellow=3s
    (cycle = 2*(30+3) = 66s, matching common textbook baselines)

Run once after the network is generated; the runner does NOT
regenerate this file on every simulation.

Usage:
    python -m runner.build_static_tll
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

GREEN_DURATION = 30
YELLOW_DURATION = 3
STATIC_PROGRAM_ID = "ft"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NET = PROJECT_ROOT / "sim" / "grid4x4.net.xml"
DEFAULT_OUT = PROJECT_ROOT / "sim" / "tll_static.add.xml"


def build_static_tll(net_path: Path, out_path: Path) -> int:
    tree = ET.parse(net_path)
    root = tree.getroot()

    add_root = ET.Element("additional")
    n_tls = 0

    for tl in root.findall("tlLogic"):
        phases = tl.findall("phase")
        if not phases:
            continue
        new_tl = ET.SubElement(
            add_root,
            "tlLogic",
            {
                "id": tl.get("id"),
                "type": "static",
                "programID": STATIC_PROGRAM_ID,
                "offset": "0",
            },
        )
        for idx, phase in enumerate(phases):
            state = phase.get("state")
            duration = GREEN_DURATION if idx % 2 == 0 else YELLOW_DURATION
            ET.SubElement(
                new_tl,
                "phase",
                {"duration": str(duration), "state": state},
            )
        n_tls += 1

    ET.indent(add_root, space="    ")
    out_path.write_bytes(
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(add_root, encoding="utf-8")
    )
    return n_tls


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--net", type=Path, default=DEFAULT_NET)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    n = build_static_tll(args.net, args.out)
    print(f"wrote {n} tlLogic blocks (programID={STATIC_PROGRAM_ID!r}) -> {args.out}")


if __name__ == "__main__":
    main()
