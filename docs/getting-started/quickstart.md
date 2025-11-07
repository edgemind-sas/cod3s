# Quick Start Guide

This guide will help you get started with COD3S by walking through a simple example of creating components, building a system, and running a basic simulation.

## Prerequisites

Make sure you have COD3S installed. If not, follow the [Installation Guide](installation.md).

## Your First COD3S Model

Let's create a simple system with two pumps and analyze their reliability.

### Step 1: Import COD3S

```python
import cod3s
```

### Step 2: Create a Knowledge Base

The knowledge base stores component templates that can be reused across different systems.

```python
# Create a knowledge base
kb = cod3s.kb.ComponentClass(
    name="Pump",
    description="A centrifugal pump component",
    metadata={
        "type": "pump",
        "manufacturer": "Generic"
    }
)
```

### Step 3: Define Component Behavior

Let's add some basic failure behavior to our pump:

```python
# Create a pump component class with failure modes
pump_class = cod3s.kb.ComponentClass(
    name="Pump",
    description="A pump with failure modes",
    automata=[
        {
            "name": "operational_state",
            "states": [
                {"name": "working", "initial": True},
                {"name": "failed"}
            ],
            "transitions": [
                {
                    "name": "failure",
                    "source": "working",
                    "target": "failed",
                    "occurrence_law": {
                        "cls": "exp",
                        "rate": 0.001  # failures per hour
                    }
                },
                {
                    "name": "repair",
                    "source": "failed", 
                    "target": "working",
                    "occurrence_law": {
                        "cls": "exp",
                        "rate": 0.1  # repairs per hour
                    }
                }
            ]
        }
    ]
)
```

### Step 4: Create a System

Now let's create a system with two pumps in parallel:

```python
# Create a system
system = cod3s.system.System(
    name="PumpingSystem",
    description="A system with two parallel pumps"
)

# Add pump instances to the system
pump1 = pump_class.create_instance(
    name="pump_01",
    description="Primary pump"
)

pump2 = pump_class.create_instance(
    name="pump_02", 
    description="Secondary pump"
)

# Add components to system
system.components = [pump1, pump2]
```

### Step 5: Define System Indicators

Let's define some indicators to monitor system performance:

```python
# System availability indicator
system_available = cod3s.pycatshoo.indicator.PycFunIndicator(
    name="system_availability",
    description="System is available if at least one pump works",
    fun=lambda: (
        system.get_component("pump_01").get_state("operational_state") == "working" or
        system.get_component("pump_02").get_state("operational_state") == "working"
    )
)

# Add indicator to system
system.indicators = [system_available]
```

### Step 6: Convert to Simulation Backend

Convert the system to PyCATSHOO for simulation:

```python
# Convert to PyCATSHOO system
pyc_system = system.to_bkd_pycatshoo()
```

### Step 7: Run a Simulation

Set up and run a Monte Carlo simulation:

```python
# Create simulation parameters
simu_params = cod3s.pycatshoo.system.PycMCSimulationParam(
    nb_runs=1000,
    schedule=[
        cod3s.pycatshoo.system.InstantLinearRange(
            start=0,
            end=8760,  # One year in hours
            nvalues=100
        )
    ],
    time_unit="h"
)

# Create and run study
study = cod3s.pycatshoo.study.PycStudy(
    system_model=pyc_system,
    simu_params=simu_params
)

# Run the simulation
study.prepare_simu()
results = study.run_simu()
study.postproc_simu()
```

### Step 8: Analyze Results

```python
# Get availability results
availability_results = study.get_indicator_results("system_availability")

# Print average availability
print(f"Average system availability: {availability_results.mean():.3f}")

# Plot results over time
import plotly.graph_objects as go

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=availability_results.index,
    y=availability_results.values,
    mode='lines',
    name='System Availability'
))

fig.update_layout(
    title='System Availability Over Time',
    xaxis_title='Time (hours)',
    yaxis_title='Availability',
    yaxis=dict(range=[0, 1])
)

fig.show()
```

## Complete Example

Here's the complete code for the example above:

```python
import cod3s

# Create pump component class
pump_class = cod3s.kb.ComponentClass(
    name="Pump",
    description="A pump with failure modes",
    automata=[
        {
            "name": "operational_state",
            "states": [
                {"name": "working", "initial": True},
                {"name": "failed"}
            ],
            "transitions": [
                {
                    "name": "failure",
                    "source": "working",
                    "target": "failed",
                    "occurrence_law": {"cls": "exp", "rate": 0.001}
                },
                {
                    "name": "repair",
                    "source": "failed", 
                    "target": "working",
                    "occurrence_law": {"cls": "exp", "rate": 0.1}
                }
            ]
        }
    ]
)

# Create system
system = cod3s.system.System(name="PumpingSystem")

# Add components
system.components = [
    pump_class.create_instance("pump_01"),
    pump_class.create_instance("pump_02")
]

# Convert and simulate
pyc_system = system.to_bkd_pycatshoo()

# Set up simulation
simu_params = cod3s.pycatshoo.system.PycMCSimulationParam(
    nb_runs=1000,
    schedule=[cod3s.pycatshoo.system.InstantLinearRange(0, 8760, 100)]
)

# Run study
study = cod3s.pycatshoo.study.PycStudy(pyc_system, simu_params)
study.prepare_simu()
results = study.run_simu()
study.postproc_simu()
```

## What's Next?

Now that you've created your first COD3S model, you can:

1. **Learn Core Concepts**: Read about [COD3S concepts](concepts.md) to understand the framework better
2. **Explore Components**: Learn more about [component modeling](../user-guide/components.md)
3. **Build Complex Systems**: Discover how to create [complex systems](../user-guide/systems.md)
4. **Advanced Simulation**: Explore [simulation capabilities](../user-guide/simulation.md)
5. **Follow Tutorials**: Try the [hands-on tutorials](../tutorials/basic-component.md)

## Common Patterns

### Creating Reusable Components

```python
# Define a generic component template
generic_component = cod3s.kb.ComponentClass(
    name="GenericComponent",
    variables=[
        {"name": "status", "type": "discrete", "values": ["ok", "degraded", "failed"]}
    ],
    automata=[
        {
            "name": "health_state",
            "states": [
                {"name": "healthy", "initial": True},
                {"name": "degraded"},
                {"name": "failed"}
            ]
        }
    ]
)
```

### System-Level Indicators

```python
# Define system-level performance indicators
system_performance = cod3s.pycatshoo.indicator.PycAttrIndicator(
    name="system_performance",
    component="system",
    var="performance_level",
    operator=">=",
    value_test=0.8
)
```

### Failure Mode Analysis

```python
# Add failure modes to components
failure_mode = cod3s.pycatshoo.component.ObjFMExp(
    name="pump_failure",
    target_components=["pump_01", "pump_02"],
    failure_param_name="failure_rate"
)
```

This quick start guide should give you a solid foundation for using COD3S. For more detailed information, explore the other sections of this documentation.
