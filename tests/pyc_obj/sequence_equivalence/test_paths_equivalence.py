"""Strict equivalence test: ``from_pyc_system`` vs XML round-trip.

For each test system, run **one** Monte Carlo, then exercise both
analysis paths and verify that the minimal sequences are bit-identical
(same signatures, same weights).

The two paths exercise different code:

* **XML round-trip** — ``setResultFileName`` dumps a ``sequences.xml``
  during ``simulate``; we re-parse it via ``ElementTree`` and feed
  the sequences into ``SequenceAnalyser`` with **explicit**
  ``objfm_internal``/``objfm_external`` lists (the user-supplied
  case).
* **from_pyc_system** — pulls the same sequences directly from the
  live ``CSequence`` objects, attaches the system to the analyser,
  and calls ``filter_objfm_cycles()`` with **no arguments**
  (auto-discovery).

If the auto-discovery is correct, the two paths must converge on
the same minimal sequences.
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

import cod3s
from cod3s.pycatshoo.component import ObjFM
from cod3s.pycatshoo.sequence import SeqEvent, Sequence, SequenceAnalyser

sys.path.insert(0, str(Path(__file__).parent))
from _systems import (  # noqa: E402
    build_ccf_order2_internal_system,
    build_ccf_order3_internal_system,
    build_external_rep_indep_system,
    build_mixed_internal_external_system,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_xml_to_sequences(xml_text):
    """Build cod3s ``Sequence`` objects from a ``sequences.xml`` dump."""
    root = ET.fromstring(xml_text)
    sequences = []
    for seq_el in root.findall(".//SEQ"):
        events = []
        for br in seq_el.findall("BR"):
            try:
                t = float(br.get("T") or 0.0)
            except ValueError:
                t = 0.0
            for tr in br.findall("TR"):
                name = tr.get("NAME", "")
                obj, _, attr = name.partition(".")
                events.append(
                    SeqEvent(obj=obj or name, attr=attr or name, time=t, type=None)
                )
        sequences.append(
            Sequence(
                probability=None,
                weight=1,
                end_time=None,
                target_name=seq_el.get("C") or "Normal",
                events=events,
            )
        )
    return sequences


def _explicit_filter_args(system):
    """Collect (objfm_internal, objfm_external) lists by introspecting
    the same way ``_discover_objfm_specs`` would — but used here as the
    *user-supplied* explicit reference so that the test verifies the
    auto-discovery matches a hand-rolled equivalent."""
    objfm_internal = []
    objfm_external = []
    for comp in system.comp.values():
        if not isinstance(comp, ObjFM):
            continue
        if comp.behaviour == "internal":
            objfm_internal.append(comp.name())
        else:
            objfm_external.append(comp.name())
    return objfm_internal, objfm_external


def _path_xml(xml_path, objfm_internal, objfm_external):
    """Path A: XML → ElementTree → analyser + explicit filter args."""
    raws = _parse_xml_to_sequences(xml_path.read_text())
    analyser = SequenceAnalyser(sequences=raws)
    analyser.group_sequences(inplace=True)
    analyser.filter_objfm_cycles(
        objfm_internal=objfm_internal,
        objfm_external=objfm_external,
        inplace=True,
    )
    analyser.compute_minimal_sequences(inplace=True)
    return analyser


def _path_from_system(system):
    """Path B: from_pyc_system + zero-config filter."""
    analyser = SequenceAnalyser.from_pyc_system(system)
    analyser.group_sequences(inplace=True)
    analyser.filter_objfm_cycles(inplace=True)
    analyser.compute_minimal_sequences(inplace=True)
    return analyser


def _signatures(analyser):
    """Aggregate ``{event_signature: total_weight}`` across all
    sequences. Used for set-equality comparison between the two paths
    (their internal ordering may differ)."""
    sigs = {}
    for s in analyser.sequences:
        sig = tuple((ev.obj, ev.attr) for ev in s.events)
        sigs[sig] = sigs.get(sig, 0) + s.weight
    return sigs


# ---------------------------------------------------------------------------
# Fixture: cleanup
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _terminate_session():
    yield
    cod3s.terminate_session()


# ---------------------------------------------------------------------------
# Parametrised equivalence test
# ---------------------------------------------------------------------------


SYSTEM_BUILDERS = [
    pytest.param(build_ccf_order2_internal_system, 1500, 8760.0, id="ccf_o2_internal"),
    pytest.param(build_ccf_order3_internal_system, 1500, 8760.0, id="ccf_o3_internal"),
    pytest.param(build_mixed_internal_external_system, 1500, 8760.0, id="mixed_int_ext"),
    pytest.param(build_external_rep_indep_system, 1500, 500.0, id="external_rep_indep"),
]


@pytest.mark.parametrize("builder,nb_runs,tmax", SYSTEM_BUILDERS)
def test_xml_and_from_pyc_system_yield_identical_minimal_sequences(
    builder, nb_runs, tmax, tmp_path
):
    """Build the system, simulate once, run both analysis paths,
    assert the minimal sequence signatures + weights match exactly."""
    system = builder()
    seq_path = tmp_path / "sequences.xml"
    system.setResultFileName(str(seq_path), False)
    system.setBinSeqFile(False)
    system.simulate({"nb_runs": nb_runs, "seed": 42, "schedule": [float(tmax)]})

    # Path B FIRST — reads live ``CSequence`` objects from C++. Must
    # run before any operation that might mutate the system's
    # internal state (it won't on the analyser side, but ordering is
    # the safest).
    analyser_from_system = _path_from_system(system)

    # Path A — parse the XML written during ``simulate``.
    objfm_internal, objfm_external = _explicit_filter_args(system)
    analyser_from_xml = _path_xml(seq_path, objfm_internal, objfm_external)

    # Total weight conserved on both sides.
    total_xml = sum(s.weight for s in analyser_from_xml.sequences)
    total_sys = sum(s.weight for s in analyser_from_system.sequences)
    assert total_xml == nb_runs, (
        f"XML path lost trajectories: {total_xml} != {nb_runs}"
    )
    assert total_sys == nb_runs, (
        f"from_pyc_system path lost trajectories: {total_sys} != {nb_runs}"
    )

    # Same number of distinct minimal sequences.
    assert len(analyser_from_xml.sequences) == len(analyser_from_system.sequences), (
        f"Distinct minimal count diverges: "
        f"xml={len(analyser_from_xml.sequences)} "
        f"sys={len(analyser_from_system.sequences)}"
    )

    # Same {signature: weight} mapping.
    sigs_xml = _signatures(analyser_from_xml)
    sigs_sys = _signatures(analyser_from_system)
    assert sigs_xml == sigs_sys, (
        f"Minimal signatures differ.\n"
        f"  Only-in-xml: {set(sigs_xml) - set(sigs_sys)}\n"
        f"  Only-in-sys: {set(sigs_sys) - set(sigs_xml)}\n"
        f"  Common-but-weight-differs: {[k for k in sigs_xml if k in sigs_sys and sigs_xml[k] != sigs_sys[k]]}"
    )
