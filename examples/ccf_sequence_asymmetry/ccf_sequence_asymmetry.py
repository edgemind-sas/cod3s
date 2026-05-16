"""Minimal reproducer for the ``compute_minimal_sequences`` asymmetry bug.

This standalone example exercises the standard cod3s pipeline
(``ObjFMExp`` in ``internal`` behaviour + a 2-component CCF group +
``SequenceAnalyser.group_sequences`` ± ``compute_minimal_sequences``)
on a deliberately symmetric system, and surfaces an artificial
asymmetry between mirror ordered sequences when
``compute_minimal_sequences`` is applied.

System under test
-----------------

Two redundant equipment items (``pump_1``, ``pump_2``) share a single
order-2 CCF failure mode ``def_pump`` :

- ``ObjFMExp``, ``behaviour="internal"`` (same as the platform's
  factory default — cf. ``cli/CLAUDE.md`` § Simulation et quantification)
- ``failure_param = [(lambda_1,), (lambda_2,)]`` → 2^N - 1 = 3
  occurrence transitions are generated: ``cc_1`` and ``cc_2``
  (order 1, governed by ``lambda_1``) and ``cc_12`` (order 2,
  governed by ``lambda_2``).
- ``repair_param = [(mu_1,), (mu_2,)]`` → 3 mirror repair transitions
  (``rep__cc_1``, ``rep__cc_2``, ``rep__cc_12``).

The parameters are taken from the RATP FMD-IFQ study so the numbers
ring true to a reliability analyst, but the components are anonymous
pumps — no domain-specific code or labels.

Expected vs observed
--------------------

The two ordered sequences ``cc_1 → cc_2 → both_failed`` and
``cc_2 → cc_1 → both_failed`` must have *similar* counts at Monte
Carlo convergence : both are governed by the same ``lambda_1``, and
the temporal order of two independent order-1 failures is equiprobable.

``group_sequences`` alone preserves that symmetry (ratio ≈ 1× within
MC noise). ``group + compute_minimal_sequences`` breaks it (observed
ratio up to ~8× on a 10 000-run sample). The bug appears to come from
``compute_minimal_sequences``' greedy, order-dependent absorption of
longer sequences into the first shorter sequence that matches as an
ordered sub-sequence.

This script reproduces both behaviours in one run so the bug can be
investigated against a fully open-source, model-free system.

Run
---

::

    LD_LIBRARY_PATH=<dir containing libPycatshoo.so> \\
    PYTHONPATH=<dir containing Pycatshoo.so> \\
        uv run python examples/ccf_sequence_asymmetry/ccf_sequence_asymmetry.py

    # smaller / faster (just to smoke-test)
    ... --nb-runs 1000 --tmax 8760

What you should see in the console
----------------------------------

::

    === group_sequences ONLY (expected symmetry) ===
       cc_1 → cc_2 → ... weight   ≈   cc_2 → cc_1 → ... weight     (ratio < 1.3)

    === group + compute_minimal_sequences (reproduces the bug) ===
       cc_1 → cc_2 → ... weight   <<   cc_2 → cc_1 → ... weight     (ratio > 3)

A persistent asymmetry > a few sigma on these mirror pairs is the
canonical bug signature — fix ``compute_minimal_sequences`` and rerun
to confirm the asymmetry collapses below the MC noise floor.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import Pycatshoo as Pyc

import cod3s


# ---------------------------------------------------------------------------
# Component class — generic pump with a single ``working`` boolean state.
# ---------------------------------------------------------------------------


class Pump(cod3s.PycComponent):
    """Redundant equipment item monitored by the CCF ObjFM.

    Carries a single boolean ``working`` variable that the
    ``failure_effects`` block flips to ``False`` on occurrence and the
    automaton's repair state resets to ``True`` on repair.
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


# ---------------------------------------------------------------------------
# System factory — 2 redundant pumps + 1 order-2 CCF failure mode (internal).
# ---------------------------------------------------------------------------

