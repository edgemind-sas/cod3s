# Sequence analysis

Once a Monte-Carlo simulation has run, the sequences of events that led
to each "top event" carry the **safety story** of the simulated system.
COD3S exposes those sequences as first-class objects you can group,
filter, and reduce to **minimal sequences** — the typical input to a
reliability analyst's diagnosis ("which combinations of failures
actually cause the top event, and how often?").

This page documents the data model, the two ways to ingest the
sequences after a simulation, and the canonical analysis pipeline
including the *non-trivial* prerequisite — filtering ObjFM occ/rep
cycles — without which the minimal-sequence algorithm produces biased
results.

## Data model

The analysis layer lives in `cod3s.pycatshoo.sequence` and revolves
around three classes:

| Class | Role |
|---|---|
| `SeqEvent` | One atomic event in a trace — a transition fired on a component. Carries `obj` (component name), `attr` (transition name), `time` (simulation time), `type` (event class). |
| `Sequence` | An ordered list of `SeqEvent` plus metadata — `weight` (how many trajectories matched this signature after grouping), `probability` (weight / total weight), `end_time`, `target_name` (which top event this trajectory reached). |
| `SequenceAnalyser` | A container of `Sequence` objects. All pipeline methods live here: ingestion, grouping, filtering, minimisation. Optionally carries a reference to the originating `PycSystem` for auto-discovery (see below). |

`SeqEvent.name` is a derived property returning `"{obj}.{attr}"`,
which is the form you'll see in printed traces and in pattern-based
filters.

## Two ingestion paths

After `system.simulate(...)` you have two ways to construct the
`SequenceAnalyser`. **They produce equivalent results** (verified by
`tests/pyc_obj/sequence_equivalence/`), but with very different
ergonomics and performance characteristics.

### Path A — `SequenceAnalyser.from_pyc_system(system)` *(recommended)*

Reads the live `CSequence` objects directly from the PyCATSHOO C++
backend. The system reference is **stored on the analyser** so
subsequent methods (in particular `filter_objfm_cycles`) can
introspect the ObjFM topology automatically.

```python
analyser = SequenceAnalyser.from_pyc_system(system)
analyser.group_sequences(inplace=True)
analyser.filter_objfm_cycles(inplace=True)        # ← zero-config
analyser.compute_minimal_sequences(inplace=True)
```

**Pros**

* No XML write/read/parse — typically ~2× faster than path B.
* Auto-discovery of ObjFM names + modes + custom state names.
* The system is alive and inspectable for any subsequent diagnosis.

**Cons**

* Requires the simulation to still be in-process (no
  `cod3s.terminate_session()` since `simulate()`).
* Does not survive a Python process boundary.

### Path B — XML round-trip *(post-mortem)*

Have PyCATSHOO write `sequences.xml` during the simulation, then parse
that file. The analyser does not know the system.

```python
system.setResultFileName("sequences.xml", False)
system.setBinSeqFile(False)
system.monitorTransition("#.*")
system.simulate(...)

# Later, in another process or after terminate_session():
analyser = SequenceAnalyser(sequences=parse_my_xml("sequences.xml"))
analyser.group_sequences(inplace=True)
analyser.filter_objfm_cycles(
    objfm_internal=["pump_X__pump_def"],         # explicit lists
    objfm_external=["sensor_1__sensor_def", "sensor_2__sensor_def"],
    inplace=True,
)
analyser.compute_minimal_sequences(inplace=True)
```

**Pros**

* Survives process boundaries — re-analyse historical runs without
  re-simulating.
* Works without `cod3s` installed on the analysing host (only requires
  the XML).

**Cons**

* Slower (~2×) due to XML parsing and Pydantic re-construction.
* User must supply the ObjFM names explicitly — no introspection.

### Performance comparison

Measured on `tests/pyc_obj/sequence_equivalence/_systems.py:build_ccf_order2_internal_system`
(2 pumps + 1 CCF order-2 internal-mode ObjFM, top event = both
pumps down), seed=42, tmax=8760 h.

| `nb_runs` | `from_pyc_system` total | XML total | Ratio |
|---:|---:|---:|---:|
| 1 000 | 75 ms | 140 ms | 1.86× |
| 5 000 | 237 ms | 595 ms | 2.51× |
| 20 000 | 1 333 ms | 2 514 ms | 1.89× |
| 50 000 | 2 842 ms | 5 677 ms | 2.00× |

Both paths scale linearly with `nb_runs`. Run the bench yourself with
`examples/bench_sequence_paths/bench_paths.py`.

## The canonical analysis pipeline

Whichever ingestion path you took, the next three steps are the same
and should be applied **in this order**:

