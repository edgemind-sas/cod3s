"""Export the interactive timeline to CSV / JSON.

The timeline is owned by :class:`ISimuEngine` (a list of :class:`FiredEvent`).
This module turns it into long-format files for downstream analysis. The CSV
schema matches the spirit of ``SequenceAnalyser.to_df_long`` in
``cod3s/pycatshoo/sequence.py:1054`` — one row per fired transition, with the
real firing time captured at step time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from cod3s.pycatshoo.isimu.engine import FiredEvent


def history_to_records(history: Iterable[FiredEvent]) -> List[dict]:
    """Flatten the timeline into one row per fired transition."""
    rows: List[dict] = []
    for event_idx, evt in enumerate(history):
        for trans_idx, trans in enumerate(evt.transitions):
            dump = trans.model_dump() if hasattr(trans, "model_dump") else {}
            rows.append(
                {
                    "fired_at": evt.fired_at,
                    "event_idx": event_idx,
                    "trans_idx": trans_idx,
                    "comp_name": dump.get("comp_name"),
                    "comp_classname": dump.get("comp_classname"),
                    "transition": dump.get("name"),
                    "source": dump.get("source"),
                    "target": dump.get("target"),
                    "occ_law_cls": (dump.get("occ_law") or {}).get("cls"),
                    "is_interruptible": dump.get("is_interruptible"),
                }
            )
    return rows


def export_csv(history: Iterable[FiredEvent], path: Path) -> Path:
    """Write the timeline to ``path`` as CSV. Returns ``path`` for chaining.

    An empty history produces a header-only CSV instead of an empty file so
    downstream consumers don't need a special case.
    """
    path = Path(path)
    rows = history_to_records(history)
    columns = [
        "fired_at",
        "event_idx",
        "trans_idx",
        "comp_name",
        "comp_classname",
        "transition",
        "source",
        "target",
        "occ_law_cls",
        "is_interruptible",
    ]
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
    return path


def export_json(history: Iterable[FiredEvent], path: Path) -> Path:
    """Write the timeline to ``path`` as JSON. Returns ``path`` for chaining."""
    path = Path(path)
    payload = {
        "history": [
            {
                "fired_at": evt.fired_at,
                "transitions": [
                    trans.model_dump() if hasattr(trans, "model_dump") else repr(trans)
                    for trans in evt.transitions
                ],
            }
            for evt in history
        ],
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path