# Parameters reflect the RATP FMD-IFQ "def_fct_automate" CCF group on a
# duplicated PLC. Translated to per-hour exponential rates :
#   lambda_1 → 2.79e-04 /h  (MTBF order 1 ≈ 3580 h)
#   lambda_2 → 4.19e-05 /h  (MTBF order 2 ≈ 23900 h)
#   mu_1     → 6.72e-03 /h  (MTTR order 1 ≈ 149 h)
#   mu_2     → 3.76e-01 /h  (MTTR order 2 ≈ 2.7 h)
LAMBDA_1 = 2.79e-04
LAMBDA_2 = 4.19e-05
MU_1 = 6.72e-03
MU_2 = 3.76e-01


def build_system(system_name: str = "CCF_Sequence_Asymmetry_Demo") -> cod3s.PycSystem:
    """Construct the dual-pump CCF system in default ``internal`` mode.

    Wires :

    - 2 ``Pump`` components with a single ``working`` boolean.
    - 1 ``ObjFMExp`` failure mode with the order-2 CCF group :
      ``cc_1`` and ``cc_2`` (order 1, rate ``lambda_1``) and ``cc_12``
      (order 2, rate ``lambda_2``). Repair transitions mirror the
      same combinatorics.
    - 1 ``ObjEvent`` ``system_down`` that fires (state ``occ``) when
      **both** pumps are simultaneously in ``working=False``. Used as
      the simulation target — registered via ``system.addTarget`` so
      every Monte Carlo trajectory stops the first time the event
      occurs (same pattern as the platform's ``run_study`` pipeline).
    """
    system = cod3s.PycSystem(name=system_name)
    for n in ("pump_1", "pump_2"):
        system.add_component(name=n, cls="Pump")
    system.add_component(
        cls="ObjFMExp",
        fm_name="def_pump",
        targets=["pump_1", "pump_2"],
        behaviour="internal",
        failure_effects={"working": False},
        failure_param=[(LAMBDA_1,), (LAMBDA_2,)],
        repair_param=[(MU_1,), (MU_2,)],
    )

    # Single-AND condition: pump_1.working == False AND pump_2.working == False.
    # ``ObjEvent.cond`` accepts the canonical OR-of-AND nested-list
    # form used by the platform's study translator output. Each leaf
    # carries (obj, attr) separately — the attribute resolver doesn't
    # accept the dotted ``"pump_1.working"`` shortcut directly.
    system.add_component(
        cls="ObjEvent",
        name="system_down",
        cond=[[
            {"obj": "pump_1", "attr": "working", "ope": "==", "value": False},
            {"obj": "pump_2", "attr": "working", "ope": "==", "value": False},
        ]],
    )

    # Stop each MC trajectory the first time ``system_down.occ`` flips
    # to True ("ST" = stop on True). Without an early-stop target the
    # raw sequences.xml would contain full TMAX trajectories with
    # tens of transitions each, and group_sequences would never
    # collapse anything — defeating the bug reproduction.
    system.addTarget("system_down_target", "system_down.occ", "ST")
    return system


# ---------------------------------------------------------------------------
# Simulation driver — dump sequences.xml via setResultFileName.
# ---------------------------------------------------------------------------


