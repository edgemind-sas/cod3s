"""Benchmark + profile the two sequence-analysis paths.

Two analysis paths compared, side by side, on a chosen test system:

* **xml**         — ``simulate`` writes ``sequences.xml`` via
                    ``setResultFileName``; the path reads the file
                    back with ``ElementTree`` and feeds the sequences
                    into ``SequenceAnalyser`` with explicit
                    ``objfm_internal`` / ``objfm_external`` lists.

* **from_system** — ``SequenceAnalyser.from_pyc_system(system)`` reads
                    the live ``CSequence`` objects directly and the
                    auto-discovery of ObjFM via the attached system is
                    used in ``filter_objfm_cycles()``.

Two outputs:

* a **timing table** with per-stage wall clock (simulate, ingest,
  group, filter, minimal) for each path, across multiple ``nb_runs``;
* a **cProfile dump** sorted by cumulative time for each path so
  hotspots can be inspected.

Usage::

    .venv/bin/python examples/bench_sequence_paths/bench_paths.py \\
        --system ccf_o2 --runs 5000

Available systems: ``ccf_o2``, ``ccf_o3``, ``mixed``, ``ext_rep_indep``.
Pass ``--runs N1 N2 ...`` to run a sweep.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

# Re-use the test systems so the bench reflects what the test suite
# already validates for equivalence.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "pyc_obj" / "sequence_equivalence"))
from _systems import (  # noqa: E402
    build_ccf_order2_internal_system,
    build_ccf_order3_internal_system,
    build_mixed_internal_external_system,
    build_external_rep_indep_system,
)

import cod3s
from cod3s.pycatshoo.component import ObjFM
from cod3s.pycatshoo.sequence import SeqEvent, Sequence, SequenceAnalyser


SYSTEMS = {
    "ccf_o2": build_ccf_order2_internal_system,
    "ccf_o3": build_ccf_order3_internal_system,
    "mixed": build_mixed_internal_external_system,
    "ext_rep_indep": build_external_rep_indep_system,
}


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _parse_xml_to_sequences(xml_text):
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
    internal, external = [], []
    for comp in system.comp.values():
        if not isinstance(comp, ObjFM):
            continue
        if comp.behaviour == "internal":
            internal.append(comp.name())
        else:
            external.append(comp.name())
    return internal, external


def _bench_xml_path(system, xml_path):
    """Per-stage timings for the XML path."""
    timings = {}

    t0 = time.perf_counter()
    xml_text = xml_path.read_text()
    timings["read_xml"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    raws = _parse_xml_to_sequences(xml_text)
    timings["parse_xml"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    analyser = SequenceAnalyser(sequences=raws)
    analyser.group_sequences(inplace=True)
    timings["group"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    objfm_internal, objfm_external = _explicit_filter_args(system)
    analyser.filter_objfm_cycles(
        objfm_internal=objfm_internal,
        objfm_external=objfm_external,
        inplace=True,
    )
    timings["filter"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    analyser.compute_minimal_sequences(inplace=True)
    timings["minimal"] = time.perf_counter() - t0

    timings["total"] = sum(timings.values())
    return timings, analyser


def _bench_from_system_path(system):
    """Per-stage timings for the from_pyc_system path."""
    timings = {}

    t0 = time.perf_counter()
    analyser = SequenceAnalyser.from_pyc_system(system)
    timings["from_pyc_system"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    analyser.group_sequences(inplace=True)
    timings["group"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    analyser.filter_objfm_cycles(inplace=True)  # auto
    timings["filter"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    analyser.compute_minimal_sequences(inplace=True)
    timings["minimal"] = time.perf_counter() - t0

    timings["total"] = sum(timings.values())
    return timings, analyser


# ---------------------------------------------------------------------------
# Profiling
# ---------------------------------------------------------------------------


def _profile_xml_path(system, xml_path, top=25):
    objfm_internal, objfm_external = _explicit_filter_args(system)
    pr = cProfile.Profile()
    pr.enable()
    raws = _parse_xml_to_sequences(xml_path.read_text())
    analyser = SequenceAnalyser(sequences=raws)
    analyser.group_sequences(inplace=True)
    analyser.filter_objfm_cycles(
        objfm_internal=objfm_internal,
        objfm_external=objfm_external,
        inplace=True,
    )
    analyser.compute_minimal_sequences(inplace=True)
    pr.disable()
    return _format_pstats(pr, top), analyser


def _profile_from_system_path(system, top=25):
    pr = cProfile.Profile()
    pr.enable()
    analyser = SequenceAnalyser.from_pyc_system(system)
    analyser.group_sequences(inplace=True)
    analyser.filter_objfm_cycles(inplace=True)
    analyser.compute_minimal_sequences(inplace=True)
    pr.disable()
    return _format_pstats(pr, top), analyser


def _format_pstats(pr, top):
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(top)
    return s.getvalue()


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _simulate(system, nb_runs, seed, tmax, results_dir):
    seq_path = results_dir / "sequences.xml"
    system.setResultFileName(str(seq_path), False)
    system.setBinSeqFile(False)
    t0 = time.perf_counter()
    system.simulate({"nb_runs": nb_runs, "seed": seed, "schedule": [float(tmax)]})
    simulate_s = time.perf_counter() - t0
    return seq_path, simulate_s


def _print_timings_row(label, t):
    """Print a single row of the timings table."""
    keys = [k for k in t if k != "total"]
    cells = "  ".join(f"{k}={t[k]*1e3:7.1f}ms" for k in keys)
    print(f"  {label:<16}  {cells}    total={t['total']*1e3:8.1f}ms")


def _compare_sequences(a, b):
    sigs_a = {tuple((e.obj, e.attr) for e in s.events): s.weight for s in a.sequences}
    sigs_b = {tuple((e.obj, e.attr) for e in s.events): s.weight for s in b.sequences}
    return sigs_a == sigs_b


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--system", choices=list(SYSTEMS), default="ccf_o2",
                        help="Test system to bench (default: ccf_o2)")
    parser.add_argument("--runs", type=int, nargs="+", default=[1000, 5000, 20000],
                        help="One or more nb_runs values to sweep over")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tmax", type=float, default=8760.0,
                        help="Simulation horizon (default 8760 h = 1 year)")
    parser.add_argument("--profile", action="store_true",
                        help="Run a single cProfile dump per path on the largest --runs")
    parser.add_argument("--profile-top", type=int, default=25)
    parser.add_argument("--out", type=Path, default=Path("./bench-results"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    builder = SYSTEMS[args.system]
    print(f"=== System: {args.system} ===")
    print(f"  tmax: {args.tmax}  seed: {args.seed}\n")

    # -------------------------------------------------------------------
    # Sweep over nb_runs
    # -------------------------------------------------------------------
    print(f"{'='*78}\nTiming sweep\n{'='*78}\n")
    for nb_runs in args.runs:
        print(f"--- nb_runs={nb_runs} ---")
        system = builder()
        seq_path, simulate_s = _simulate(system, nb_runs, args.seed, args.tmax, args.out)
        print(f"  simulate          {simulate_s*1e3:7.1f}ms  "
              f"({(seq_path.stat().st_size / 1e6):.2f} MB XML written)")

        # Run path B FIRST (live CSequence objects).
        t_sys, an_sys = _bench_from_system_path(system)
        _print_timings_row("from_pyc_system", t_sys)

        # Then path A.
        t_xml, an_xml = _bench_xml_path(system, seq_path)
        _print_timings_row("xml", t_xml)

        # Equivalence
        ok = _compare_sequences(an_xml, an_sys)
        print(f"  signatures match? {'✓' if ok else '✗ DIVERGES'}")
        print()

        cod3s.terminate_session()

    # -------------------------------------------------------------------
    # Profile (single run on largest --runs)
    # -------------------------------------------------------------------
    if args.profile:
        nb_runs = max(args.runs)
        print(f"{'='*78}\ncProfile (nb_runs={nb_runs}, top={args.profile_top})\n{'='*78}\n")

        system = builder()
        seq_path, simulate_s = _simulate(system, nb_runs, args.seed, args.tmax, args.out)
        print(f"  simulate ({nb_runs} runs)  {simulate_s*1e3:.1f}ms\n")

        # Path B
        print(f"--- from_pyc_system path ---")
        prof_sys, _ = _profile_from_system_path(system, top=args.profile_top)
        print(prof_sys)

        # Path A
        print(f"--- xml path ---")
        prof_xml, _ = _profile_xml_path(system, seq_path, top=args.profile_top)
        print(prof_xml)

        cod3s.terminate_session()

    return 0


if __name__ == "__main__":
    sys.exit(main())
