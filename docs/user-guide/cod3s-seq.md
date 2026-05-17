# Interactive Sequence Analysis (`cod3s-seq`)

`cod3s-seq` is a terminal user-interface (TUI) for **post-mortem
analysis** of PyCATSHOO sequence dumps. It loads a sequence file
(raw XML or JSON cod3s), shows the sequences in a 3-panel layout,
and lets you interactively stack operations from the cod3s
sequence-analysis pipeline:

* `group_sequences` — collapse identical event signatures
* `filter_objfm_cycles` — drop `(occ, …, rep)` ObjFM round-trips
* `compute_minimal_sequences` — keep only minimal cut-sets
* `rm_events_by_obj` — remove every event whose `obj` matches a name
* `rm_events_ordered_pattern` — remove ordered event patterns (regex)
* `rename_events` — regex-substitute event fields

Each operation is pushed onto a **linear pipeline** with full
undo / redo, and the resulting analyser can be exported to JSON cod3s,
CSV (one row per event) or a Markdown report.

## Installation

`cod3s-seq` ships with `cod3s` by default — installing the package is
enough:

```bash
pip install cod3s
# or, with uv:
uv sync
```

The `cod3s-seq` console script is registered as an entry-point in
`pyproject.toml`, so a fresh install of the `cod3s` package
automatically makes the binary available on `$PATH`.

Textual (≥ 8.2, < 9) is pulled in as a default runtime dependency by
`cod3s`; no extra install step is required.

## Quick start

```bash
# Inspect a raw XML dump produced by PycSystem.setResultFileName
cod3s-seq results/sequences.xml

# Inspect a JSON cod3s dump produced by run-cod3s-study
cod3s-seq results/sequences_minimal.json

# Replay a saved pipeline on a new dump
cod3s-seq results/sequences.xml --pipeline canonical.yaml

# Quickly explore a huge XML dump — only load the first 200 sequences
cod3s-seq results/sequences.xml --max-sequences 200

# Live mode: a Python factory builds the PycSystem so ObjFM are
# auto-discovered and the filter modal renders a checklist
cod3s-seq results/sequences.xml --factory mymodule:build_system
```

The TUI opens immediately; press `?` (or the displayed key bindings in
the footer) to discover the actions.

## Post-mortem mode vs live mode

`cod3s-seq` runs in one of two modes, chosen at startup:

| Mode         | Triggered by                       | What it knows                                                                                  | UX difference                                                                                                 |
|--------------|------------------------------------|------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| Post-mortem  | The default (no `--factory`)       | Only the dump file. ObjFM names are unknown to the tool.                                       | The `filter_objfm_cycles` modal asks you to **type** the ObjFM names as a comma-separated list.               |
| Live         | `--factory module.path:fn`         | Also the **populated `PycSystem`** returned by the factory — every `ObjFM` component is known. | The `filter_objfm_cycles` modal renders a **checklist** of every ObjFM (`SelectionList`), pre-checked.        |

The factory contract is identical to `cod3s-isimu`'s: `fn()` must
return a populated `PycSystem`, **without simulating it** —
`cod3s-seq` does the simulation itself (via the loaded dump). PyCATSHOO
is a process-level singleton, so you can't run `cod3s-isimu` and
`cod3s-seq --factory` simultaneously in the same shell.

When the live system is attached, `filter_objfm_cycles` also gains
auto-discovery: calling it with empty lists is no longer a no-op —
the analyser introspects every `ObjFM` component on the system and
filters them all in one go.

## Layout

```
┌──────────────────┬────────────────────────────────────┬─────────────────┐
│ Pipeline         │ Sequences                          │ Detail          │
│                  │                                    │                 │
│ 1. group_sequen. │   #   weight  proba   target  sig… │ Detail — top ...│
│ 2. filter_objfm. │   1   3344    0.6688  top    a.o…  │ - weight: 3344  │
│ 3. compute_mini. │   2   875     0.1750  top    b.o…  │ - proba: 0.6688 │
│                  │   3   …                            │ ...             │
│ [-7 sigs]        │                                    │ Events:         │
│                  │                                    │ 1. t=… a.occ    │
│                  │                                    │ 2. t=… top.occ  │
└──────────────────┴────────────────────────────────────┴─────────────────┘
```

* **Pipeline panel** (left) lists the applied steps in order and
  annotates the most recent step with the size delta (`-7 sigs`).
* **Sequences panel** (middle) is a sortable `DataTable` over the
  current analyser, sorted by descending `weight`.
