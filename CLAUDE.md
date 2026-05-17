# AI Guidance

This file provides guidance to any AI assistant when working with code in this repository.

## Language

**Conversation with Roland: French.** All chat replies, status updates, planning prose, brainstorm notes, and commit-message bodies written *for the human in this session* must be in French.

**Code artefacts: English.** Everything that lives in the repository — source code, identifiers, docstrings, inline comments, log/exception messages, Markdown documentation (`docs/`, `README.md`, `CLAUDE.md`, brainstorm/plan files under `docs/`), test names and assertion messages, example walkthrough text inside `examples/*.py` — is written in English. This keeps the codebase consistent for future readers and tooling.

Commit-message subjects follow Conventional Commits in English (`feat(...):`, `fix(...):`, etc.); the body can stay English too unless Roland explicitly asks for a French body.

## Workflow / Collaboration

**Solo project — no PRs / MRs to open.** Roland is the sole developer and code reviewer of COD3S. Do not run `gh pr create` (or equivalents) and do not propose opening one as a "next step".

The expected workflow is:

1. **Develop on a feature branch**, e.g. `feat/<topic>` or `fix/<topic>`, branched from `master`.
2. **Push the branch** (`git push -u origin <branch>`) once a phase or atomic change is committed and tested green. This persists work and lets us reference it across machines/sessions; it is not a request for review.
3. **Validate locally** (full pytest, lint, mypy on touched files, optional `mkdocs build`).
4. **Merge to `master` directly** when validated. Roland performs the merge himself (typically a fast-forward or `--no-ff` merge from the local feature branch). Then the feature branch can be deleted.

When closing a session, suggest "merge to master when validated" — never "open a PR".

## Project Overview

COD3S (COmplex Dynamic Stochastic System Simulation) is a Python library for modeling and simulating complex industrial systems. It provides a high-level abstraction layer over simulation engines like PyCATSHOO, based on **Piecewise Deterministic Markov Processes (PDMPs)** mathematical framework.

The framework enables users to build reusable component libraries, define system architectures, and perform quantitative reliability/performance analyses through Monte Carlo simulation.

## Development Commands

### Environment Setup
```bash
# Install development dependencies using uv
uv sync --upgrade

# Activate virtual environment
source .venv/bin/activate
```

### Testing
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run slow tests
pytest --runslow

# Run specific test file
pytest tests/core/test_kb_001.py

# Run specific test function
pytest tests/core/test_kb_001.py::test_function_name
```

### Code Quality
```bash
# Automatic formatting
black .
isort .

# Linting
flake8 .

# Type checking
mypy cod3s/
```

### Documentation
```bash
# Start MkDocs development server (accessible at http://127.0.0.1:8000)
mkdocs serve

# Build static documentation
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy
```

### Package Building
```bash
# Build package
python -m build

