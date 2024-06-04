import typing
import pydantic
import pkg_resources
from .. import StudyModel, MCSimulationParam
from . import PycSystem, PycVarIndicator, PycTransition

installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: 401


# Utility functions
# -----------------


class PycMCSimulationParam(MCSimulationParam):
    """
    A class representing Monte Carlo Simulation parameters for Pycatshoo.
    """


class PycStudy(StudyModel):

    """
    A class representing a study in Pycatshoo.

    Attributes:
        system_model (PycSystem): The system model.
        simu_params (PycMCSimulationParam): The simulation parameters.
        indicators (typing.List[PycVarIndicator]): The list of indicators.
    """

    system_model: PycSystem = pydantic.Field(
        None, description="System model"
    )

    simu_params: PycMCSimulationParam = pydantic.Field(
        None, description="Simulator parameters"
    )

    indicators: typing.List[PycVarIndicator] = pydantic.Field(
        [], description="List of indicators"
    )

    def prepare_simu(self, **kwargs):

        """
        Prepare the simulation by setting up the system model and indicators.

        Args:
            **kwargs: Additional keyword arguments.
        """
        self.run_before_hook()

        # Set instants
        instants_list = self.simu_params.get_instants_list()

        # Prepare indicators
        for indic in self.indicators:
            indic.instants = instants_list
            indic.bkd = \
                self.system_model.bkd.addIndicator(indic.name,
                                                   indic.get_expr(),
                                                   indic.get_type())
            indic.update_restitution()

        # Simulator configuration
        self.system_model.bkd.setTMax(instants_list[-1])

        for instant in instants_list:
            self.system_model.bkd.addInstant(instant)

        if self.simu_params.seed:
            self.system_model.bkd.setRNGSeed(self.simu_params.seed)

        if self.simu_params.nb_runs:
            self.system_model.bkd.setNbSeqToSim(self.simu_params.nb_runs)

    def run_simu(self, **kwargs):

        self.prepare_simu(**kwargs)

        self.system_model.bkd.simulate()

        self.postproc_simu(**kwargs)

    def postproc_simu(self, **kwargs):

        for indic in self.indicators:
            indic.update_values()

        self.run_after_hook()