* **Detail panel** (right) displays the metadata and full event
  trajectory of the sequence currently highlighted in the table.

## Key bindings

| Key      | Action                                                               |
|----------|----------------------------------------------------------------------|
| `+`      | Add a pipeline step (opens the operation picker)                     |
| `u`      | Undo the last step (restores the previous analyser snapshot)         |
| `r`      | Redo the step undone with `u`                                        |
| `s`      | Save the current pipeline to a YAML file                             |
| `l`      | Load a pipeline from a YAML file (replaces current, re-applies all)  |
| `e`      | Export the current analyser (modal: JSON cod3s / CSV / Markdown)     |
| `↑` / `↓`| Move the cursor in the sequences table                               |
| `Enter`  | Select a sequence — the Detail panel updates                          |
| `q`      | Quit                                                                  |

Compute-heavy operations (`compute_minimal_sequences` on tens of
thousands of sequences) run in worker threads, so the TUI stays
responsive during long computations.

## Input formats

`cod3s-seq` accepts two formats, auto-detected via the file extension
(override with `--format`):

### 1. PyCATSHOO XML (`*.xml`)

The raw XML written by `PycSystem.setResultFileName(path)` after a
Monte-Carlo run, structured as:

```xml
<PY_RES>
  <SEQ C="target_name">
    <BR T="42.0">
      <TR NAME="component.attr"/>
    </BR>
    <BR T="57.3">
      <TR NAME="other.occ"/>
    </BR>
    ...
  </SEQ>
  <SEQ C="another_target">
    ...
  </SEQ>
</PY_RES>
```

* `SEQ@C` — the `target_name` attribute (defaults to `"Normal"` when
  absent).
* `BR@T` — the `time` attribute of every event in the sequence.
* `TR@NAME` — the event name, parsed as `obj.attr`. Names without a dot
  fall back to `obj == attr == NAME`.
* Weights are always `1` on XML (PyCATSHOO writes one `SEQ` per
  Monte-Carlo run).

The XML loader uses `ElementTree.iterparse` to stream large files, so
dumps in the tens-of-megabytes range load with bounded memory.

### 2. JSON cod3s (`*.json`)

The format produced by `run-cod3s-study` (`sequences_all.json`,
`sequences_minimal.json`) and by `cod3s-seq` itself when exporting in
JSON cod3s. The envelope is:

```json
{
  "schema_version": "1.0.0",
  "target_group_id": null,
  "sequences": [
    {
      "probability": 0.6688,
      "weight": 3344,
      "end_time": null,
      "target_name": "top",
      "events": [
        {"obj": "a", "attr": "occ", "time": 1.0, "type": null},
        {"obj": "top", "attr": "occ", "time": 2.0, "type": null}
      ]
    },
    ...
  ],
  "meta": {
    "comment": "produced by run-cod3s-study"
  }
}
```

* `schema_version` — required; the loader checks it (warn-only by
  default, strict refusal with `strict_schema=True`).
* `target_group_id` / `meta` — optional, preserved for provenance.
* `sequences[i]` — each entry is validated by the cod3s
  `Sequence` pydantic model. Errors surface the offending index
  (`sequences[3]: …`) so the file can be fixed.

A round-trip via `cod3s-seq` is **lossless**: the exported JSON cod3s
re-loads to a `SequenceAnalyser` that equals the source on a per-event
basis (weights, signatures, probabilities, target names).

## Output formats

Three exporters are exposed; pick one in the `Export` modal (`e`):

### JSON cod3s

```python
from cod3s.pycatshoo.seq_tui.exporter import export_json_cod3s
export_json_cod3s(analyser, "minimal.json")
```

Writes the same envelope as the loader's input format — re-loadable
with `--format json-cod3s` or via `load_sequences_from_json_cod3s`.

### CSV (long format)

```python
from cod3s.pycatshoo.seq_tui.exporter import export_csv
export_csv(analyser, "events.csv")
```

One row per event. Columns include at least:

| column       | meaning                                              |
|--------------|------------------------------------------------------|
| `seq_idx`    | Sequence index in the analyser                        |
| `event_obj`  | Event object name                                     |
| `event_attr` | Event attribute                                       |
| `event_time` | Event timestamp                                       |
| `event_type` | Optional event type                                   |
| `weight`     | Weight of the parent sequence                         |
| `probability`| Probability of the parent sequence                    |
| `target_name`| Target the sequence is contributing to                |

