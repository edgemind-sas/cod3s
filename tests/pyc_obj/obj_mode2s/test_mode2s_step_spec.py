"""``step`` on the study.yaml wire: spec field -> ObjMode2S.step.

``step`` selects the PDMP phase (PyCATSHOO "étape", declared with
``system.addStep``) the mode's effect methods are placed in. It has
always been an ``ObjMode2S`` constructor kwarg, but ``extra="forbid"``
on ``FailureModeBaseSpec`` made it undeclarable in a study.yaml — a
model whose effects must run in an early phase could not be expressed
on the wire at all, and its effects landed in whatever phase was
current when the transition fired (a hard PyCATSHOO error when that
phase is already closed).

This module locks the whole path: the runner's
``model_dump(exclude={"cls", "enabled"})`` carries the value, every FM
class the registry can resolve accepts it, the default ``None`` leaves
the historical behaviour untouched, and an unknown phase name still
produces the engine's own error.
"""

import inspect

import pydantic
import pytest
import yaml

import Pycatshoo as Pyc

import cod3s
from cod3s.pycatshoo.system import PycSystem
from cod3s.scripts.study_runner import (
    _FM_REGISTRY,
    _resolve_fm_class,
    add_failure_modes,
)
from cod3s.specs.study_yaml import (
    FailureModeSpec,
    ObjFMDelaySpec,
    ObjFMExpSpec,
    ObjFMInstSpec,
)

_SPEC_ADAPTER = pydantic.TypeAdapter(FailureModeSpec)

#: The phases a stepped system declares, in order.
STEP_NAMES = ("failure_propagation", "flow_propagation")


class Equipment(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


class SteppedSystem(PycSystem):
    """A system that declares named PDMP phases (the IMDR shape)."""

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.pdmp_manager = self.addPDMPManager("pdmp_manager")
        for step_name in STEP_NAMES:
            self.addStep(step_name)


def fresh_system(cls, name):
    cod3s.terminate_session()
    system = cls(name=name)
    Equipment("E1")
    return system


#: One spec per typed spec class, with parameters its law accepts.
TYPED_SPECS = {
    "ObjFMExp": (ObjFMExpSpec, {"failure_param": [0.1], "repair_param": [0.5]}),
    "ObjFMDelay": (ObjFMDelaySpec, {"failure_param": [5.0], "repair_param": [2.0]}),
    "ObjFMInst": (ObjFMInstSpec, {"failure_param": [0.5], "repair_param": [0.5]}),
}

#: The generic (extra="allow") wire path, onto the native engine.
GENERIC_SPEC_YAML = """
cls: ObjMode2S
fm_name: m
targets: [E1]
occ_law: {cls: exp, rate: 0.4}
not_occ_law: {cls: delay, time: 1.5}
occ_effects: {working: false}
"""


class TestStepReachesTheConstructor:
    @pytest.mark.parametrize("cls_name", sorted(TYPED_SPECS))
    def test_typed_spec(self, cls_name):
        spec_cls, params = TYPED_SPECS[cls_name]
        system = fresh_system(SteppedSystem, f"Step_{cls_name}")
        spec = spec_cls(
            fm_name="m",
            targets=["E1"],
            failure_effects={"working": False},
            step="failure_propagation",
            **params,
        )
        assert add_failure_modes(system, [spec]) == 1
        mode = system.comp["E1__m"]
        assert mode.step is not None
        assert mode.step.name() == system.step("failure_propagation").name()
        cod3s.terminate_session()

    def test_generic_spec_onto_the_native_engine(self):
        system = fresh_system(SteppedSystem, "StepGeneric")
        raw = yaml.safe_load(GENERIC_SPEC_YAML)
        raw["step"] = "flow_propagation"
        spec = _SPEC_ADAPTER.validate_python(raw)
        assert add_failure_modes(system, [spec]) == 1
        mode = system.comp["E1__m"]
        assert mode.step.name() == system.step("flow_propagation").name()
        cod3s.terminate_session()


class TestDefaultIsUntouched:
    """The overwhelmingly common case: a study declaring no phase."""

    def test_every_registered_class_defaults_step_to_none(self):
        _resolve_fm_class("ObjFMExp")  # populate the lazy registry
        for cls_name, fm_cls in _FM_REGISTRY.items():
            param = inspect.signature(fm_cls.__init__).parameters.get("step")
            assert param is not None, f"{cls_name} does not accept step"
            assert param.default is None, cls_name

    @pytest.mark.parametrize("cls_name", sorted(TYPED_SPECS))
    def test_no_step_declared_on_a_stepped_system(self, cls_name):
        spec_cls, params = TYPED_SPECS[cls_name]
        system = fresh_system(SteppedSystem, f"NoStep_{cls_name}")
        spec = spec_cls(
            fm_name="m",
            targets=["E1"],
            failure_effects={"working": False},
            **params,
        )
        assert spec.model_dump()["step"] is None
        assert add_failure_modes(system, [spec]) == 1
        assert system.comp["E1__m"].step is None
        cod3s.terminate_session()

    @pytest.mark.parametrize("cls_name", sorted(TYPED_SPECS))
    def test_no_step_declared_on_a_system_without_phases(self, cls_name):
        spec_cls, params = TYPED_SPECS[cls_name]
        system = fresh_system(PycSystem, f"NoPhase_{cls_name}")
        spec = spec_cls(
            fm_name="m",
            targets=["E1"],
            failure_effects={"working": False},
            **params,
        )
        assert add_failure_modes(system, [spec]) == 1
        assert system.comp["E1__m"].step is None
        cod3s.terminate_session()


class TestUnknownStepName:
    def test_engine_error_is_preserved(self):
        """An unknown phase must fail loudly, not build a phase-less mode."""
        fresh_system(SteppedSystem, "BadStep")
        spec = ObjFMDelaySpec(
            fm_name="m",
            targets=["E1"],
            failure_param=[5.0],
            repair_param=[2.0],
            failure_effects={"working": False},
            step="does_not_exist",
        )
        kwargs = spec.model_dump(exclude={"cls", "enabled"})
        with pytest.raises(ValueError, match="Step does_not_exist does not exist"):
            _resolve_fm_class("ObjFMDelay")(**kwargs)
        cod3s.terminate_session()

    def test_runner_swallow_semantics(self):
        """``add_failure_modes`` logs and counts 0 (checked by callers /
        ``simulation.strict_failure_modes``), it does not raise."""
        system = fresh_system(SteppedSystem, "BadStepRunner")
        spec = ObjFMDelaySpec(
            fm_name="m",
            targets=["E1"],
            failure_param=[5.0],
            repair_param=[2.0],
            failure_effects={"working": False},
            step="does_not_exist",
        )
        assert add_failure_modes(system, [spec]) == 0
        cod3s.terminate_session()
