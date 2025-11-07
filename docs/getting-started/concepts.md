# Core Concepts

This section introduces the fundamental concepts of COD3S and the underlying mathematical framework based on Piecewise Deterministic Markov Processes (PDMPs).

## Overview

COD3S provides a high-level abstraction layer over simulation engines like PyCATSHOO to model complex industrial systems. The framework is built around several key concepts that work together to create comprehensive system models.

## Mathematical Foundation: Piecewise Deterministic Markov Processes

COD3S is based on the theoretical framework of **Piecewise Deterministic Markov Processes (PDMPs)**, which can model systems that exhibit both continuous deterministic evolution and discrete stochastic jumps.

### PDMP Definition

A PDMP is characterized by:

- A finite set of modes $M$ where the system can operate
- For each mode $m \in M$, a region $\Omega_m \subset \mathbb{R}^d$ where continuous variables evolve
- The global state space: $E = \bigcup_{m \in M} E_m$ where $E_m = \{m\} \times \Omega_m$

### Continuous Evolution

Within each mode $m$, the continuous state variables evolve deterministically according to:

$$\frac{dx(t)}{dt} = f_m(t, x(t))$$

where $x(t + s) = \Phi_m(s, x(t))$ is the solution of the differential equation system.

### Discrete Jumps

The system can experience two types of jumps:

#### 1. Spontaneous Jumps

These occur randomly according to a transition rate $\lambda_m(x)$. The probability of a spontaneous jump before time $t$ is:

$$P(T < t | Z = (x, m)) = \begin{cases}
1 - e^{-\int_0^t \lambda_m(x(u)) du} & \text{if } t < t^*(x, m) \\
1 & \text{if } t \geq t^*(x, m)
\end{cases}$$

where $t^*(x, m) = \inf\{t > 0 : \Phi_m(t, x) \in \partial\Omega_m\}$ is the hitting time of the boundary.

#### 2. Forced Jumps

These occur when the continuous trajectory hits the boundary $\partial\Omega_m$ of the current region.

### Jump Probabilities

