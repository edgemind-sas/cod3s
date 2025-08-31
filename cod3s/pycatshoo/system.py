"""
PyCATSHOO System Module

This module provides classes and utilities for building and managing PyCATSHOO systems.
It includes functionality for:

- Monte Carlo simulation parameters and execution
- System state management and transitions
- Component and indicator handling
- Interactive simulation sessions
- Data visualization and analysis

Key Classes:
    - PycSystem: Main system class for PyCATSHOO models
    - MCSimulationParam: Configuration for Monte Carlo simulations
    - InstantLinearRange: Utility for defining time ranges
    - PycMCSimulationParam: PyCATSHOO-specific simulation parameters

The module integrates with PyCATSHOO's backend while providing a more Pythonic interface
for system modeling and simulation management.
"""

import Pycatshoo as pyc
import pydantic
import numpy as np
import pandas as pd
import plotly.express as px
import typing
import itertools
import warnings
import re
from .indicator import (
    PycAttrIndicator,
    PycVarIndicator,
    PycSTIndicator,
    PycFunIndicator,
)
from .automaton import PycTransition
from .sequence import PycSequence
from .component import PycComponent
from .common import get_pyc_attr_list_name, get_pyc_simu_mode


def transition_to_indexed_dict(transitions):
    """Convert a list of transition objects to a list of dictionaries with indexed IDs.

    This function processes a list of transition objects and converts each one into a dictionary
    format with additional indexing information. It handles both single-state and multi-state
    transitions, adding appropriate indices for identification.

    Args:
        transitions (list): A list of transition objects that implement model_dump().
            Each transition should have a 'target' attribute that is either a single state
            or a list of states.

    Returns:
        list[dict]: A list of dictionaries where each dictionary contains:
            - trans_id (int): Index of the transition in the original list
            - state_index (int, optional): For multi-state transitions, index of the state
            - All fields from the original transition's model_dump()

    Example:
        >>> transitions = [
        ...     Transition(target=[State("S1"), State("S2")]),
        ...     None,  # Skipped in output
        ...     Transition(target=State("S3"))
        ... ]
        >>> result = transition_to_indexed_dict(transitions)
        >>> print(result)
        [
            {'trans_id': 0, 'state_index': 0, 'target': 'S1', ...},
            {'trans_id': 0, 'state_index': 1, 'target': 'S2', ...},
            {'trans_id': 2, 'target': 'S3', ...}
        ]

    Note:
        - None values in the input list are skipped
        - For transitions with multiple target states (occ_law == "inst"),
          each state gets its own dictionary with a unique state_index
    """
    trans_list = []
    for i, trans in enumerate(transitions):
        if not trans:
            continue
        if isinstance(trans.target, list):
            # case occ_law == "inst"
            for j, target_specs in enumerate(trans.target):
                trans_list.append(dict(trans_id=i, state_index=j, **trans.model_dump()))
        else:
            trans_list.append(dict(trans_id=i, **trans.model_dump()))

    return trans_list


class InstantLinearRange(pydantic.BaseModel):
    """A class representing a linear range of time instants for simulation.

    This class defines a linear sequence of time points between a start and end time,
    useful for specifying measurement or observation points in a simulation.

    Attributes:
        start (float): The starting time point of the range
        end (float): The ending time point of the range
        nvalues (int): Number of values to generate in the range

    Example:
        >>> range = InstantLinearRange(start=0, end=100, nvalues=5)
        >>> range.get_instants_list()
        [0.0, 25.0, 50.0, 75.0, 100.0]
    """

    start: float = pydantic.Field(..., description="Starting time point")
    end: float = pydantic.Field(..., description="Ending time point")
    nvalues: int = pydantic.Field(..., description="Number of time points to generate")

    def get_instants_list(self):
        """Generate a list of evenly spaced time instants.

        Returns:
            list[float]: A list of time points. If nvalues <= 1, returns [end],
                        otherwise returns nvalues evenly spaced points from start to end.
        """
        if self.nvalues <= 1:
            return [self.end]
        else:
            return list(np.linspace(self.start, self.end, self.nvalues))


