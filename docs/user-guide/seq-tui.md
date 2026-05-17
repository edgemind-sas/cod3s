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
```

The TUI opens immediately; press `?` (or the displayed key bindings in
the footer) to discover the actions.

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

### 1. Load + minimise + export

```bash
cod3s-seq results/sequences.xml
```

1. Press `+`, pick `group_sequences`. The sequences collapse to
   distinct signatures.
2. Press `+`, pick `filter_objfm_cycles`. Enter the relevant ObjFM
   names in the modal (comma-separated).
3. Press `+`, pick `compute_minimal_sequences`. The cut-sets appear.
4. Press `e`, pick `Markdown`, type `/tmp/report.md`. Done.

Save the pipeline with `s` for replay on future dumps.

### 2. Replay a saved pipeline

```bash
cod3s-seq results/sequences.xml --pipeline canonical.yaml
```

The TUI opens already showing the post-pipeline state; the pipeline
panel lists the three applied steps with their size deltas.

### 3. Compare two dumps with the same pipeline

```bash
cod3s-seq runA/sequences.xml --pipeline canonical.yaml
cod3s-seq runB/sequences.xml --pipeline canonical.yaml
```

The Markdown export of each session can be diffed with any standard
tool (`diff`, `git diff --no-index`).

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
