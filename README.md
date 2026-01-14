# COD3S - COmplex Dynamic Stochastic System Simulation

[![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub Issues](https://img.shields.io/github/issues/edgemind-sas/cod3s)](https://github.com/edgemind-sas/cod3s/issues)

> A Python library for modeling and simulating complex industrial systems using Piecewise Deterministic Markov Processes (PDMP).

COD3S provides a comprehensive framework for building reusable component libraries to model complex industrial systems for simulation and reliability assessment. The library offers a generic formalism to describe components and systems, with seamless integration to simulation engines like PyCATSHOO for quantitative analyses.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Examples](#examples)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [Citation](#citation)

## Features

- **🎯 Generic Component Modeling**: Create reusable component libraries with standardized interfaces and behaviors
- **🏗️ System Architecture Builder**: Construct complex systems by connecting components with well-defined interfaces
- **🎲 Monte Carlo Simulation**: Seamless integration with PyCATSHOO for stochastic simulation using PDMP (Piecewise Deterministic Markov Processes)
- **🔧 Failure Mode Analysis**: Built-in support for modeling reliability, failure modes, and maintenance strategies
- **📊 Custom Indicators**: Define flexible system-level and component-level performance indicators
- **✅ Pydantic-based**: Leverages Pydantic v2 for robust data validation, serialization, and type safety
- **📈 Results Analysis**: Comprehensive tools for analyzing simulation results and event sequences

## Installation

### Prerequisites

- Python >= 3.9, < 3.12
- pip or uv package manager

### Using pip

```bash
pip install cod3s
```

### Using uv (recommended for development)

```bash
# Install uv if you haven't already
pip install uv

# Install cod3s
uv pip install cod3s
```

### From Source

```bash
git clone https://github.com/edgemind-sas/cod3s.git
cd cod3s
pip install -e .
```

## Quick Start

Here's a minimal example to get you started with COD3S:

```python
from cod3s.kb import ComponentClass
from cod3s.system import System
from cod3s.pycatshoo.automaton import (
    PycAutomaton, PycState, PycTransition, ExpOccDistribution
)
from cod3s.pycatshoo.study import PycStudy, PycMCSimulationParam

# 1. Create a component class with reliability model
pump_automaton = PycAutomaton(
    name="reliability",
    states=[
        PycState(id="working", label="Working"),
        PycState(id="failed", label="Failed"),
    ],
    transitions=[
        PycTransition(
            name="failure",
            source="working",
            target="failed",
            occ_law=ExpOccDistribution(rate=1/8760)  # MTTF = 1 year
        ),
        PycTransition(
            name="repair",
            source="failed",
            target="working",
            occ_law=ExpOccDistribution(rate=1/24)  # MTTR = 24 hours
        ),
    ],
    initial_state="working"
)

pump_class = ComponentClass(
    name="Pump",
    label="Industrial Pump",
    description="Pump with exponential failure and repair",
    automata=[pump_automaton]
)

# 2. Build a system
system = System(name="pumping_system")
system.add_component(
    kb=[pump_class],
    class_name="Pump",
    instance_name="main_pump"
)

# 3. Convert to simulation backend
pyc_system = system.to_bkd_pycatshoo()

# 4. Run Monte Carlo simulation
simu_params = PycMCSimulationParam(
    nb_runs=1000,
    time_unit="h",
    max_time=8760,  # 1 year
    schedule=[8760]
)

study = PycStudy(
    system_model=pyc_system,
    simu_params=simu_params,
    name="Pump Reliability Analysis"
)

study.prepare_simu()
results = study.postproc_simu()

print(f"Simulation completed with {simu_params.nb_runs} runs")
```

## Examples

### Creating a Knowledge Base

Define reusable component templates:

```python
from cod3s.kb import KB, ComponentClass, AttributeTemplate, InterfaceTemplate

# Create a knowledge base
kb = KB(name="industrial_components")

# Define component attributes
flow_rate_attr = AttributeTemplate(
    name="flow_rate",
    attr_type="float",
    default=100.0,
    unit="m3/h"
)

# Define component interfaces
inlet_interface = InterfaceTemplate(
    name="inlet",
    interface_type="fluid",
    direction="in"
)

outlet_interface = InterfaceTemplate(
    name="outlet",
    interface_type="fluid",
    direction="out"
)

# Create a component class
pump = ComponentClass(
    name="CentrifugalPump",
    label="Centrifugal Pump",
    description="Industrial centrifugal pump",
    attributes=[flow_rate_attr],
    interfaces=[inlet_interface, outlet_interface]
)

kb.add_component_class(pump)
```

### Building a System with Connected Components

```python
from cod3s.system import System, Connection

# Create system
system = System(name="water_distribution")

# Add components
system.add_component(kb, "CentrifugalPump", "pump_1", flow_rate=150.0)
system.add_component(kb, "CentrifugalPump", "pump_2", flow_rate=150.0)
system.add_component(kb, "Tank", "storage_tank", capacity=1000.0)

# Connect components
system.add_connection(
    Connection(
        source_component="pump_1",
        source_interface="outlet",
        target_component="storage_tank",
        target_interface="inlet"
    )
)
```

### Setting Up Automata with Failure Modes

```python
from cod3s.pycatshoo.automaton import (
    PycAutomaton, PycState, PycTransition,
    ExpOccDistribution, DelayOccDistribution
)

# Define states
states = [
    PycState(id="operational", label="Operational"),
    PycState(id="degraded", label="Degraded"),
    PycState(id="failed", label="Failed"),
    PycState(id="maintenance", label="Under Maintenance")
]

# Define transitions with different occurrence laws
transitions = [
    # Random failure (exponential)
    PycTransition(
        name="random_failure",
        source="operational",
        target="failed",
        occ_law=ExpOccDistribution(rate=1/10000)
    ),
    # Degradation (exponential)
    PycTransition(
        name="degradation",
        source="operational",
        target="degraded",
        occ_law=ExpOccDistribution(rate=1/5000)
    ),
    # Repair (deterministic)
    PycTransition(
        name="repair",
        source="failed",
        target="operational",
        occ_law=DelayOccDistribution(time=48)
    ),
    # Scheduled maintenance (deterministic)
    PycTransition(
        name="scheduled_maintenance",
        source="operational",
        target="maintenance",
        occ_law=DelayOccDistribution(time=4380)  # Every 6 months
    ),
    # Maintenance completion
    PycTransition(
        name="maintenance_complete",
        source="maintenance",
        target="operational",
        occ_law=DelayOccDistribution(time=8)
    )
]

# Create automaton
reliability_automaton = PycAutomaton(
    name="advanced_reliability",
    states=states,
    transitions=transitions,
    initial_state="operational"
)
```

### Defining and Using Indicators

```python
from cod3s.pycatshoo.indicator import PycVarIndicator, PycFunIndicator

# Component-level indicator
pump_availability = PycVarIndicator(
    name="pump_availability",
    component="main_pump",
    var="working",
    operator="==",
    value_test=True
)

# System-level indicator using custom function
def system_availability(system):
    """System is available if at least one pump is working"""
    return (system.pump_1.working or system.pump_2.working)

system_avail_indicator = PycFunIndicator(
    name="system_availability",
    fun=system_availability
)

# Add indicators to system
pyc_system.add_indicator(**pump_availability.model_dump())
pyc_system.add_indicator(**system_avail_indicator.model_dump())
```

### Analyzing Results

```python
from cod3s.pycatshoo.sequence import SequenceAnalyser

# Run simulation
study.prepare_simu()
results = study.postproc_simu()

# Analyze indicator results
availability = results["system_availability"]
print(f"Mean availability: {availability.mean():.4f}")
print(f"Std deviation: {availability.std():.4f}")

# Analyze event sequences
analyser = SequenceAnalyser.from_pyc_system(pyc_system)
print(f"Total sequences: {analyser.nb_sequences}")

# Group similar sequences
grouped = analyser.group_sequences(inplace=False)
print(f"Unique sequences: {grouped.nb_sequences}")

# Show top failure sequences
grouped.show_sequences(max_sequences=5, max_events=3)
```

For a complete working example, see [`examples/basic_example.py`](examples/basic_example.py).

## Architecture

COD3S is organized around a multi-layer architecture:

### Core Layer

- **ObjCOD3S**: Base class providing common functionality for all COD3S objects
- **Core primitives**: Fundamental data structures and validation logic

### Knowledge Base Layer

- **KB (Knowledge Base)**: Repository for storing component templates and specifications
- **ComponentClass**: Templates defining component types with attributes, interfaces, and behaviors
- **Templates**: AttributeTemplate, InterfaceTemplate for standardized component definitions

### System Layer

- **System**: Container for component instances and connections
- **ComponentInstance**: Instantiated components with specific parameter values
- **Connection**: Defines relationships between component interfaces

### Backend Layer

- **PyCATSHOO Integration**: Translates COD3S models to PyCATSHOO format for simulation
- **Automaton**: Stochastic automata with states and probabilistic transitions
- **Study**: Manages simulation execution and result collection
- **Indicator**: Performance metrics and system measurements
- **Sequence Analysis**: Tools for analyzing event sequences from simulations

```
┌─────────────────────────────────────┐
│         Application Layer           │
│    (Your System Models)             │
└─────────────────────────────────────┘
                 │
┌─────────────────────────────────────┐
│          System Layer               │
│  System │ Connection │ Instance     │
└─────────────────────────────────────┘
                 │
┌─────────────────────────────────────┐
│      Knowledge Base Layer           │
│    KB │ ComponentClass │ Templates  │
└─────────────────────────────────────┘
                 │
┌─────────────────────────────────────┐
│           Core Layer                │
│         ObjCOD3S Base               │
└─────────────────────────────────────┘
                 │
┌─────────────────────────────────────┐
│        Backend Layer                │
│  PyCATSHOO │ Simulation │ Analysis  │
└─────────────────────────────────────┘
```

## Documentation

- **📚 Full Documentation**: [MkDocs Site](https://edgemind-sas.github.io/cod3s/) (Coming soon)
- **🔍 API Reference**: Comprehensive API documentation with all classes and methods
- **📖 Tutorials**: Step-by-step guides for common use cases
- **💡 Examples**: Ready-to-run code examples in the [`examples/`](examples/) directory

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/edgemind-sas/cod3s.git
cd cod3s

# Install with development dependencies using uv
uv pip install -e ".[dev]"

# Or using pip
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cod3s --cov-report=html

# Run specific test file
pytest tests/core/test_system_001.py
```

### Code Quality Tools

COD3S uses several tools to maintain code quality:

```bash
# Format code with black
black cod3s/

# Sort imports with isort
isort cod3s/

# Lint with flake8
flake8 cod3s/

# Type checking with mypy
mypy cod3s/

# Run all quality checks
black cod3s/ && isort cod3s/ && flake8 cod3s/ && mypy cod3s/
```

### Project Structure

```
cod3s/
├── cod3s/              # Main package
│   ├── core.py         # Core functionality
│   ├── kb.py           # Knowledge Base
│   ├── system.py       # System modeling
│   ├── pycatshoo/      # PyCATSHOO backend
│   └── utils/          # Utility functions
├── examples/           # Example scripts
├── tests/              # Test suite
├── docs/               # Documentation
└── pyproject.toml      # Project configuration
```

## Contributing

Contributions are welcome! We appreciate your help in making COD3S better.

### How to Contribute

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a feature branch**: `git checkout -b feature/your-feature-name`
4. **Make your changes** and add tests
5. **Run tests and quality checks** to ensure everything passes
6. **Commit your changes**: `git commit -m "Add your feature"`
7. **Push to your fork**: `git push origin feature/your-feature-name`
8. **Open a Pull Request** on GitHub

### Contribution Guidelines

- Follow the existing code style (black formatting, isort for imports)
- Add tests for new features
- Update documentation as needed
- Ensure all tests pass before submitting PR
- Write clear commit messages

For more details, see our [Contributing Guidelines](CONTRIBUTING.md) (coming soon).

## License

COD3S is released under the **MIT License**. See the [LICENSE](LICENSE) file for full details.

Copyright (c) 2024 EdgeMind

## Citation

If you use COD3S in your research or projects, please cite:

```bibtex
@software{cod3s2024,
  title = {COD3S: COmplex Dynamic Stochastic System Simulation},
  author = {Donat, Roland},
  year = {2024},
  url = {https://github.com/edgemind-sas/cod3s},
  version = {1.0.32}
}
```

## Use Cases

COD3S is particularly well-suited for:

- **⚡ Industrial System Modeling**: Power plants, manufacturing systems, water distribution networks
- **🔧 Reliability Engineering**: Component reliability analysis, system availability studies
- **⚠️ Risk Assessment**: Quantitative risk analysis using Monte Carlo simulation and PDMP
- **🏗️ System Design**: Exploring different architectures, redundancy strategies, and configurations
- **🔬 Research**: Academic research in reliability theory, stochastic processes, and industrial engineering

## Support

- **Issues**: Report bugs or request features at [GitHub Issues](https://github.com/edgemind-sas/cod3s/issues)
- **Discussions**: Join conversations at [GitHub Discussions](https://github.com/edgemind-sas/cod3s/discussions)
- **Email**: Contact the maintainers at roland.donat@edgemind.net

---

**Built with ❤️ by [EdgeMind](https://github.com/edgemind-sas)**