```
   ingestion → group_sequences → filter_objfm_cycles → compute_minimal_sequences
                    │                    │                       │
                    │                    │                       └─ produces the analyst's deliverable
                    │                    └─ removes information-less cycles
                    └─ deduplicates trajectories sharing a signature
```

### Step 1 — `group_sequences(inplace=False, progress=False)`

Merges sequences that have **the same event signature** (same
`(obj, attr, type)` triples in the same order) and accumulates their
`weight`. The `time` of merged events is averaged.

On a 5 000-run CCF order-2 system, this typically collapses 5 000 raw
trajectories into a few thousand distinct signatures (still many —
because trajectories differ by the *number* of occ/rep cycles before
the top event fires).

**Why it matters:** downstream filters operate on signatures, not on
raw trajectories — so this is a cheap preliminary that cuts the
working set.

### Step 2 — `filter_objfm_cycles(objfm_internal=..., objfm_external=..., inplace=False, progress=False)` ★

**This is the step that prevents `compute_minimal_sequences` from
producing biased results.**

#### The problem it solves

An ObjFM transient — a failure followed somewhere later in the trace
by its mirror repair — does **not** contribute to the sequence
leading to the top event: by the time the top event fires, the
failure has been repaired. But the raw trajectory still contains
those events, making the trace longer and (more critically) making
the downstream greedy minimal-sequence algorithm absorb the
trajectory into whichever ordered sub-sequence appears *first* in the
post-grouping list — biasing the weights of mirror sequences (`cc_1 →
cc_2 → top` vs `cc_2 → cc_1→ top`).

`filter_objfm_cycles` drops those occ/rep pairs so the minimal
algorithm sees only the events that actually matter.

#### Handling the two ObjFM modes

The way an ObjFM is wired in the simulator affects what events it
emits and how they should be filtered.

**Internal mode** (`behaviour="internal"` — the default)

The ObjFM owns its own automata: failure transitions live on the
ObjFM, and their `failure_effects` write directly into the target
variables. Event names look like:

```
pump_X__def_pump.occ__cc_1     # ObjFM combo-1 failure
pump_X__def_pump.rep__cc_1     # ObjFM combo-1 repair
pump_X__def_pump.occ__cc_12    # ObjFM order-2 combo
…
```

The filter drops paired events on the **same suffix** —
`occ__cc_1` is paired with `rep__cc_1` (not with `rep__cc_2`). The
suffix capture is `\S*` so single-target ObjFM (no `__cc_X` suffix)
work transparently.

**External mode** (`behaviour="external"` or `"external_rep_indep"`)

The ObjFM creates an automaton **on each target** to synchronise the
failure. Event names then come from two sources:

```
C1__frun.occ__cc_1      # ObjFM combo-1 failure
C1__frun.rep__cc_1      # ObjFM combo-1 repair
C1.frun__occ            # target-side failure (name-prefixed by the ObjFM, see note)
C1.frun__rep            # target-side repair
```

The filter does two things on external mode:

1. **Drops every event on the ObjFM** (`rm_events_by_obj`) — the
   ObjFM's own events are a synchronisation mechanism, not
   trajectory-meaningful in external mode.
2. **Drops paired target events** — `C1.frun__occ` paired with
   `C1.frun__rep` on the *same* target.

!!! note "Why the target events are prefixed by `frun__`"
    Up to cod3s 1.3.3, target events were named `C1.occ` / `C1.rep`
    without an ObjFM prefix. This blocked stacking multiple ObjFM on
    the same target (state-name collision in PyCATSHOO) and made
    sequence traces ambiguous when more than one ObjFM acted on a
    component. From cod3s 1.4.0, target automata are name-prefixed
    with the ObjFM's `fm_name` so they coexist cleanly, and so the
    filter can identify the target events from the ObjFM name alone.

#### Three ways to call `filter_objfm_cycles`

```python
# 1. Auto-discovery (path A, system attached) — preferred
analyser.filter_objfm_cycles(inplace=True)

# 2. Explicit (path B, post-mortem from XML)
analyser.filter_objfm_cycles(
    objfm_internal=["pump_X__pump_def"],
    objfm_external=["sensor_1__sensor_def", "sensor_2__sensor_def"],
    inplace=True,
)

# 3. Custom state names (when an ObjFM uses non-default state names)
analyser.filter_objfm_cycles(
    objfm_internal=["my_fm"],
    failure_state="ko",
    repair_state="ok",
    inplace=True,
)
```

Auto-discovery uses each ObjFM's own `failure_state` / `repair_state`
attributes, so a system that mixes default and custom naming is
handled correctly in a single call.

#### Empty list = explicit no-op (NOT auto-discovery)

Passing `objfm_internal=[]` (an empty list) **disables** auto-discovery
for the whole call — the caller has explicitly taken control. To
re-enable auto-discovery, omit the parameter (i.e. pass `None`, the
default).

