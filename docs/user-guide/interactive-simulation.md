# Interactive Simulation (`cod3s-isimu`)

`cod3s-isimu` is a terminal user-interface (TUI) that drives a `PycSystem`
step-by-step. It lets you select transitions to fire manually, observe how
components and variables evolve, see exactly which transitions fired
together at each instant, and replay or reset the trace at will.

## Installation

The TUI is shipped as an optional extra so the default `cod3s` install stays
lightweight:

```bash
pip install -e ".[isimu]"
# or, with uv:
uv sync --extra isimu
```

This pulls in [Textual](https://textual.textualize.io/) (≥8.2,<9) and
`pytest-asyncio` (≥0.23) for the test suite.

## Quick start

### From a YAML model file

`cod3s-isimu` accepts the **same YAML model format** as `run-cod3s-study`:

```bash
cod3s-isimu --model examples/pyc_pdmp/model.yaml
```

The model YAML must contain `imports`, `system`, `components` and
`connections` keys. See `cod3s/scripts/_common.py` for the shared loader.

### From a Python factory

When your system is built programmatically, point `cod3s-isimu` at a callable
that returns a populated `PycSystem`:

```bash
cod3s-isimu --factory my_project.systems:build_demo
```

The factory must take no arguments. Modules are resolved through the regular
Python import machinery, so make sure `my_project` is on `PYTHONPATH`.

### Adding failure-modes and events

If you keep failure-modes / events / etc. in a separate study spec, pass
`--study-specs`:

```bash
cod3s-isimu --model model.yaml --study-specs study.yaml
```

Only `failure_modes` and `events` keys are applied. `indicators` / `targets`
are silently ignored — they're meaningless in interactive mode.

## Layout

```
┌─ Fireable transitions ──────┐┌─ Components / Variables ──────────────┐
│ # comp transition src→tgt ★ ││ filter: [_______________________]      │
│ 0 A    fail        ok→ko  ★ ││ A                                       │
│ 1 B    fail        ok→ko  ★ ││  ├─ flag    : True  (init: False)      │
│ 2 V    open        ok→on    ││  ├─ counter : 0                         │
│                             ││ B                                       │
│                             ││  ├─ flag    : False → True              │
└─────────────────────────────┘└─────────────────────────────────────────┘
┌─ Last transition Δ ─────────┐┌─ History (grouped by t) ───────────────┐
│ t = 1.000                   ││ t=1.000  ▸ A.fail, B.fail               │
│ • A.fail: ok → ko           ││ t=0.000  ▸ <bootstrap>                  │
│ • B.fail: ok → ko           ││                                          │
│ Δ vars:                     ││                                          │
│   B.flag: False → True      ││                                          │
└─────────────────────────────┘└─────────────────────────────────────────┘
```

* **Fireable transitions** — every transition currently due (planned at the
  next `stepForward`). The trailing `★` column lights up on the rows that
  share `end_time` with the highlighted row, so you know what will fire
  together if you press <kbd>Enter</kbd>.
* **Components / Variables** — every backend variable, namespaced as
  `component.variable`. The filter input above the tree applies a
  case-insensitive substring match live, on every keystroke.
* **Last transition Δ** — the transitions that fired at the last step plus
  the variables whose value changed.
* **History (grouped by t)** — every step in reverse chronological order,
  grouped by firing time.

### Variable coloring

| Style          | Meaning                                          |
|----------------|--------------------------------------------------|
| dim grey       | current value matches the declared initial       |
| **orange**     | current ≠ initial but did *not* change at this step |
| **bold red**   | changed at the last step (renders `prev → curr`) |

## Keyboard bindings

| Key                     | Action                                                 |
|-------------------------|--------------------------------------------------------|
| <kbd>Enter</kbd>        | Force-fire the highlighted row (and all its peers)     |
| <kbd>↑</kbd> / <kbd>↓</kbd>     | Move the cursor in the fireable list (updates ★) |
| <kbd>b</kbd>            | Step backward — undo the last step                     |
| <kbd>r</kbd>            | Reset the simulation to t=0                            |
| <kbd>e</kbd>            | Open the Export modal (writes `<path>.csv` and `<path>.json`) |
| <kbd>p</kbd>            | Open the Re-plan modal (sets a transition's planned date) |
| <kbd>?</kbd>            | Show the command palette                               |
| <kbd>q</kbd> / <kbd>Ctrl+C</kbd> | Quit (calls `system.stopInteractive()` cleanly) |

## Programmatic usage

The TUI is a regular Python class — you can launch it from a script that
already built a `PycSystem`:

```python
from cod3s.pycatshoo.isimu.app import run_isimu

system = build_my_system()  # returns a PycSystem
run_isimu(system)
```

`PycSystem.isimu_start_cli()` is a convenience shortcut for the same call:

```python
system = PycSystem(name="...")
# ... add_components, add_connections, ...
system.isimu_start_cli()
```

## Limitations

* **Continuous variables (PDMP)** evolve between transitions. The TUI takes
  one snapshot per step — values you see are the state immediately
  before/after each `stepForward`, not the continuous trajectory in
  between. Sampling during continuous evolution is on the roadmap.
* **One PyCATSHOO system at a time.** PyCATSHOO is a process-level
  singleton; closing the TUI calls `stopInteractive()` but does *not*
  call `terminate_session()` — leaving room for the parent script to
  reuse the system.
* **No save/restore yet.** A session lives for the duration of the
  process. Use the Export modal (`e`) to persist the timeline.

## Troubleshooting

* `ModuleNotFoundError: No module named 'textual'` — install the extra:
  `pip install -e ".[isimu]"`.
* The screen flickers on a tiny terminal — Textual needs at least 80
  columns × 24 rows for the grid layout to look right.
* `cod3s-isimu` exits immediately with a `NameError` on `python_class` —
  the `imports:` list of your model YAML doesn't expose the system class
  to the loader. Check that the imported file actually defines (or
  re-exports) the class named in `system.python_class`.