class MCSimulationParam(pydantic.BaseModel):
    """Configuration parameters for Monte Carlo simulations.

    This class defines the parameters needed to run Monte Carlo simulations,
    including number of runs, measurement schedule, time units, and random seed.

    Attributes:
        nb_runs (int): Number of simulation runs to perform. Defaults to 1.
        schedule (List[Union[InstantLinearRange, float]]): List of time points or ranges
            at which to take measurements. Defaults to [100].
        time_unit (Optional[str]): Unit of time for the simulation (e.g., 'h', 'd', 'y').
            Defaults to None.
        seed (Any): Random seed for reproducible simulations. Defaults to None.

    Example:
        >>> params = MCSimulationParam(
        ...     nb_runs=1000,
        ...     schedule=[0, InstantLinearRange(start=0, end=100, nvalues=11)],
        ...     time_unit='h',
        ...     seed=42
        ... )
    """

    nb_runs: int = pydantic.Field(1, description="Number of simulation runs to perform")
    schedule: typing.List[typing.Union[InstantLinearRange, float]] = pydantic.Field(
        [100], description="List of measurement time points or ranges"
    )
    time_unit: typing.Optional[str] = pydantic.Field(
        None, description="Time unit for simulation (e.g., 'h', 'd', 'y')"
    )
    seed: typing.Any = pydantic.Field(
        None, description="Random seed for reproducibility"
    )

    def get_instants_list(self):
        """Generate a sorted list of all measurement time points.

        This method processes the schedule attribute to create a complete list of
        time points at which measurements should be taken. It handles both individual
        time points and InstantLinearRange objects.

        Returns:
            List[float]: Sorted list of all measurement time points.

        Example:
            >>> params = MCSimulationParam(schedule=[
            ...     0,
            ...     InstantLinearRange(start=0, end=10, nvalues=3),
            ...     15
            ... ])
            >>> params.get_instants_list()
            [0, 0, 5, 10, 15]
        """
        instants = []
        for sched in self.schedule:
            if isinstance(sched, InstantLinearRange):
                instants.extend(sched.get_instants_list())
            else:
                instants.append(sched)

        return sorted(instants)


class PycMCSimulationParam(MCSimulationParam):
    """PyCATSHOO-specific Monte Carlo simulation parameters.

    This class extends MCSimulationParam to provide PyCATSHOO-specific functionality
    for Monte Carlo simulations. Currently identical to the base class, but serves
    as an extension point for PyCATSHOO-specific features.

    Example:
        >>> params = PycMCSimulationParam(
        ...     nb_runs=100,
        ...     schedule=[0, 10, 20],
        ...     time_unit='h'
        ... )
    """

    pass