# Verify built package
twine check dist/*

# Local editable installation
pip install -e .
```

## Core Architecture

COD3S is built around a multi-layer architecture that translates high-level system descriptions into simulation backends:

### 1. Core Layer (`cod3s/core.py`)

**ObjCOD3S**: Base class for all COD3S objects, providing:
- Recursive serialization/deserialization with `cls` field injection
- YAML loading with `from_yaml()` and `from_dict()`
- Subclass enumeration via `get_subclasses()`
- Dynamic object instantiation based on `cls` attribute

Key pattern: All COD3S data structures inherit from `ObjCOD3S` to enable polymorphic (de)serialization.

### 2. Knowledge Base Layer (`cod3s/kb.py`)

Defines reusable component templates:

- **KB**: Container for component class definitions with semantic versioning
- **ComponentClass**: Template defining component structure (attributes, interfaces, automata)
- **InterfaceTemplate**: Defines input/output ports with connection constraints
- **AttributeTemplate**: Typed attributes (bool, int, float, enum) with default values
- **ComponentInstance**: Instantiation of a ComponentClass with specific parameters

The KB provides validation, versioning, and the ability to create component instances with custom parameters.

### 3. System Layer (`cod3s/system.py`)

Manages system architecture:

- **System**: Collection of component instances and connections
  - `components`: Dictionary of ComponentInstance objects
  - `connections`: Dictionary of Connection objects defining inter-component links
  - `check_kb()`: Validates KB compatibility using semver
  - `add_component()`: Creates instances from KB templates
  - `connect()`: Creates validated connections between component interfaces
  - `to_bkd()`: Translates to backend simulation frameworks

- **Connection**: Defines links between component interfaces
  - Validates port types (output→input)
  - Carries initialization parameters and metadata

### 4. PyCATSHOO Backend Layer (`cod3s/pycatshoo/`)

Translates COD3S models to PyCATSHOO simulation engine:

- **automaton.py**:
  - `PycAutomaton`: Finite state machine with states and transitions
  - `PycState`: Discrete modes with entry/exit actions
  - `PycTransition`: State changes with occurrence laws (exponential, delay, instantaneous)
  - Occurrence distributions: `ExpOccDistribution`, `DelayOccDistribution`

- **component.py**:
  - `PycComponent`: Extends `Pycatshoo.CComponent` with COD3S semantics
  - Bridge between COD3S component model and PyCATSHOO backend
  - Handles automata, variables, and PDMP contributions

- **system.py**:
  - `PycSystem`: Extends `Pycatshoo.CSystem`
  - Manages component interactions and PDMP evolution
  - `PycMCSimulationParam`: Monte Carlo simulation parameters

- **indicator.py**:
  - `PycVarIndicator`: Monitor component variables with conditions
  - `PycFunIndicator`: Custom boolean measurement functions
  - Statistical computation (mean, variance, quantiles)

- **sequence.py**:
  - `PycSequence`: Simulation trajectory data
  - `SequenceAnalyser`: Post-processing and analysis tools
  - `SeqEvent`: Discrete event representation

### 5. Utilities (`cod3s/utils/`)

- **common.py**: Utility functions (`get_class_by_name`, `get_operator_function`)
- **etl.py**: Data extraction and transformation helpers
- **logger.py**: Logging configuration

## Key Design Patterns

### 1. Polymorphic Serialization
All classes include a `cls` field in serialized form, enabling dynamic type reconstruction:
```python
obj_dict = {"cls": "PycAutomaton", "name": "my_automaton", ...}
obj = ObjCOD3S.from_dict(obj_dict)  # Returns PycAutomaton instance
```

### 2. Backend Translation Pattern
Systems translate to backend frameworks via `to_bkd_*` methods:
```python
system = System(...)
pyc_system = system.to_bkd("pycatshoo")  # Calls to_bkd_pycatshoo()
```

### 3. Template-Instance Pattern
KB stores ComponentClass templates; System contains ComponentInstance objects created from templates:
```python
kb = KB(component_classes={"Pump": pump_template})
system.add_component(kb=kb, class_name="Pump", instance_name="pump1")
```

### 4. PDMP Integration
Components contribute to continuous-discrete evolution:
- `pdmp_equation_method()`: Defines ODEs for continuous variables
- `pdmp_boundary_method()`: Detects boundary crossings
- Automata transitions define discrete jumps

## Mathematical Foundation

COD3S models are based on **Piecewise Deterministic Markov Processes**:

- **Modes**: Discrete states where continuous variables evolve deterministically
- **Continuous evolution**: ODEs within each mode: dx/dt = f_m(t, x(t))
- **Spontaneous jumps**: Random transitions with rate λ_m(x)
- **Forced jumps**: Triggered when continuous trajectories hit boundaries

See `docs/getting-started/concepts.md` for full mathematical details.

## Testing Structure

- **tests/core/**: Tests for core functionality (KB, System, serialization)
- **tests/pyc_obj/**: Tests for PyCATSHOO backend components
  - `obj_event/`: Event handling tests
  - `obj_fm/`: Failure mode tests
- **tests/usecases/**: Real-world scenario tests

## Common Development Patterns

### Creating a Component Class
```python
from cod3s.kb import ComponentClass, InterfaceTemplate, AttributeTemplate

component_class = ComponentClass(
    name="MyComponent",
    attributes=[
        AttributeTemplate(name="param1", type="float", value_default=1.0)
    ],
    interfaces=[
        InterfaceTemplate(name="input1", port_type="input"),
        InterfaceTemplate(name="output1", port_type="output")
    ]
)
```

### Building a System
```python
from cod3s.system import System
from cod3s.kb import KB

kb = KB(name="MyKB", version="1.0.0", component_classes={"Comp": comp_class})
system = System(name="MySystem", kb_name="MyKB", kb_version=">=1.0.0")
system.add_component(kb=kb, class_name="Comp", instance_name="comp1")
system.connect("comp1", "output1", "comp2", "input1")
```

### Running a Simulation
```python
from cod3s.pycatshoo.system import PycMCSimulationParam

pyc_system = system.to_bkd("pycatshoo")
sim_params = PycMCSimulationParam(
    nb_runs=1000,
    t_max=8760.0  # One year in hours
)
results = pyc_system.simulate(sim_params)
```

## Important Notes

- Python version constraint: `>=3.9,<3.12` (defined in pyproject.toml)
- Uses Pydantic v2 for data validation
- Dependencies include pandas, plotly for data analysis/visualization
- The `terminate_session()` function must be called when cleaning up PyCATSHOO resources
- Line length: 88 characters (Black formatter configuration)
- Type checking with mypy enabled but not strict (allow untyped defs)

## Entry Points

- **run-cod3s-study**: CLI for batch Monte-Carlo studies (`cod3s/scripts/run_cod3s_study.py`).
- **cod3s-isimu**: CLI for the interactive Textual TUI simulator (`cod3s/scripts/run_cod3s_isimu.py`). Textual ships as a default runtime dependency; no extra install step. See `docs/user-guide/interactive-simulation.md`.
- **cod3s-seq**: CLI for the post-mortem sequence-analysis TUI (`cod3s/scripts/run_cod3s_seq.py`). Loads a PyCATSHOO XML dump or a JSON cod3s envelope, lets the user stack pipeline steps (group / filter / minimal / rm / rename), supports undo/redo, save/load YAML, export JSON cod3s / CSV / Markdown. See `docs/user-guide/seq-tui.md`.

## Versioning

Version lives in `cod3s/version.py` (read by `pyproject.toml` via `[tool.setuptools.dynamic]`) and is exposed as `cod3s.__version__`. Bumped by Roland at release time.

The `cod3s-isimu` and `cod3s-seq` CLIs and the TUI headers **reuse the parent package version** — there is no separate `__version__` for either TUI. `cod3s-isimu --version` and `cod3s-seq --version` both print the parent `cod3s` version; the TUI shows the same value in its header. The tests `tests/scripts/test_run_cod3s_isimu.py::test_version_runs_via_subprocess` and `tests/scripts/test_run_cod3s_seq.py::test_version_runs_via_subprocess` enforce this contract.

## Examples

### ObjFM convention for example components

Whenever an example wires an ``ObjFM`` to a component variable, follow this rule:

1. **Declare the variable as reinitialised**, e.g.
   ``self.working = self.addVariable("working", Pyc.TVarType.t_bool, True); self.working.setReinitialized(True)``.
   Pick the initial value freely (``True`` or ``False``) — it is the resting / "no failure" value.
2. **Declare only ``failure_effects`** on the ObjFM (set the variable to the opposite of its initial value, e.g. ``failure_effects={"working": False}``).
3. **Leave ``repair_effects`` empty.** PyCATSHOO's reinitialised-variable mechanism restores the resting value automatically when no ObjFM automaton is in its failure state.

**Why:** A ``repair_effects`` clause registers a sensitive method on the variable that re-applies the repair value on every change. With multi-target ObjFMs, several combo automata (e.g. ``cc_1``, ``cc_12``) overlap on the same variable: the rep-state sensitive method of one fights the occ-state sensitive method of the other and ``stepForward`` loops forever. The reinitialised pattern sidesteps this by removing the rep-side enforcement entirely — no two automata ever try to write the variable simultaneously.

This convention applies to *examples*. Domain components in user code that genuinely need symmetric `failure_effects` / `repair_effects` (e.g. counter increments, state machines that go beyond a single boolean) can keep the explicit pattern, but they must use disjoint combos to avoid the same fight.

- `examples/basic_example.py` — full study (components, automata, system, indicators, Monte Carlo, results).
- `examples/objfm_demo/objfm_demo.py` — minimal showcase of the `internal` and `external` `ObjFM` behaviours with deterministic delays. Expected timeline and per-transition state are documented inline. Designed to be loaded in `cod3s-isimu` for hands-on exploration. Run with: `PYTHONPATH="examples/objfm_demo:$PYTHONPATH" uv run cod3s-isimu --factory objfm_demo:build_system`. (`external_rep_indep` is sketched in commented-out code; it will be activated when the planned pulse model from the ObjFM brainstorm lands.)
- `examples/objfm_exp_demo/objfm_exp_demo.py` — three independent equipments (pump1, pump2, valve), each with its own `ObjFMExp` (`behaviour="internal"`) using **exponential** failure / repair laws with different rates. Designed to drive the manual-planning workflow: every exp transition is fireable "now" (`end_time = currentTime()`), the user explicitly re-plans via `p` to make time advance. Run with: `PYTHONPATH="examples/objfm_exp_demo:$PYTHONPATH" uv run cod3s-isimu --factory objfm_exp_demo:build_system`.
- `examples/objfm_mix_demo/objfm_mix_demo.py` — two ObjFMs cohabiting in one system: an `ObjFMExp` over three components (C1/C2/C3, individual exp failures) and an `ObjFMDelay` over two components (D1/D2, common-cause cc_12 with ttf=10). Designed to verify the TUI surfaces what `isimu_fireable_transitions` returns when non-deterministic and deterministic laws coexist. Run with: `PYTHONPATH="examples/objfm_mix_demo:$PYTHONPATH" uv run cod3s-isimu --factory objfm_mix_demo:build_system`.

### ObjFM `external_rep_indep` (trigger model) demos

Five scenarios, one folder each. Each docstring walks the user through a precise sequence of Enter / `p` / `b` actions to verify a specific facet of the trigger semantic:

- `examples/objfm_trigger_01_minimal/` — single target, delay law, smallest possible trigger cycle. Run: `PYTHONPATH="examples/objfm_trigger_01_minimal:$PYTHONPATH" uv run cod3s-isimu --factory objfm_trigger_01_minimal:build_system`.
- `examples/objfm_trigger_02_common_cause/` — two targets, `cc_12` common cause, delay law. Synchronous repair (★ "fires together"). Run: `PYTHONPATH="examples/objfm_trigger_02_common_cause:examples/objfm_trigger_common:$PYTHONPATH" uv run cod3s-isimu --factory objfm_trigger_02_common_cause:build_system`.
- `examples/objfm_trigger_03_async_repair/` — same setup as #02; the test sequence uses `p` to re-plan one target's repair to a later date, demonstrating that target repair clocks are independent. Run: `PYTHONPATH="examples/objfm_trigger_03_async_repair:examples/objfm_trigger_common:$PYTHONPATH" uv run cod3s-isimu --factory objfm_trigger_03_async_repair:build_system`.
- `examples/objfm_trigger_04_exp_manual/` — exponential laws, two targets. The operator drives the timeline via `p` (no auto-sampling in interactive mode). Run: `PYTHONPATH="examples/objfm_trigger_04_exp_manual:$PYTHONPATH" uv run cod3s-isimu --factory objfm_trigger_04_exp_manual:build_system`.
- `examples/objfm_trigger_05_block_retrigger/` — same setup as #02; verifies a *non-event* — the ObjFM cannot re-trigger while a target is still in occ (`failure_cond` blocks it). Run: `PYTHONPATH="examples/objfm_trigger_05_block_retrigger:examples/objfm_trigger_common:$PYTHONPATH" uv run cod3s-isimu --factory objfm_trigger_05_block_retrigger:build_system`.

Scenarios 2, 3, and 5 share the same underlying system topology; the common build code lives in `examples/objfm_trigger_common/objfm_trigger_common.py` so the three scenario files are pure documentation walkthroughs of distinct interactive test sequences.

### Instantaneous transitions (probabilistic branching) demos

Two scenarios exercising the inst pending UX delivered by `cod3s-isimu` 0.3.0+. The fireable panel switches to a tree view at every instant where at least one inst transition is pending; the user picks branches and presses `s` to submit them all atomically.

- `examples/inst_coin_demo/inst_coin_demo.py` — single component, one 2-branch inst transition (`heads`/`tails`), `delay(1)` re-arms the toss. Smallest possible walk-through of the tree picker. Run: `PYTHONPATH="examples/inst_coin_demo:$PYTHONPATH" uv run cod3s-isimu --factory inst_coin_demo:build_system`.
- `examples/inst_panne_demo/inst_panne_demo.py` — two pumps, each with a 3-branch inst (`panne_severe` 0.05 / `panne_legere` 0.15 / `ok` 0.80) and per-branch effects on a `severity` integer. Both inst pendings start simultaneously at t=0, demonstrating the multi-pending atomic-submit UX. Recovery delays differ per landing state (10 / 5 / 1) so the pumps drift in and out of synchronisation as the simulation progresses. Run: `PYTHONPATH="examples/inst_panne_demo:$PYTHONPATH" uv run cod3s-isimu --factory inst_panne_demo:build_system`.