- **Spontaneous jump** to mode $m'$: $K_{x,m}(m') = \frac{\lambda_{m \to m'}(x)}{\lambda_m(x)}$
- **Forced jump** to mode $m''$: $K_m(m'') = \gamma_{m \to m''}$

where $\lambda_m(x) = \sum_{n \in M, n \neq m} \lambda_{m \to n}(x)$

## COD3S Core Concepts

### 1. Components

Components are the fundamental building blocks of any system in COD3S. They represent physical or logical entities with:

- **State Variables**: Continuous or discrete variables that characterize the component's state
- **Automata**: Finite state machines that define the component's behavior
- **Message Boxes**: Communication interfaces with other components
- **PDMP Contributions**: Differential equations and boundary conditions

```python
# Example: Pump component with failure behavior
pump_class = cod3s.kb.ComponentClass(
    name="Pump",
    variables=[
        {"name": "flow_rate", "type": "continuous", "initial": 100.0},
        {"name": "status", "type": "discrete", "values": ["working", "failed"]}
    ],
    automata=[{
        "name": "operational_state",
        "states": [
            {"name": "working", "initial": True},
            {"name": "failed"}
        ],
        "transitions": [{
            "name": "failure",
            "source": "working",
            "target": "failed",
            "occurrence_law": {"cls": "exp", "rate": 0.001}  # λ = 0.001 h⁻¹
        }]
    }]
)
```

### 2. Automata and States

Automata define the discrete behavior of components using finite state machines:

- **States**: Discrete modes of operation (e.g., "working", "failed", "maintenance")
- **Transitions**: Rules for changing between states
- **Conditions**: Boolean expressions that enable transitions
- **Occurrence Laws**: Probability distributions for transition timing

#### Transition Types

1. **Deterministic Transitions**: Triggered immediately when conditions are met
2. **Stochastic Transitions**: Follow probability distributions:
   - **Exponential**: $P(T \leq t) = 1 - e^{-\lambda t}$ (memoryless)
   - **Delay**: Fixed time delay $\Delta t$
   - **Instantaneous**: Immediate with given probabilities

### 3. Variables and References

#### Variables
Internal state variables that belong to a component:
- **Continuous**: Real-valued variables (temperature, pressure, flow rate)
- **Discrete**: Categorical variables (status, mode, configuration)

#### References
External information receptacles that receive values from other components:
- Act as "sensors" for inter-component communication
- Support aggregation operations (sum, product, logical AND/OR)

### 4. Message Boxes and Communication

Message boxes implement the encapsulation principle by providing controlled access to component internals:

- **Export Slots**: Expose internal variables to other components
- **Import Slots**: Receive external values into references
- **Communication Architecture**: Defines system-level information flow

```python
# Message box example
messageBox = component.addMessageBox("sensor_data")
messageBox.addExport(component.temperature, "temp_reading")
messageBox.addImport(component.external_temp, "ambient_temp")
```

### 5. PDMP Manager

The PDMP Manager coordinates the continuous-discrete evolution:

#### Continuous Variables Management
- **ODE Variables**: Governed by differential equations
- **Explicit Variables**: Computed from algebraic expressions

#### Equation Methods
Define the system's continuous dynamics:

```python
def pdmp_equation_method(self):
    # Energy balance: dT/dt = (P_in - P_loss) / (m * c_p)
    self.temperature.setDvdtODE(
        (self.power_input.sumValue() - self.heat_loss.value()) / 
        (self.mass.value() * self.specific_heat.value())
    )
```

#### Boundary Checking
Detect when continuous variables reach critical thresholds:

```python
def boundary_checker(self):
    # Return negative if boundary crossed
    if self.temperature.value() > self.max_temperature.value():
        return -1.0  # Forbidden region
    return 1.0  # Valid region
```

### 6. Systems and Architecture

Systems are collections of interconnected components that form complete models:

- **Component Instances**: Specific realizations of component classes
- **Connections**: Links between component message boxes
- **System-Level Behavior**: Emergent properties from component interactions

### 7. Indicators and Measurements

Indicators define what to measure during simulation:

#### Types of Indicators

1. **Variable Indicators**: Monitor component variables
   ```python
   temp_indicator = PycVarIndicator(
       component="reactor",
       var="temperature",
       operator=">",
       value_test=350.0  # Temperature > 350°C
   )
   ```

2. **Function Indicators**: Custom boolean functions
   ```python
   system_available = PycFunIndicator(
       fun=lambda: pump1.is_working() or pump2.is_working()
   )
   ```

3. **State Indicators**: Monitor automaton states
   ```python
   failure_indicator = PycSTIndicator(
       component="pump",
       state="failed"
   )
   ```

#### Statistical Measures

For each indicator, COD3S can compute:
- **Mean values**: $\mathbb{E}[I(t)]$
- **Standard deviation**: $\sqrt{\text{Var}[I(t)]}$
- **Quantiles**: Values $q_p$ such that $P(I(t) \leq q_p) = p$
- **Cumulative distributions**: $P(I(t) \leq x)$

### 8. Knowledge Base

The knowledge base stores reusable component templates:

- **Component Classes**: Generic component definitions
- **Parameterization**: Customizable component parameters
- **Inheritance**: Hierarchical component relationships
- **Validation**: Pydantic-based data validation

## Simulation Workflow

The typical COD3S simulation workflow follows these steps:

1. **Model Definition**: Create component classes and system architecture
2. **System Instantiation**: Build specific system instances
3. **Backend Translation**: Convert to PyCATSHOO simulation model
4. **Indicator Setup**: Define measurements and statistics
5. **Monte Carlo Simulation**: Run multiple stochastic realizations
6. **Post-Processing**: Analyze results and generate reports

### Monte Carlo Method

COD3S uses Monte Carlo simulation to estimate system performance:

$$\mathbb{E}[I] \approx \frac{1}{N} \sum_{i=1}^N I^{(i)}$$

where $I^{(i)}$ is the indicator value in the $i$-th simulation run.

The confidence interval for the estimate is:

$$\mathbb{E}[I] \pm z_{\alpha/2} \frac{\sigma}{\sqrt{N}}$$

where $z_{\alpha/2}$ is the critical value and $\sigma$ is the sample standard deviation.

## Advanced Concepts

### Failure Mode Modeling

COD3S provides specialized components for modeling failure modes:

```python
# Common cause failure affecting multiple components
ccf = ObjFMExp(
    name="common_cause_failure",
    target_components=["pump1", "pump2", "pump3"],
    failure_param_name="ccf_rate",
    order_max=2  # Up to 2 components can fail simultaneously
)
```

### Dependency Modeling

Components can have complex dependencies:
- **Functional Dependencies**: Component A needs Component B to operate
- **Shared Resources**: Multiple components compete for limited resources
- **Cascading Failures**: Failure of one component triggers others

### Performance Optimization

For large systems, COD3S provides optimization techniques:
- **Distributed Simulation**: Parallel execution across multiple cores
- **Importance Sampling**: Focus computational effort on rare events
- **Variance Reduction**: Techniques to improve statistical efficiency

## Integration with PyCATSHOO

COD3S acts as a high-level interface to PyCATSHOO, providing:

- **Automatic Translation**: Convert COD3S models to PyCATSHOO backend
- **Parameter Management**: Handle complex parameterization schemes
- **Result Processing**: Extract and format simulation results
- **Visualization**: Generate plots and reports from simulation data

This abstraction allows users to focus on system modeling rather than simulation implementation details, while still leveraging the powerful PDMP simulation capabilities of PyCATSHOO.
