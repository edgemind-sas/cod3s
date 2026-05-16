# Example: CCF sequence asymmetry

Standalone reproducer for the
`SequenceAnalyser.compute_minimal_sequences` asymmetry bug on a dual-
component CCF system. Open-source, no domain colouring — built with
the standard cod3s API (`PycSystem`, `ObjFMExp` in `internal` mode,
`ObjEvent`, `addTarget`, `simulate`, `SequenceAnalyser`).

## What it does

1. Builds a system of 2 redundant pumps + 1 order-2 CCF failure mode
   (`ObjFMExp`, `behaviour="internal"`, `lambda_1` / `lambda_2`,
   `mu_1` / `mu_2`).
2. Wires an `ObjEvent` target firing when both pumps are simultaneously
   in `working=False`, registered via `system.addTarget(..., "ST")` so
   each Monte Carlo trajectory stops the first time the condition holds.
3. Runs MC, dumps `sequences.xml` via `setResultFileName`.
4. Parses the XML into `cod3s.Sequence` objects, runs the analysis
   twice :
   - with `group_sequences` only — **symmetric output**, the mirror
     ordered pairs `[cc_1, cc_2, target]` and `[cc_2, cc_1, target]`
     come out with the same weight within MC noise (ratio < 1.3×) ;
   - with `group_sequences` + `compute_minimal_sequences` — **broken
     symmetry**, one of the two ordered pairs absorbs the bulk of the
     weight (typical observed ratio 5-10×).
5. Surfaces the symmetry ratio on the console and flags it
   automatically.

## Run

```bash
LD_LIBRARY_PATH=/path/to/libPycatshoo.so/dir \
PYTHONPATH=/path/to/Pycatshoo.so/dir \
    uv run python examples/ccf_sequence_asymmetry/ccf_sequence_asymmetry.py \
        --nb-runs 5000 --tmax 87600 --top 6
```

Flags :

- `--nb-runs N` (default 5000) — MC trajectory count.
- `--seed S` (default 42) — RNG seed.
- `--tmax T` (default 87600 h ≈ 10 years) — simulation horizon.
- `--out DIR` (default `./results-ccf-demo`) — where the `sequences.xml`
  + `pyc_param.xml` get dumped.
- `--top N` (default 10) — how many top sequences to print.
- `--skip-minimal` — only run the group-only pass, skip the bug
  reproduction (useful to confirm symmetry without paying the
  `compute_minimal_sequences` cost on large XMLs).

## Expected console output

```
=== group_sequences ONLY (expected symmetry) ===
  total weight = 5000  (2413 distinct sequences)
  # 1  N=   327  P=0.0654  events=2
       pump_X__def_pump.occ__cc_12 -> system_down.occ
  ...
  # 4  N=    99  P=0.0198  events=3
       pump_X__def_pump.occ__cc_1 -> pump_X__def_pump.occ__cc_2 -> system_down.occ
  # 5  N=    98  P=0.0196  events=3
       pump_X__def_pump.occ__cc_2 -> pump_X__def_pump.occ__cc_1 -> system_down.occ

  Symmetry on ordered pairs cc_1 ↔ cc_2 (weight aggregated) :
    cc_1 then cc_2 : weight 3661
    cc_2 then cc_1 : weight 3667
    asymmetry ratio : 1.00×  (OK (within MC noise))

=== group + compute_minimal_sequences (reproduces the bug) ===
  total weight = 5000  (21 distinct sequences)
  ...
  # 2  N=  1448  P=0.2896  events=3
       pump_X__def_pump.occ__cc_1 -> pump_X__def_pump.occ__cc_2 -> system_down.occ
  # 3  N=   190  P=0.0380  events=3
       pump_X__def_pump.occ__cc_2 -> pump_X__def_pump.occ__cc_1 -> system_down.occ

  Symmetry on ordered pairs cc_1 ↔ cc_2 (weight aggregated) :
    cc_1 then cc_2 : weight 1466
    cc_2 then cc_1 : weight 208
    asymmetry ratio : 7.05×  (SUSPECT — investigate)
```

The asymmetry direction (whether `cc_1→cc_2` or `cc_2→cc_1` rafle the
weight) depends on the post-grouping tie-breaking, which is itself
sensitive to the dict iteration order in `group_sequences`. Either way
the asymmetry ratio crossing well beyond MC noise is the bug signature.

## Root cause

`SequenceAnalyser.compute_minimal_sequences` is a **greedy,
order-dependent** algorithm : it sorts sequences by ascending length,
pops the shortest, and absorbs into it the weight of *every* longer
sequence that contains it as an ordered sub-sequence, removing those
longer sequences from the pool. Longer trajectories that are
sub-sequence-compatible with **both** mirror ordered pairs (e.g. a
trajectory that has `cc_1 → rep_cc_1 → cc_2 → cc_1 → cc_2 → top`)
end up attributed to whichever short sequence is processed first —
typically the one that appears first in the post-grouping list.

## Fix — `SequenceAnalyser.filter_objfm_cycles`

The asymmetry comes from raw traces that contain unrelated occ/rep
cycles before the top event. A failure that gets repaired before the
top event does not contribute to the sequence leading there, but it
makes the trace longer and harder to minimise. The cure is to strip
those cycles before running `compute_minimal_sequences`:

```python
analyser.filter_objfm_cycles(
    objfm_internal=["pump_X__def_pump"],  # ObjFM in internal mode
    inplace=True,
)
analyser.compute_minimal_sequences(inplace=True)
```

`filter_objfm_cycles` handles both ObjFM modes:

* **internal** — drops paired `{fm}.occ__<suffix>` /
  `{fm}.rep__<suffix>` events on the ObjFM (suffix-aware, so any
  user-customised `trans_name_prefix` works).
* **external / external_rep_indep** — pass
  `objfm_external={fm_name: [target_names]}` instead. The helper drops
  every event whose `obj == fm_name` (the ObjFM only acts as a sync
  mechanism in external modes) and filters paired `{target}.occ` /
  `{target}.rep` events on each target.

`failure_state` / `repair_state` arguments cover non-default state
names on the ObjFM. Single-target ObjFM (no `__cc_X` suffix) is handled
transparently.

The third console section of this demo runs that pipeline and confirms
the asymmetry collapses below MC noise (typical ratio ≈ 1.1× on 5000
runs).

## See also

- `cod3s/pycatshoo/sequence.py::SequenceAnalyser.filter_objfm_cycles` — the recommended pre-processing step before `compute_minimal_sequences`.
- `cod3s/pycatshoo/sequence.py::Sequence.rm_events_by_obj` — drop all events from a given component (used internally for ObjFM in external mode).
- `cod3s/pycatshoo/sequence.py::compute_minimal_sequences` — the greedy order-dependent algorithm; safe to call after `filter_objfm_cycles`.
- `cod3s/pycatshoo/sequence.py::Sequence.is_included` and `SequenceAnalyser.group_sequences` — the sane building blocks.
- For the original platform reproducer (RATP FMD-IFQ study, 21 MB
  `sequences.xml`) cf. `/tmp/cod3s-debug/ratp-fmd-ifq/` on the host.