Suitable for spreadsheet analysis (Excel, pandas, R).

### Markdown report

```python
from cod3s.pycatshoo.seq_tui.exporter import export_markdown
export_markdown(analyser, "report.md")
```

Produces a self-contained Markdown document:

```markdown
# Sequence analysis

_Total weight: 5000 — 12 distinct signatures_

| # | weight | probability | target | events                       |
|---|--------|-------------|--------|------------------------------|
| 1 | 3344   | 0.6688      | top    | a.occ → top.occ              |
| 2 | 875    | 0.1750      | top    | b.occ → c.occ → top.occ      |
| ...                                                              |

## Sequence #1

- weight: 3344
- probability: 0.6688
- target_name: top
- end_time: —

| t       | obj    | attr      | type |
|---------|--------|-----------|------|
| 100.000 | a      | occ       | —    |
| 250.123 | top    | occ       | —    |
```

The top summary table is sorted by descending weight; each detail
section follows the same order. Empty sequences (no `top` event
reached) are flagged with a placeholder line so they remain visible.

## Pipeline YAML format

Pipelines are serialised as YAML via PyYAML's `safe_dump`. The shape
is intentionally minimal:

```yaml
version: '1.0.0'
steps:
  - op: group_sequences
  - op: filter_objfm_cycles
    objfm_internal: [pump_X__def_pump, valve_Y__def_valve]
    objfm_external: []
    failure_state: occ
    repair_state: rep
  - op: compute_minimal_sequences
  - op: rm_events_by_obj
    obj_name: noise_component
  - op: rm_events_ordered_pattern
    name_pat1: ^(.+)\.start$
    name_pat2: ^\1\.stop$
  - op: rename_events
    attr: obj
    pat_source: ^old_(.+)$
    pat_target: new_\1
```

* `version` — schema version (currently `"1.0.0"`).
* `steps` — ordered list. Each entry has an `op` discriminator and the
  parameters of the operation.
* Unknown `op` values are rejected with a clear Pydantic validation
  error (so typos surface immediately).
* Unknown step parameters are rejected (`extra = "forbid"`).

### Apply a pipeline non-interactively

```bash
cod3s-seq results/sequences.xml --pipeline my-canonical.yaml
```

The startup pipeline is applied silently before the TUI opens; the
panels show the post-pipeline state. From there you can keep adding
steps interactively.

### Apply a pipeline programmatically

```python
from cod3s.pycatshoo.seq_tui.loader import load_sequences_from_xml
from cod3s.pycatshoo.seq_tui.pipeline import Pipeline
from cod3s.pycatshoo.sequence import SequenceAnalyser

sequences = load_sequences_from_xml("results/sequences.xml")
analyser = SequenceAnalyser(sequences=sequences)
analyser.update_probs()

Pipeline.load_yaml("canonical.yaml").apply(analyser)
print(len(analyser.sequences), "distinct signatures")
```

## Operations reference

### `group_sequences`

Collapses sequences with identical event signatures into a single
entry whose weight is the sum of the originals. No parameters.

### `filter_objfm_cycles`

Removes `(occ, …, rep)` round-trips on ObjFM events. Useful before
computing minimal sequences when ObjFM auto-repair would otherwise
pollute the cut-sets.

| parameter        | type        | default | meaning                                                                                  |
|------------------|-------------|---------|------------------------------------------------------------------------------------------|
| `objfm_internal` | `list[str]` | `[]`    | ObjFM names whose `occ__cc_*` events should be paired with their `rep__cc_*` counterparts |
| `objfm_external` | `list[str]` | `[]`    | Same, for externally-triggered ObjFMs                                                    |
| `failure_state`  | `str`       | `"occ"` | Failure attribute prefix (override if you customised `trans_name_prefix`)                |
| `repair_state`   | `str`       | `"rep"` | Repair attribute prefix                                                                  |

### `compute_minimal_sequences`

Keeps only minimal cut-sets — sequences that are not extensions of
shorter sequences in the same analyser. No parameters.

### `rm_events_by_obj`

Drops every event whose `obj` field equals `obj_name`.

| parameter   | type  | meaning                          |
|-------------|-------|----------------------------------|
| `obj_name`  | `str` | Exact match on the `obj` field   |

### `rm_events_ordered_pattern`

For each sequence, finds the first event matching `name_pat1`; if it
is later followed (any time later) by an event matching `name_pat2`,
the first event is removed. `name_pat1` and `name_pat2` are Python
regexes applied on the event "name" (`{obj}.{attr}`).

