# COD3S Documentation

Welcome to the COD3S (COmplex Dynamic Stochastic System Simulation) library documentation.

## What is COD3S?

COD3S is a Python library designed for modeling and simulating complex industrial systems. It provides a generic formalism to describe components and systems, along with tools to translate system descriptions into simulation frameworks like PyCATSHOO for quantitative analyses.

## Key Features

- **Generic Component Modeling**: Create reusable component libraries with standardized interfaces
- **System Architecture**: Build complex systems by connecting components together
- **Simulation Integration**: Seamless integration with PyCATSHOO for Monte Carlo simulations
- **Failure Mode Analysis**: Built-in support for modeling failure modes and reliability analysis
- **Flexible Indicators**: Define custom indicators for system monitoring and analysis
- **Pydantic-based**: Leverages Pydantic v2 for robust data validation and serialization

## Quick Start

### Installation

```bash
pip install cod3s
```

### Basic Example

```python
import cod3s

# Create a knowledge base
kb = cod3s.kb.KnowledgeBase()

# Define a component class
component_class = cod3s.kb.ComponentClass(
    name="Pump",
    description="A basic pump component"
)

# Create a system
system = cod3s.system.System(name="MySystem")

# Add component instance to system
system.add_component(kb, "Pump", "pump_01")

# Convert to PyCATSHOO for simulation
pyc_system = system.to_bkd_pycatshoo()
```

## Architecture Overview

COD3S is organized around several key concepts:

- **Components**: Reusable building blocks that represent system elements
- **Systems**: Collections of connected components that form complete models
- **Knowledge Base**: Repository of component templates and specifications
- **Indicators**: Metrics and measurements for system analysis
- **Simulation**: Integration with external simulation engines

## Use Cases

COD3S is particularly well-suited for:

- **Industrial System Modeling**: Power plants, manufacturing systems, transportation networks
- **Reliability Analysis**: Failure mode modeling and system availability studies
- **Risk Assessment**: Quantitative risk analysis using Monte Carlo simulation
- **System Design**: Exploring different system architectures and configurations

## Getting Help

- **User Guide**: Step-by-step guides for common tasks
- **Tutorials**: Hands-on examples and case studies
- **API Reference**: Complete documentation of all classes and methods
- **Examples**: Ready-to-run code examples

## Contributing

COD3S is an open-source project. Contributions are welcome! Please see our contributing guidelines for more information.

## License

COD3S is released under the MIT License. See the [LICENSE](https://github.com/edgemind-sas/cod3s/blob/main/LICENSE) file for details.