class PycSystem(pyc.CSystem):
    """A PyCATSHOO system class that manages components, indicators and simulation.

    This class extends PyCATSHOO's CSystem to provide a higher-level interface for:
    - Managing system components and their interactions
    - Handling simulation indicators and measurements
    - Controlling interactive simulation sessions
    - Processing and visualizing simulation results

    Attributes:
        indicators (dict): Dictionary of system indicators for measurements
        isimu_sequence (PycSequence): Sequence tracker for interactive simulation
        comp (dict): Dictionary of system components (populated by PycComponent.register)
    """

    def __init__(self, name):
        """Initialize a new PyCATSHOO system.

        Args:
            name (str): The name of the system
        """
        super().__init__(name)

        self.indicators = {}
        self.isimu_sequence = PycSequence()
        self.comp = {}  # Populated by PycComponent register method at init

    def add_component(self, **comp_specs):
        """Add a new component to the system.

        Creates a new component from specifications and adds it to the system.
        If a component with the same name already exists, returns None.

        Args:
            **comp_specs: Keyword arguments defining the component specifications.
                Must include a 'name' key.

        Returns:
            PycComponent: The newly created component, or None if component already exists.

        Warns:
            UserWarning: If a component with the same name already exists.
        """
        comp_name = comp_specs.get("name")

        if comp_name in self.comp:
            warnings.warn(f"Component {comp_name} already exists", UserWarning)
            return None
        else:
            comp_new = PycComponent.from_dict(**comp_specs)
            return comp_new

    def get_components(self, pattern="^.*$"):
        """Get components whose names match a regular expression pattern.

        Args:
            pattern (str): Regular expression pattern to match component names.
                Defaults to "^.*$" (matches all components).

        Returns:
            dict: Dictionary of {name: component} for components whose names match the pattern.
        """
        return {k: v for k, v in self.comp.items() if re.search(f"^({pattern})$", k)}

    def add_indicator(self, **indic_specs):
        """Add attribute-based indicators to the system.

        Creates indicators for component attributes matching specified patterns.
        Supports filtering by component name and attribute name using regex patterns.

        Args:
            **indic_specs: Indicator specifications including:
                component (str): Regex pattern for component names. Defaults to ".*"
                attr_name (str): Regex pattern for attribute names. Defaults to ".*"
                attr_type (str): Type of attribute to monitor
                Other kwargs are passed to PycAttrIndicator constructor

        Returns:
            list[PycAttrIndicator]: List of created indicators

        Example:
            >>> system.add_indicator(
            ...     component="pump.*",
            ...     attr_name="flow.*",
            ...     attr_type="variable"
            ... )
        """
        comp_pat = indic_specs.pop("component", ".*")
        attr_name_pat = indic_specs.pop("attr_name", ".*")
        attr_type = indic_specs.pop("attr_type")

        pyc_attr_list_name = get_pyc_attr_list_name(attr_type)

        indic_added_list = []
        for comp in self.components("#" + comp_pat, "#.*"):

            attr_list = [
                attr.basename()
                for attr in getattr(comp, pyc_attr_list_name)()
                if re.search(attr_name_pat, attr.basename())
            ]

            for attr in attr_list:
                # if indic_name:
                #     indic_name_cur = f"{indic_name}_{attr}"
                # else:
                #     if indic_name_pattern:
                #         if measure_name:
                #             indic_name_pattern = "{component}_{attr_name}_{measure}"
                #         else:
                #             indic_name_pattern = "{component}_{attr_name}"

                indic = PycAttrIndicator(
                    # name=indic_name_cur,
                    # name_pattern=indic_name_pattern,
                    component=comp.basename(),
                    attr_type=attr_type,
                    attr_name=attr,
                    **indic_specs,
                )

                # if "MES" in comp_pat:
                #     ipdb.set_trace()

                self.indicators[indic.name] = indic

                indic_added_list.append(indic)

        return indic_added_list

    def add_indicator_var(self, **indic_specs):
        """Add variable-based indicators to the system.

        Creates indicators for component variables matching specified patterns.
        Supports statistical measurements (mean, std, etc.) of variable values.

        Args:
            **indic_specs: Indicator specifications including:
                stats (list[str]): Statistical measures to compute. Defaults to ["mean"]
                component (str): Regex pattern for component names. Defaults to ".*"
                var (str): Regex pattern for variable names. Defaults to ".*"
                name (str): Base name for indicators. Defaults to ""
                measure (str): Optional measurement name suffix. Defaults to ""
                Other kwargs are passed to PycVarIndicator constructor

        Returns:
            list[PycVarIndicator]: List of created indicators

        Example:
            >>> system.add_indicator_var(
            ...     stats=["mean", "std"],
            ...     component="tank.*",
            ...     var="level",
            ...     name="tank_level"
            ... )
        """
        stats = indic_specs.pop("stats", ["mean"])
        comp_pat = indic_specs.pop("component", ".*")
        var_pat = indic_specs.pop("var", ".*")
        indic_name = indic_specs.pop("name", "")
        measure_name = indic_specs.get("measure", "")

        indic_added_list = []
        for comp in self.components("#" + comp_pat, "#.*"):
            var_list = [
                var.basename()
                for var in comp.variables()
                if re.search(var_pat, var.basename())
            ]

            for var in var_list:
                if indic_name:
                    indic_name_cur = f"{indic_name}_{var}"
                else:
                    indic_name_cur = f"{comp.basename()}_{var}"

                if measure_name:
                    indic_name_cur += f"_{measure_name}"

                indic = PycVarIndicator(
                    name=indic_name_cur,
                    component=comp.basename(),
                    var=var,
                    stats=stats,
                    **indic_specs,
                )

                # if "MES" in comp_pat:
                #     ipdb.set_trace()

                self.indicators[indic_name_cur] = indic

                indic_added_list.append(indic)

        return indic_added_list

    def add_indicator_state(self, **indic_specs):
        """Add state-based indicators to the system.

        Creates indicators for component states matching specified patterns.
        Monitors state occupancy and transitions.

        Args:
            **indic_specs: Indicator specifications including:
                stats (list[str]): Statistical measures to compute. Defaults to ["mean"]
                component (str): Regex pattern for component names. Defaults to ".*"
                state (str): Regex pattern for state names. Defaults to ".*"
                name (str): Base name for indicators. Defaults to ""
                measure (str): Optional measurement name suffix. Defaults to ""
                Other kwargs are passed to PycSTIndicator constructor

        Returns:
            list[PycSTIndicator]: List of created indicators

        Example:
            >>> system.add_indicator_state(
            ...     stats=["mean"],
            ...     component="pump.*",
            ...     state="failed",
            ...     name="pump_failure"
            ... )
        """
        stats = indic_specs.pop("stats", ["mean"])
        comp_pat = indic_specs.pop("component", ".*")
        state_pat = indic_specs.pop("state", ".*")
        indic_name = indic_specs.pop("name", "")
        measure_name = indic_specs.get("measure", "")

        indic_added_list = []
        for comp in self.components("#" + comp_pat, "#.*"):
            state_list = [
                state.basename()
                for state in comp.states()
                if re.search(state_pat, state.basename())
            ]

            for state in state_list:
                if indic_name:
                    indic_name_cur = f"{indic_name}_{state}"
                else:
                    indic_name_cur = f"{comp.basename()}_{state}"

                if measure_name:
                    indic_name_cur += f"_{measure_name}"

                indic = PycSTIndicator(
                    name=indic_name_cur,
                    component=comp.basename(),
                    state=state,
                    stats=stats,
                    **indic_specs,
                )

                # if "MES" in comp_pat:
                #     ipdb.set_trace()

                self.indicators[indic_name_cur] = indic

                indic_added_list.append(indic)

        return indic_added_list

    def prepare_simu(self, simu_params: PycMCSimulationParam):
        """Prepare the system for simulation with given parameters.

        This method configures the simulation environment by:
        - Setting up measurement time points
        - Configuring system indicators
        - Setting simulation parameters (max time, seed, number of runs)

        Args:
            simu_params (PycMCSimulationParam): Simulation parameters including:
                - Number of runs
                - Measurement schedule
                - Random seed
                - Time units

        Example:
            >>> params = PycMCSimulationParam(
            ...     nb_runs=1000,
            ...     schedule=[0, 100],
            ...     seed=42
            ... )
            >>> system.prepare_simu(params)
        """
        instants_list = simu_params.get_instants_list()

        # Configure indicators with measurement points
        for indic_name, indic in self.indicators.items():
            indic.instants = instants_list
            indic.set_indicator(self)

        # Set simulation parameters
        self.setTMax(instants_list[-1])
        for instant in instants_list:
            self.addInstant(instant)

        if simu_params.seed is not None:
            self.setRNGSeed(simu_params.seed)

        if simu_params.nb_runs is not None:
            self.setNbSeqToSim(simu_params.nb_runs)

    def simulate(self, simu_params: PycMCSimulationParam):
        """Run a complete simulation with the given parameters.

        This method handles the full simulation workflow:
        1. Parameter validation and preparation
        2. System simulation
        3. Post-processing of results

        Args:
            simu_params (Union[PycMCSimulationParam, dict]): Simulation parameters.
                Can be provided as a PycMCSimulationParam object or a dict.

        Example:
            >>> system.simulate({
            ...     'nb_runs': 1000,
            ...     'schedule': [0, 50, 100],
            ...     'seed': 42
            ... })
        """
        if isinstance(simu_params, dict):
            simu_params = PycMCSimulationParam(**simu_params)

        self.prepare_simu(simu_params)
        super().simulate()
        if self.MPIRank() > 0:
            exit(0)
        self.postproc_simu()

    def postproc_simu(self):
        """Process simulation results after completion.

        Updates all indicator values with simulation results.
        Called automatically by simulate(), but can be called manually
        if needed for custom post-processing workflows.
        """
        for indic in self.indicators.values():
            indic.update_values()

    def get_simulation_mode(self):
        """Get the current simulation mode.

        Returns:
            str: Current simulation mode ('MC' for Monte Carlo, 'INT' for interactive)
        """
        return get_pyc_simu_mode(self.simuMode())

    def indic_metadata_names(self):
        """Get all unique metadata field names from indicators.

        Returns:
            list[str]: List of all metadata field names present in any indicator.
        """
        metadata_df = pd.DataFrame(
            [indic.metadata for indic in self.indicators.values()]
        )
        return list(metadata_df.columns)

    #     return [indic.metadata.keys() for indic in self.indicators.values()],
    # axis=0, ignore_index=True)

    def indic_to_frame(self):
        """Convert all indicators' values to a pandas DataFrame.

        Returns:
            pandas.DataFrame: Combined DataFrame of all indicators' values, or
            None if no indicators are present.

        The DataFrame contains columns for:
        - instant: Time point of measurement
        - values: Measured values
        - name: Indicator name
        - stat: Statistical measure (e.g., 'mean', 'std')
        - Additional metadata columns from indicators
        """
        if len(self.indicators) == 0:
            return None
        else:
            return pd.concat(
                [indic.values for indic in self.indicators.values()],
                axis=0,
                ignore_index=True,
            )

    def indic_px_line(
        self,
        x="instant",
        y="values",
        color="name",
        markers=True,
        comp_pattern=".*",
        attr_pattern=".*",
        layout={},
        **px_conf,
    ):
        """Create a line plot of indicator values using plotly express.

        Args:
            x (str): Column name for x-axis. Defaults to "instant".
            y (str): Column name for y-axis. Defaults to "values".
            color (str): Column name for color grouping. Defaults to "name".
            markers (bool): Whether to show markers. Defaults to True.
            layout (dict): Additional layout parameters for the figure.
            **px_conf: Additional keyword arguments passed to px.line().

        Returns:
            plotly.graph_objects.Figure: Line plot of indicator values, or
            None if no indicators are present.

        Example:
            >>> system.indic_px_line(
            ...     title="System Performance",
            ...     labels={"values": "Flow Rate (m³/s)"}
            ... )
        """
        indic_df = self.indic_to_frame()

        if indic_df is None:
            return None

        # Filter based on component pattern
        if "comp" in indic_df.columns:
            idx_comp_sel = indic_df["comp"].str.match(comp_pattern, na=False)
        else:
            idx_comp_sel = pd.Series([True] * len(indic_df))

        # Filter based on attribute pattern
        if "attr" in indic_df.columns:
            idx_attr_sel = indic_df["attr"].str.match(attr_pattern, na=False)
        else:
            idx_attr_sel = pd.Series([True] * len(indic_df))

        # Filter for mean statistics
        idx_stat_sel = indic_df["stat"].isin(["mean"])

        # Combine all filters
        idx_combined = idx_comp_sel & idx_attr_sel & idx_stat_sel
        indic_sel_df = indic_df.loc[idx_combined]

        fig = px.line(indic_sel_df, x=x, y=y, color=color, markers=markers, **px_conf)
        fig.update_layout(**layout)

        return fig

    def isimu_start(self, **kwargs):
        """Start an interactive simulation session.

        Initializes the interactive mode and prepares the system for step-by-step
        simulation. Creates a new sequence tracker for recording transitions.

        Args:
            **kwargs: Additional arguments (reserved for future use)
        """
        self.startInteractive()
        self.stepForward()
        self.isimu_sequence = PycSequence()

    def isimu_stop(self, **kwargs):
        """Stop the current interactive simulation session.

        Terminates interactive mode and clears the sequence tracker.

        Args:
            **kwargs: Additional arguments (reserved for future use)
        """
        self.stopInteractive()
        self.isimu_sequence = PycSequence()

    def isimu_start_cli(self):
        """Start an interactive CLI simulation session"""
        from .isimu_cli import COD3SISimuCLI

        # Start interactive simulation
        self.isimu_start()

        # Start CLI
        cli = COD3SISimuCLI(self)
        try:
            cli.cmdloop()
        except KeyboardInterrupt:
            print("\nReceived keyboard interrupt")
            self.isimu_stop()

    def isimu_active_transitions(self, **kwargs):
        """Get all currently active transitions in the system.

        Retrieves all transitions that are currently active (their source state is active
        and their conditions are met).

        Args:
            **kwargs: Additional arguments (reserved for future use)

        Returns:
            list[PycTransition]: List of active transitions
        """
        return [PycTransition.from_bkd(trans) for trans in self.activeTransitions()]

    def isimu_fireable_transitions(self, **kwargs):
        """Get all transitions that can be fired at the current time.

        A transition is fireable if:
        - For deterministic transitions: its end time is less than or equal to the
          minimum end time of all active transitions
        - For non-deterministic transitions: it is active at the current time

        Args:
            **kwargs: Additional arguments (reserved for future use)

        Returns:
            list[PycTransition]: List of fireable transitions, with None entries for
                non-fireable transitions to maintain indexing
        """
        trans_list = self.isimu_active_transitions()
        if not trans_list:
            return []

        end_time_bound = min([trans.bkd.endTime() for trans in trans_list])
        trans_list_fireable = []
        for trans in trans_list:
            if trans.occ_law.is_occ_time_deterministic and (
                trans.end_time <= end_time_bound
            ):
                trans_list_fireable.append(trans)
            elif not trans.occ_law.is_occ_time_deterministic:
                trans.end_time = self.currentTime()
                trans_list_fireable.append(trans)
            else:
                trans_list_fireable.append(None)

        # Update end time to match bkd endTime
        for trans in trans_list_fireable:
            if trans:
                trans.end_time = trans.bkd.endTime()

        return trans_list_fireable

    def isimu_show_active_transitions(self, **kwargs):
        """Display all currently active transitions in a formatted list.

        Shows each active transition with its index and a detailed representation
        including component name, transition name, source and target states.

        Args:
            **kwargs: Additional arguments (reserved for future use)

        Example output:
            0: PycTransition pump1.failure: working → failed [exp(0.001)] @ 100.0
            1: PycTransition tank1.empty: normal → low [level <= 0.1]
        """
        transitions = self.isimu_active_transitions()
        trans_list_str = "\n".join(
            [f"{i}: {repr(tr)}" for i, tr in enumerate(transitions) if tr]
        )
        print(trans_list_str)

    def isimu_show_fireable_transitions(self, **kwargs):
        """Display all currently fireable transitions in a formatted list.

        Shows each fireable transition with its index and a detailed representation.
        A transition is fireable if it's active and meets timing/probability conditions.

        Args:
            **kwargs: Additional arguments (reserved for future use)

        Example output:
            0: PycTransition pump1.repair: failed → working [delay(24)] @ 124.0
            1: PycTransition tank1.fill: [empty=0.3 | full=0.7]
        """
        transitions = self.isimu_fireable_transitions()
        trans_list_str = "\n".join(
            [f"{i}: {repr(tr)}" for i, tr in enumerate(transitions) if tr]
        )
        print(trans_list_str)

    def isimu_step_backward(self, reset_planning=True):
        """Step backward in the interactive simulation.

        Reverts the last transition and updates the simulation state accordingly.
        Can optionally reset the planning of non-deterministic transitions.

        Args:
            reset_planning (bool): If True, resets planning for non-deterministic
                transitions. Defaults to True.

        Returns:
            list[PycTransition]: List of transitions that were removed from the sequence

        Note:
            When stepping backward:
            1. The system state is reverted to before the last transition
            2. Matching transitions are removed from the sequence
            3. Non-deterministic transition planning can be reset
        """
        self.stepBackward()

        trans_fireable = [trans for trans in self.isimu_fireable_transitions() if trans]

        trans_removed = []
        for trans_f in trans_fireable:
            i = len(self.isimu_sequence.transitions) - 1
            while i >= 0:
                trans_s_cur = self.isimu_sequence.transitions[i]
                if trans_s_cur == trans_f:
                    trans_rem = self.isimu_sequence.transitions.pop(i)
                    trans_removed.append(trans_rem)
                    break
                i -= 1

        if reset_planning:
            for tr in trans_removed:
                if not tr.occ_law.is_occ_time_deterministic:
                    self.setTransPlanning(tr.bkd, float("inf"), 0)
                    self.updatePlanningInt()

        return trans_removed

    def isimu_step_forward(self):
        """Step forward in the interactive simulation.

        Advances the simulation by one step, firing all transitions that are
        scheduled to occur at the current time.

        Returns:
            list[PycTransition]: List of transitions that were fired during this step

        Note:
            - Only transitions whose end time matches the current time are fired
            - Fired transitions are added to the sequence tracker
            - The simulation time is advanced after firing transitions
        """

        trans_fireable = self.isimu_fireable_transitions()

        self.stepForward()

        trans_fired = [
            trans
            for trans in trans_fireable
            if trans and trans.end_time <= self.currentTime()
        ]

        self.isimu_sequence.transitions.extend(trans_fired)

        return trans_fired

    def isimu_set_transition(
        self, trans_id=None, date=None, state_index=None, **kwargs
    ):
        """Schedule a transition to occur at a specific time.

        Args:
            trans_id (int, optional): ID of the transition to schedule.
                If None, performs a normal step forward. Defaults to None.
            date (float, optional): Time at which to schedule the transition.
                If None, uses current time. Defaults to None.
            state_index (int, optional): For transitions with multiple target states,
                specifies which state to transition to. Defaults to 0.
            **kwargs: Additional arguments (reserved for future use)

        Returns:
            If trans_id is None, returns result of isimu_step_forward()

        Raises:
            IndexError: If trans_id does not correspond to a valid transition

        Example:
            >>> system.isimu_set_transition(
            ...     trans_id=1,      # Schedule transition #1
            ...     date=100.0,      # to occur at t=100
            ...     state_index=0    # targeting first state
            ... )
        """
        if trans_id is None:
            return self.isimu_step_forward()

        trans_list = self.isimu_active_transitions()

        selected_transition = None
        if isinstance(trans_id, int):
            selected_transition = trans_list[trans_id]
        elif isinstance(trans_id, str):
            for trans in trans_list:
                if trans.bkd.name() == trans_id:
                    selected_transition = trans
                    break
        else:
            raise ValueError(
                f"Transition id must be the index of the transition as an integer or its name as a str. Not a value of type {type(trans_id)}"
            )

        if not selected_transition:
            raise IndexError(f"Incorrect transition id {trans_id}")

        if not date:
            if (
                selected_transition.bkd.endTime() >= 0
                and selected_transition.bkd.endTime() < float("inf")
            ):
                date = selected_transition.bkd.endTime()
            else:
                date = self.currentTime()

        if not state_index:
            state_index = 0

        self.setTransPlanning(selected_transition.bkd, date, state_index)
        self.updatePlanningInt()