### Step 3 — `compute_minimal_sequences(inplace=False, progress=False)`

Reduces a set of grouped sequences to the **minimal cut sets** that
explain the top event.

#### Algorithm

For each `target_name`, sort sequences by ascending length. Pop the
shortest, then scan all remaining longer sequences and **absorb**
into the shortest those that *contain it as an ordered
sub-sequence* (`Sequence.is_included` test). Repeat on the next
shortest.

Output: each remaining sequence is *minimal* (no shorter sequence in
the set is an ordered sub-sequence of it), and its weight equals the
sum of the weights of all longer sequences it absorbed.

#### Properties and limitations

* **Greedy.** When two short sequences are mirror twins (same length,
  no inclusion relation between them), the longer trajectories that
  match *both* are attributed to whichever short sequence is processed
  first. Without `filter_objfm_cycles` in step 2, the post-grouping
  ordering is essentially random and the resulting weights are
  biased.

* **Order-dependent.** With `filter_objfm_cycles` applied first, the
  remaining trajectories no longer match multiple mirror twins
  ambiguously (the bias-generating long trajectories have collapsed
  onto a single signature), so the greedy algorithm produces a
  symmetric, stable result.

* **The output's `weight` field is the total trajectory count
  absorbed by that minimal**, and `probability = weight / total_weight`
  is the empirical probability of the cut set occurring before the
  top event.

* **Zero-event sequences are kept.** They represent trajectories
  where the top event was *not* reached (in `addTarget("…", "ST")`
  setups, these are the trajectories that ran the full `tmax` without
  triggering). Useful for safety probability accounting.

## End-to-end example

The canonical reproducer for the asymmetry bug
(`examples/ccf_sequence_asymmetry/`) shows the three intermediate
stages side by side:

```
=== group_sequences ONLY (expected symmetry) ===
  total weight = 5000  (2413 distinct sequences)
  …
  cc_1 then cc_2 : weight 3661
  cc_2 then cc_1 : weight 3667
  asymmetry ratio : 1.00×  (OK)

=== group + compute_minimal_sequences (reproduces the bug) ===
  total weight = 5000  (21 distinct sequences)
  …
  cc_1 then cc_2 : weight 1466
  cc_2 then cc_1 : weight 208
  asymmetry ratio : 7.05×  (SUSPECT — investigate)

=== filter occ↔rep + group + compute_minimal_sequences (canonical fix) ===
  total weight = 5000  (4 distinct sequences)
  #1 N=3344  cc_12 → system_down.occ                       (66.88 %)
  #2 N= 866  cc_2 → cc_1 → system_down.occ                 (17.32 %)
  #3 N= 772  cc_1 → cc_2 → system_down.occ                 (15.44 %)
  #4 N=  18  (zero events — no top event reached)
  cc_1 then cc_2 : weight 772
  cc_2 then cc_1 : weight 866
  asymmetry ratio : 1.12×  (OK)
```

The first run shows that without minimalisation the analysis is
correct but uselessly large (2 413 signatures). The second shows that
naively minimalising on top of `group_sequences` distorts the cut-set
weights by 7×. The third — the canonical pipeline — produces 4 clean,
symmetry-respecting cut sets.

## Quick reference

| Method | Purpose |
|---|---|
| `SequenceAnalyser.from_pyc_system(system)` | Build from a live PyCATSHOO system + attach the system for auto-discovery. |
| `analyser.group_sequences(inplace, progress)` | Merge identical signatures, sum weights. |
| `analyser.filter_objfm_cycles(objfm_internal, objfm_external, failure_state, repair_state, inplace, progress)` | Drop ObjFM occ/rep cycles. Auto-discovers when a system is attached and no list is passed. |
| `analyser.compute_minimal_sequences(inplace, progress)` | Reduce to minimal cut sets. Run AFTER `filter_objfm_cycles`. |
| `analyser.rm_events_by_obj(obj_name, inplace, progress)` | Drop all events from a given component (low-level, used by `filter_objfm_cycles` for external-mode ObjFM). |
| `analyser.rm_events_ordered_pattern(name_pat1, name_pat2, inplace, progress)` | Drop paired events matching two regex patterns. The generic primitive `filter_objfm_cycles` wraps with ObjFM-aware regexes. |
| `analyser.compute_minimal_sequences` after `filter_objfm_cycles` | The deliverable: empirical cut-set probabilities. |

## See also

* `examples/ccf_sequence_asymmetry/` — the canonical reproducer + fix
  walkthrough.
* `examples/bench_sequence_paths/bench_paths.py` — reproducible
  performance benchmark of the two ingestion paths.
* `tests/pyc_obj/sequence_equivalence/` — automated equivalence
  checks across 4 system variants.
* `cod3s.pycatshoo.sequence` — API reference.
