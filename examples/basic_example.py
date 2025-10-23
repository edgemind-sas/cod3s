#!/usr/bin/env python3
"""
Basic COD3S Example - Simple Pump System

This example demonstrates the basic usage of COD3S to model
a simple pump system and run a reliability analysis.
"""

from cod3s.kb import ComponentClass
from cod3s.system import System
from cod3s.pycatshoo.automaton import (
    PycAutomaton, PycState, PycTransition,
    DelayOccDistribution, ExpOccDistribution
)
from cod3s.pycatshoo.study import PycStudy, PycMCSimulationParam
from cod3s.pycatshoo.indicator import PycVarIndicator, PycFunIndicator
from cod3s.pycatshoo.sequence import SequenceAnalyser


def create_pump_component():
    """Create a simple pump component with reliability model."""
    
    # Define pump states
    states = [
        PycState(id="working", label="Working"),
        PycState(id="failed", label="Failed"),
        PycState(id="maintenance", label="Under maintenance")
    ]
    
    # Define transitions
    transitions = [
        # Failure transition
        PycTransition(
            name="failure",
            source="working",
            target="failed",
            occ_law=ExpOccDistribution(rate=1/8760)  # MTTF = 1 year
        ),
        # Repair transition
        PycTransition(
            name="repair",
            source="failed",
            target="working",
            occ_law=DelayOccDistribution(time=24)  # MTTR = 24 hours
        ),
        # Scheduled maintenance
        PycTransition(
            name="scheduled_maintenance",
            source="working",
            target="maintenance",
            occ_law=DelayOccDistribution(time=4380)  # Every 6 months
        ),
        # Maintenance completion
        PycTransition(
            name="maintenance_complete",
            source="maintenance",
            target="working",
            occ_law=DelayOccDistribution(time=8)  # 8 hours maintenance
        )
    ]
    
    # Create automaton
    reliability_automaton = PycAutomaton(
        name="pump_reliability",
        states=states,
        transitions=transitions,
        initial_state="working"
    )
    
    # Create component class
    return ComponentClass(
        name="SimplePump",
        label="Simple Pump",
        description="Basic pump with reliability model",
        parameters={
            "flow_rate": {"type": "float", "default": 100.0, "unit": "m3/h"},
            "pressure": {"type": "float", "default": 5.0, "unit": "bar"}
        },
        automata=[reliability_automaton]
    )


def create_system():
    """Create a simple pumping system."""
    
    # Create component library
    pump_class = create_pump_component()
    kb = [pump_class]
    
    # Create system
    system = System(name="simple_pumping_system")
    
    # Add main pump
    system.add_component(
        kb=kb,
        class_name="SimplePump",
        instance_name="main_pump",
        flow_rate=150.0,
        pressure=6.0
    )
    
    # Add backup pump
    system.add_component(
        kb=kb,
        class_name="SimplePump",
        instance_name="backup_pump",
        flow_rate=150.0,
        pressure=6.0
    )
    
    return system


def define_indicators():
    """Define system indicators."""
    
    # System availability function
    def system_availability(system):
        """System is available if at least one pump is working."""
        return system.main_pump.working or system.backup_pump.working
    
    # Create indicators
    indicators = [
        # System-level indicator
        PycFunIndicator(
            name="system_availability",
            fun=system_availability
        ),
        
        # Component-level indicators
        PycVarIndicator(
            name="main_pump_availability",
            component="main_pump",
            var="working",
            operator="==",
            value_test=True
        ),
        
        PycVarIndicator(
            name="backup_pump_availability",
            component="backup_pump",
            var="working",
            operator="==",
            value_test=True
        )
    ]
    
    return indicators


def run_simulation(system, indicators):
    """Run Monte Carlo simulation."""
    
    print("Converting system to PyCATSHOO format...")
    pyc_system = system.to_bkd_pycatshoo()
    
    # Add indicators
    print("Adding indicators...")
    for indicator in indicators:
        pyc_system.add_indicator(**indicator.model_dump())
    
    # Configure simulation
    simu_params = PycMCSimulationParam(
        nb_runs=1000,
        time_unit="h",
        seed=42,
        schedule=[720, 2160, 4380, 8760],  # Monthly, quarterly, semi-annual, annual
        max_time=8760  # 1 year simulation
    )
    
    # Create and run study
    print(f"Running simulation ({simu_params.nb_runs} runs)...")
    study = PycStudy(
        system_model=pyc_system,
        simu_params=simu_params,
        name="Simple Pump System Analysis"
    )
    
    study.prepare_simu()
    results = study.postproc_simu()
    
    return results, study, pyc_system


def analyze_results(results):
    """Analyze simulation results."""
    
    print("\n" + "="*50)
    print("SIMULATION RESULTS")
    print("="*50)
    
    # System availability
    system_avail = results["system_availability"]
    print(f"System Availability: {system_avail.mean():.4f} ± {system_avail.std():.4f}")
    
    # Component availability
    main_pump_avail = results["main_pump_availability"]
    backup_pump_avail = results["backup_pump_availability"]
    
    print(f"Main Pump Availability: {main_pump_avail.mean():.4f}")
    print(f"Backup Pump Availability: {backup_pump_avail.mean():.4f}")
    
    # Calculate improvement from redundancy
    single_pump_avail = main_pump_avail.mean()  # Approximation
    redundancy_improvement = (system_avail.mean() - single_pump_avail) / single_pump_avail * 100
    
    print(f"Redundancy Improvement: {redundancy_improvement:.1f}%")


def analyze_sequences(pyc_system):
    """Analyze failure sequences."""
    
    print("\n" + "="*50)
    print("SEQUENCE ANALYSIS")
    print("="*50)
    
    # Extract sequences
    print("Extracting event sequences...")
    analyser = SequenceAnalyser.from_pyc_system(pyc_system)
    
    print(f"Found {analyser.nb_sequences} sequences")
    
    # Group similar sequences
    grouped = analyser.group_sequences(inplace=False)
    print(f"After grouping: {grouped.nb_sequences} unique sequences")
    
    # Show top sequences
    print("\nTop failure sequences:")
    grouped.show_sequences(max_sequences=5, max_events=3)
    
    return grouped


def main():
    """Main function to run the example."""
    
    print("COD3S Basic Example - Simple Pump System")
    print("="*50)
    
    # Create system
    print("Creating system...")
    system = create_system()
    print(f"Created system with {len(system.components)} components")
    
    # Define indicators
    indicators = define_indicators()
    print(f"Defined {len(indicators)} indicators")
    
    # Run simulation
    results, study, pyc_system = run_simulation(system, indicators)
    
    # Analyze results
    analyze_results(results)
    
    # Analyze sequences
    sequence_analyser = analyze_sequences(pyc_system)
    
    print("\n" + "="*50)
    print("EXAMPLE COMPLETED SUCCESSFULLY")
    print("="*50)
    print("\nNext steps:")
    print("1. Modify component parameters to see their impact")
    print("2. Add more complex failure modes")
    print("3. Try different system configurations")
    print("4. Explore maintenance strategies")


if __name__ == "__main__":
    main()