def simulate(system: cod3s.PycSystem, *, nb_runs: int, seed: int,
             tmax: float, results_dir: Path) -> Path:
    """Run Monte Carlo and dump ``sequences.xml`` into ``results_dir``.

    Uses ``setResultFileName`` (raw <PY_RES> dump, 1 SEQ per trajectory)
    + ``monitorTransition("#.*")`` so every ObjFM occ/rep transition is
    captured. No ``addTarget`` is registered : trajectories run for the
    full TMAX and the full transition stream is available for analysis.
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    seq_path = results_dir / "sequences.xml"

    if hasattr(system, "setResultFileName"):
        system.setResultFileName(str(seq_path), False)
    if hasattr(system, "setBinSeqFile"):
        system.setBinSeqFile(False)
    system.monitorTransition("#.*")

    print(f"  nb_runs={nb_runs}  seed={seed}  tmax={tmax}")
    t0 = time.perf_counter()
    system.simulate({"nb_runs": nb_runs, "seed": seed, "schedule": [float(tmax)]})
    print(f"  simulate : {time.perf_counter() - t0:.2f} s")
    print(f"  sequences.xml : {seq_path} ({seq_path.stat().st_size / 1e6:.2f} MB)")
    return seq_path


# ---------------------------------------------------------------------------
# Analysis — parse sequences.xml, group, optionally minimal, top + symmetry.
# ---------------------------------------------------------------------------


def _build_cod3s_sequences(xml_text: str) -> list:
    """Lift raw <PY_RES> trajectories into cod3s Sequence objects."""
    from cod3s.pycatshoo.sequence import SeqEvent, Sequence

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
                events.append(SeqEvent(obj=obj or name, attr=attr or name,
                                       time=t, type=None))
        sequences.append(Sequence(probability=None, weight=1, end_time=None,
                                  target_name=seq_el.get("C"), events=events))
    return sequences


def _print_top(seqs, top: int) -> None:
    seqs_sorted = sorted(seqs, key=lambda s: s.weight, reverse=True)
    total_w = sum(s.weight for s in seqs_sorted)
    print(f"  total weight = {total_w}  ({len(seqs_sorted)} distinct sequences)")
    for i, s in enumerate(seqs_sorted[:top], start=1):
        sig = " -> ".join(f"{ev.obj}.{ev.attr}" for ev in s.events)
        proba = (s.probability if s.probability is not None
                 else (s.weight / total_w if total_w else 0.0))
        print(f"  #{i:2d}  N={s.weight:6d}  P={proba:.4f}  events={len(s.events)}")
        print(f"       {sig[:140]}")


def _symmetry_check(seqs, a: str, b: str) -> tuple[int, int]:
    """Aggregate weights of signatures containing (a then b) vs (b then a)
    on the same parent obj. Returns (weight_ab, weight_ba)."""
    suf_a, suf_b = f"__{a}", f"__{b}"

    def matches(events, first: str, second: str) -> bool:
        for i, ev in enumerate(events):
            if not ev.attr.endswith(first):
                continue
            for j in range(i + 1, len(events)):
                if events[j].attr.endswith(second) and events[j].obj == ev.obj:
                    return True
        return False

    w_ab = sum(s.weight for s in seqs if matches(s.events, suf_a, suf_b))
    w_ba = sum(s.weight for s in seqs if matches(s.events, suf_b, suf_a))
    return w_ab, w_ba


def analyse(
    seq_path: Path, *, minimal: bool, filter_occ_rep: bool = False, top: int = 10
) -> None:
    from cod3s.pycatshoo.sequence import SequenceAnalyser

    xml_text = seq_path.read_text()
    raw = _build_cod3s_sequences(xml_text)
    print(f"  raw trajectories : {len(raw)}")

    analyser = SequenceAnalyser(sequences=raw)

    if filter_occ_rep:
        # Drop the (occ__cc_k, rep__cc_k) pairs introduced by the
        # internal-mode CCF ObjFM ``pump_X__def_pump`` — a fault that
        # has been repaired before the top event carries no information
        # about the sequence leading to the event. ``filter_objfm_cycles``
        # is the high-level helper that handles both internal-mode
        # (paired occ/rep on the ObjFM) and external-mode (drop ObjFM
        # events, filter occ/rep pairs on the targets) automatically.
        t0 = time.perf_counter()
        analyser.filter_objfm_cycles(
            objfm_internal=["pump_X__def_pump"],
            inplace=True,
        )
        print(
            f"  filter_objfm_cycles (internal mode) : "
            f"{time.perf_counter() - t0:.2f} s "
            f"→ {len(analyser.sequences)} signatures"
        )
    else:
        t0 = time.perf_counter()
        analyser.group_sequences(inplace=True)
        print(
            f"  group_sequences : {time.perf_counter() - t0:.2f} s "
            f"→ {len(analyser.sequences)} signatures"
        )

    if minimal:
        t0 = time.perf_counter()
        analyser.compute_minimal_sequences(inplace=True)
        print(f"  compute_minimal_sequences : {time.perf_counter() - t0:.2f} s "
              f"→ {len(analyser.sequences)} minimal sequences")

    print()
    _print_top(analyser.sequences, top=top)

    w_ab, w_ba = _symmetry_check(analyser.sequences, "cc_1", "cc_2")
    if w_ab and w_ba:
        ratio = max(w_ab, w_ba) / min(w_ab, w_ba)
        verdict = "OK (within MC noise)" if ratio < 1.3 else "SUSPECT — investigate"
    else:
        ratio = float("nan")
        verdict = "no data"
    print()
    print(f"  Symmetry on ordered pairs cc_1 ↔ cc_2 (weight aggregated) :")
    print(f"    cc_1 then cc_2 : weight {w_ab}")
    print(f"    cc_2 then cc_1 : weight {w_ba}")
    print(f"    asymmetry ratio : {ratio:.2f}×  ({verdict})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--nb-runs", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tmax", type=float, default=87600.0,
                        help="simulation horizon (default 87600 h ≈ 10 years)")
    parser.add_argument("--out", type=Path, default=Path("./results-ccf-demo"))
    parser.add_argument("--skip-minimal", action="store_true",
                        help="only run the group-only pass (no bug repro)")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    print("=== Build system ===")
    system = build_system()
    print(f"  components : {sorted(system.comp.keys())}")

    print()
    print("=== Simulate ===")
    seq_path = simulate(system, nb_runs=args.nb_runs, seed=args.seed,
                        tmax=args.tmax, results_dir=args.out)

    print()
    print("=== group_sequences ONLY (expected symmetry) ===")
    analyse(seq_path, minimal=False, top=args.top)

    if not args.skip_minimal:
        print()
        print("=== group + compute_minimal_sequences (reproduces the bug) ===")
        analyse(seq_path, minimal=True, top=args.top)

        print()
        print(
            "=== filter occ↔rep + group + compute_minimal_sequences "
            "(explicit, post-mortem from XML) ==="
        )
        analyse(seq_path, minimal=True, filter_occ_rep=True, top=args.top)

        print()
        print(
            "=== from_pyc_system + filter_objfm_cycles() "
            "(auto-discover via attached system) ==="
        )
        analyse_via_pyc_system(system, top=args.top)

    return 0


def analyse_via_pyc_system(system: "cod3s.PycSystem", top: int = 10) -> None:
    """Alternate analysis path that bypasses the XML round-trip and the
    explicit ``objfm_internal=[...]`` argument.

    With the system still alive in-process, ``SequenceAnalyser.from_pyc_system``
    reads the trajectories directly from PyCATSHOO's ``CSequence``
    objects (no XML write/read/parse overhead) AND attaches the system
    to the analyser so ``filter_objfm_cycles`` can auto-discover the
    ObjFM via introspection — no need to remember the ObjFM's
    ``target_name__fm_name`` mangling.
    """
    from cod3s.pycatshoo.sequence import SequenceAnalyser

    t0 = time.perf_counter()
    analyser = SequenceAnalyser.from_pyc_system(system)
    print(f"  from_pyc_system : {time.perf_counter() - t0:.2f} s "
          f"→ {len(analyser.sequences)} raw trajectories")

    t0 = time.perf_counter()
    analyser.filter_objfm_cycles(inplace=True)  # ← zero config
    print(f"  filter_objfm_cycles (auto-discover) : "
          f"{time.perf_counter() - t0:.2f} s "
          f"→ {len(analyser.sequences)} signatures")

    t0 = time.perf_counter()
    analyser.compute_minimal_sequences(inplace=True)
    print(f"  compute_minimal_sequences : "
          f"{time.perf_counter() - t0:.2f} s "
          f"→ {len(analyser.sequences)} minimal sequences")

    print()
    _print_top(analyser.sequences, top=top)
    w_ab, w_ba = _symmetry_check(analyser.sequences, "cc_1", "cc_2")
    if w_ab and w_ba:
        ratio = max(w_ab, w_ba) / min(w_ab, w_ba)
        verdict = "OK (within MC noise)" if ratio < 1.3 else "SUSPECT — investigate"
    else:
        ratio = float("nan")
        verdict = "no data"
    print()
    print(f"  Symmetry on ordered pairs cc_1 ↔ cc_2 (weight aggregated) :")
    print(f"    cc_1 then cc_2 : weight {w_ab}")
    print(f"    cc_2 then cc_1 : weight {w_ba}")
    print(f"    asymmetry ratio : {ratio:.2f}×  ({verdict})")


if __name__ == "__main__":
    sys.exit(main())