| parameter    | type  | meaning                                              |
|--------------|-------|------------------------------------------------------|
| `name_pat1`  | `str` | Regex on the event to potentially remove             |
| `name_pat2`  | `str` | Regex on the event that, if seen later, triggers the removal |

### `rename_events`

Performs a regex substitution on one of the `SeqEvent` fields. Useful
for normalising object names across runs.

| parameter    | type                                  | meaning                                              |
|--------------|---------------------------------------|------------------------------------------------------|
| `attr`       | `Literal["obj","attr","type"]`        | Field to rewrite                                     |
| `pat_source` | `str`                                 | Source regex (Python `re` syntax)                    |
| `pat_target` | `str`                                 | Replacement (supports backreferences `\1` etc.)      |

## Examples

The repository ships a complete demo system —
`examples/ccf_sequence_asymmetry/` — that produces a realistic
sequence dump on which every example below can be replayed verbatim.
Each example shows the **exact command line**, the **modal inputs**
you should type, and the **expected result** in the panels.

### Prerequisites — produce a sequence dump

`cod3s-seq` is a post-mortem tool: it needs an `.xml` or `.json` dump
to inspect. Two simple ways to obtain one:

**Option A — run the bundled CCF demo (≈ 30 s)**:

```bash
# From the repo root
cd examples/ccf_sequence_asymmetry
python ccf_sequence_asymmetry.py --nb-runs 5000 --out /tmp/ccf-demo
ls /tmp/ccf-demo/sequences.xml
```

The demo simulates two redundant pumps (`pump_1`, `pump_2`) that
share a single order-2 CCF failure mode `def_pump`. After ~5 000
Monte-Carlo runs you obtain `/tmp/ccf-demo/sequences.xml`
(≈ 5 000 `<SEQ>` entries).

**Option B — run a real study via `run-cod3s-study`**:

```bash
run-cod3s-study --model system.yaml --study-specs study.yaml \
                --results-dir /tmp/my-study
# Produces /tmp/my-study/sequences.xml (raw)
# and      /tmp/my-study/sequences_minimal.json (already pipelined).
```

The rest of this section assumes `/tmp/ccf-demo/sequences.xml`
exists.

### Example 1 — first contact: just look at the data

```bash
cod3s-seq /tmp/ccf-demo/sequences.xml
```

What you see immediately after the TUI opens:

* **Pipeline panel** — empty, with the hint `(empty — press + to add a step)`.
* **Sequences panel** — header reads `Sequences (5000 signatures, total weight 5000)` because the raw XML has not been grouped yet (one entry per Monte-Carlo run).
* **Detail panel** — empty, with `(no sequence selected)`.

Press `↓` to walk the list, then `Enter` on any row: the detail
panel fills with the full event chronology.

Press `q` to quit. Nothing is written to disk yet.

### Example 2 — group, filter, minimise (the canonical pipeline)

```bash
cod3s-seq /tmp/ccf-demo/sequences.xml
```

In the TUI, type the following sequence:

| Step | Key      | Modal input                                                                                         | Visible effect                                                            |
|------|----------|-----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| 1    | `+`      | Select **Group identical sequences** → `Add`                                                        | Pipeline shows `1. group_sequences  [-N sigs]`. List shrinks to ≈ 8 sigs. |
| 2    | `+`      | Select **Filter ObjFM cycles** → `Add`. In the next modal: `ObjFM internal = pump_X__def_pump`, leave defaults. | Pipeline gains `2. filter_objfm_cycles(int=['pump_X__def_pump'])`. Sigs drop again. |
| 3    | `+`      | Select **Compute minimal sequences** → `Add`                                                        | Pipeline gains `3. compute_minimal_sequences`. Only minimal cut-sets remain. |

The header of the Sequences panel now reads something like
`Sequences (3 signatures, total weight 5000)`, and the top entry has
a signature like `pump_X__def_pump.occ__cc_12 → system_down.occ`.

Press `e`, pick **Markdown report**, type `/tmp/ccf-report.md`,
press `Enter`. A notification confirms the export.

```bash
# Outside the TUI
head -20 /tmp/ccf-report.md
```

You see the top summary table sorted by descending weight and one
detail section per surviving sequence.

### Example 3 — save the pipeline as YAML and replay it

Continuing from Example 2 (do not quit yet), press `s` and type
`/tmp/canonical.yaml`. The file looks like:

