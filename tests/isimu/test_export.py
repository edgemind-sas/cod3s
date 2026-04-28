"""Tests for the CSV/JSON exporters (no PyCATSHOO required)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from cod3s.pycatshoo.isimu.engine import FiredEvent
from cod3s.pycatshoo.isimu.export import (
    export_csv,
    export_json,
    history_to_records,
)


def _stub_trans(name: str, comp: str, source: str, target: str):
    """Stand-in for ``PycTransition`` exposing only ``model_dump``."""
    payload = {
        "cls": "PycTransition",
        "name": name,
        "comp_name": comp,
        "comp_classname": "PycComponent",
        "source": source,
        "target": target,
        "occ_law": {"cls": "DelayOccDistribution", "time": 1.0},
        "is_interruptible": False,
    }
    return SimpleNamespace(model_dump=lambda: payload)


def _sample_history() -> list[FiredEvent]:
    return [
        FiredEvent(
            fired_at=1.0,
            transitions=[
                _stub_trans("fail", "A", "ok", "ko"),
                _stub_trans("fail", "B", "ok", "ko"),
            ],
            vars_before={"A.flag": False},
            vars_after={"A.flag": True},
        ),
        FiredEvent(
            fired_at=3.5,
            transitions=[_stub_trans("repair", "A", "ko", "ok")],
        ),
    ]


def test_history_to_records_flattens_one_row_per_transition() -> None:
    records = history_to_records(_sample_history())
    assert len(records) == 3

    first = records[0]
    assert first["fired_at"] == 1.0
    assert first["event_idx"] == 0
    assert first["trans_idx"] == 0
    assert first["comp_name"] == "A"
    assert first["transition"] == "fail"
    assert first["source"] == "ok"
    assert first["target"] == "ko"
    assert first["occ_law_cls"] == "DelayOccDistribution"
    assert first["is_interruptible"] is False

    last = records[-1]
    assert last["fired_at"] == 3.5
    assert last["event_idx"] == 1
    assert last["trans_idx"] == 0
    assert last["comp_name"] == "A"
    assert last["transition"] == "repair"


def test_export_csv_writes_expected_columns(tmp_path: Path) -> None:
    out = export_csv(_sample_history(), tmp_path / "history.csv")
    assert out.exists()

    df = pd.read_csv(out)
    expected_cols = [
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
    assert list(df.columns) == expected_cols
    assert len(df) == 3
    assert df.iloc[0]["fired_at"] == 1.0
    assert df.iloc[0]["transition"] == "fail"


def test_export_csv_empty_history_produces_header_only(tmp_path: Path) -> None:
    out = export_csv([], tmp_path / "empty.csv")
    df = pd.read_csv(out)
    assert len(df) == 0
    # Header columns are still present so consumers don't choke on empty data.
    assert "fired_at" in df.columns


def test_export_json_roundtrip(tmp_path: Path) -> None:
    out = export_json(_sample_history(), tmp_path / "history.json")
    payload = json.loads(out.read_text())

    assert "history" in payload
    assert len(payload["history"]) == 2

    first = payload["history"][0]
    assert first["fired_at"] == 1.0
    assert len(first["transitions"]) == 2
    assert first["transitions"][0]["name"] == "fail"
    assert first["transitions"][0]["comp_name"] == "A"

    second = payload["history"][1]
    assert second["fired_at"] == 3.5
    assert len(second["transitions"]) == 1


def test_export_json_empty_history(tmp_path: Path) -> None:
    out = export_json([], tmp_path / "empty.json")
    payload = json.loads(out.read_text())
    assert payload == {"history": []}