```yaml
version: '1.0.0'
steps:
- op: group_sequences
- op: filter_objfm_cycles
  objfm_internal:
  - pump_X__def_pump
  objfm_external: []
  failure_state: occ
  repair_state: rep
- op: compute_minimal_sequences
```

Quit (`q`) and replay the pipeline non-interactively on a fresh dump:

```bash
cod3s-seq /tmp/ccf-demo/sequences.xml --pipeline /tmp/canonical.yaml
```

The TUI opens with the pipeline already applied — the panels show
exactly the same minimised sigs as in Example 2.

### Example 4 — compare two simulation runs

Re-run the CCF demo with a different seed to get a second dump:

```bash
cd examples/ccf_sequence_asymmetry
python ccf_sequence_asymmetry.py --nb-runs 5000 --seed 42 \
    --out /tmp/ccf-runA
python ccf_sequence_asymmetry.py --nb-runs 5000 --seed 7 \
    --out /tmp/ccf-runB
```

Export a Markdown report for each, applying the same pipeline:

```bash
cod3s-seq /tmp/ccf-runA/sequences.xml --pipeline /tmp/canonical.yaml
# in the TUI: press `e`, pick Markdown, type /tmp/runA.md, Enter, q

cod3s-seq /tmp/ccf-runB/sequences.xml --pipeline /tmp/canonical.yaml
# in the TUI: press `e`, pick Markdown, type /tmp/runB.md, Enter, q
```

Diff the two reports side-by-side:

```bash
diff -u /tmp/runA.md /tmp/runB.md | less
# or, if you want a coloured view:
git diff --no-index /tmp/runA.md /tmp/runB.md
```

Differences in weight (column 2 of the top table) reflect
Monte-Carlo noise; differences in *signatures* indicate that the two
runs explored qualitatively different failure modes — a signal worth
investigating.

### Example 5 — undo / redo to experiment with alternative pipelines

```bash
cod3s-seq /tmp/ccf-demo/sequences.xml
```

1. `+` → `group_sequences` → `Add`. The list collapses.
2. `+` → `compute_minimal_sequences` → `Add` (skipping the filter on purpose).
3. Observe the suspicious result: minimal sequences include orphaned `occ` / `rep` pairs.
4. Press `u` — undo. The minimal step disappears; you're back to the grouped state.
5. `+` → `filter_objfm_cycles` → input `ObjFM internal = pump_X__def_pump`, `Add`.
6. `+` → `compute_minimal_sequences` → `Add`.

The pipeline panel now lists 3 clean steps and the surviving
signatures no longer contain `rep__cc_*` events. Press `r` to redo
the discarded step ; press `u` again to come back. The undo stack
has depth 20 by default.

### Example 6 — clean noisy events before minimisation

Some simulations emit periodic "heartbeat" events that have no
analytical value. To suppress them:

```bash
cod3s-seq /tmp/my-study/sequences.xml
```

1. `+` → `rm_events_by_obj` → input `Object name = clock` → `Add`. Every event whose `obj == "clock"` disappears from every sequence.
2. `+` → `group_sequences` → `Add`. Sequences that differed only by clock noise collapse.
3. Continue with `filter_objfm_cycles` + `compute_minimal_sequences` as in Example 2.

### Example 7 — fully non-interactive batch (export only, no TUI)

For CI / batch scripts where you don't want an interactive session,
use the programmatic API instead of `cod3s-seq`:

```python
# scripts/batch_export.py
from pathlib import Path

from cod3s.pycatshoo.seq_tui import (
    Pipeline,
    export_markdown,
    load_sequences_from_xml,
)
from cod3s.pycatshoo.sequence import SequenceAnalyser

for run_dir in Path("/tmp/runs").iterdir():
    sequences = load_sequences_from_xml(run_dir / "sequences.xml")
    analyser = SequenceAnalyser(sequences=sequences)
    analyser.update_probs()
    Pipeline.load_yaml("/tmp/canonical.yaml").apply(analyser)
    export_markdown(analyser, run_dir / "report.md")
    print(f"{run_dir.name}: {len(analyser.sequences)} sigs")
```

```bash
python scripts/batch_export.py
```

The pipeline YAML is the same artefact `cod3s-seq` saves with `s`,
so the interactive and batch workflows stay in lock-step.

### Example 8 — round-trip JSON cod3s through the TUI

```bash
# 1. Start from raw XML, save as canonical JSON cod3s.
cod3s-seq /tmp/ccf-demo/sequences.xml --pipeline /tmp/canonical.yaml
# In the TUI: e → JSON cod3s → /tmp/ccf-minimal.json, q

# 2. Reload the JSON dump — same view as before the save.
cod3s-seq /tmp/ccf-minimal.json
```

This is how an R&D engineer ships an analysed dump to a safety
analyst: the JSON file is self-contained (schema, weights, events,
target names) and re-opens in `cod3s-seq` exactly where the
engineer left off.

### Example 9 — live mode with a factory (`--factory`)

The bundled CCF demo exposes a `build_system` factory you can point
`cod3s-seq` at:

```bash
# Re-use the dump generated in the prerequisites step
cod3s-seq /tmp/ccf-demo/sequences.xml \
    --factory examples.ccf_sequence_asymmetry.ccf_sequence_asymmetry:build_system \
    --log-level INFO
```

The first two log lines confirm the system was attached and the
ObjFM was discovered:

```
[INFO] Live mode: system 'CCF_Sequence_Asymmetry_Demo' attached (3 components)
[INFO] Discovered ObjFM: internal=['pump_X__def_pump'], external=[]
```

Now press `+` → **Filter ObjFM cycles** → `Add`. Instead of a
text-input asking for ObjFM names, the modal renders a
**checklist**: every discovered ObjFM is listed, pre-checked, with
the message `(live mode — 1 internal, 0 external discovered)` at the
top. Hit `Tab` / `Space` to toggle entries, or just press `Enter` to
accept all the defaults.

The benefit:

* **Zero typos**: you don't have to remember the exact ObjFM name
  (`pump_X__def_pump`, not `def_pump`) — it's there in the list.
* **Discoverability**: scanning the checkbox list is faster than
  reading `git grep ObjFM` in the model source.
* **Custom failure/repair-state names**: still typed in the two
  Input fields below the checklist, since they're rarely customised
  in practice.

If your model has many ObjFM (10+), the checklist also scrolls and
supports `↑` / `↓` to navigate — much easier than typing a long
comma-separated string.

#### Caveats

* The factory must build the system **without simulating it** —
  same contract as `cod3s-isimu --factory`. If it ran a Monte Carlo
  internally, the PyCATSHOO singleton would be in a poisoned state
  by the time `cod3s-seq` reaches the TUI mainloop.
* PyCATSHOO is a process-level singleton; you cannot run
  `cod3s-isimu` and `cod3s-seq --factory` in the same shell at the
  same time. Open a second shell.
* When ObjFM are discovered, the TUI marks live mode in the modal
  header (`(live mode — N internal, M external discovered)`) so you
  know which path you're on.

## Programmatic API

The pure-Python helpers are reusable as a library — Textual is **not**
required:

```python
from cod3s.pycatshoo.seq_tui import (
    # loader
    load_sequences_from_xml,
    load_sequences_from_json_cod3s,
    # pipeline + step types
    Pipeline,
    GroupSequencesStep,
    FilterObjFMCyclesStep,
    ComputeMinimalSequencesStep,
    # exporter
    export_csv,
    export_json_cod3s,
    export_markdown,
)
from cod3s.pycatshoo.sequence import SequenceAnalyser

sequences = load_sequences_from_xml("results/sequences.xml")
analyser = SequenceAnalyser(sequences=sequences)
analyser.update_probs()

Pipeline(
    steps=[
        GroupSequencesStep(),
        FilterObjFMCyclesStep(objfm_internal=["pump_X__def_pump"]),
        ComputeMinimalSequencesStep(),
    ]
).apply(analyser)

export_markdown(analyser, "report.md")
```

## Troubleshooting

* **`cod3s-seq: command not found`** — reinstall `cod3s`
  (`pip install -e .` if you cloned the repo). The console-script
  entry is registered in `pyproject.toml`.
* **"cannot detect format" loader error** — pass `--format` explicitly,
  or rename the file with a `.xml` / `.json` extension.
* **"schema_version" missing** — the JSON file is not a cod3s envelope.
  Check it was produced by `run-cod3s-study` or by a previous
  `cod3s-seq` export.
* **TUI feels frozen during `compute_minimal_sequences`** — the
  computation runs in a worker thread; check the notification (a
  small box at the bottom) for completion. Large dumps (50k+
  sequences) can take a few seconds; the panels refresh as soon as
  the worker returns.
* **Out-of-memory on huge XML dumps** — pass `--max-sequences N` to
  cap the load.
