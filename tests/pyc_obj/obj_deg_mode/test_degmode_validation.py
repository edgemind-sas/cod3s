"""ObjDegMode construction-time validation (fail fast, clear messages).

Every error must fire at construction, never at first simulation visit.
Unique fm_names throughout: a failed construction may leave a partially
registered carrier component in the module-level system.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import DegState, ObjDegMode
from cod3s.pycatshoo.system import PycSystem


class Rail(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.broken = self.addVariable("broken", Pyc.TVarType.t_bool, False)
        self.broken.setReinitialized(True)


@pytest.fixture(scope="module")
def system():
    system = PycSystem(name="DegModeValidation")
    Rail("R1"), Rail("R2")
    yield system
    cod3s.terminate_session()


EXP = {"cls": "exp", "rate": 0.1}
REP = {"cls": "exp", "rate": 0.5}


def make(system, fm_name, **overrides):
    kwargs = dict(
        fm_name=fm_name,
        targets=["R1"],
        states=[DegState("O", occ_law=EXP, rep_law=REP)],
    )
    kwargs.update(overrides)
    return ObjDegMode(**kwargs)


class TestStatesValidation:
    def test_empty_states_rejected(self, system):
        with pytest.raises(ValueError, match="non-empty"):
            make(system, "v01", states=[])

    def test_duplicate_state_names_rejected(self, system):
        with pytest.raises(ValueError, match="duplicated state"):
            make(
                system,
                "v02",
                states=[
                    DegState("O", occ_law=EXP),
                    DegState("O", occ_law=EXP),
                ],
            )

    def test_healthy_state_collision_rejected(self, system):
        with pytest.raises(ValueError, match="healthy"):
            make(system, "v03", states=[DegState("sain", occ_law=EXP)])

    @pytest.mark.parametrize("bad", ["with.dot", "double__underscore", "_edge", ""])
    def test_invalid_state_names_rejected(self, system, bad):
        with pytest.raises(ValueError, match="state name"):
            make(system, f"v04_{abs(hash(bad))}", states=[DegState(bad, occ_law=EXP)])

    def test_bare_dict_states_accepted(self, system):
        dm = make(
            system,
            "v05",
            states=[{"name": "O", "occ_law": EXP, "rep_law": REP}],
        )
        assert dm.states[0].name == "O"

    def test_unknown_degstate_field_rejected(self, system):
        with pytest.raises(Exception, match="not_a_field"):
            make(
                system, "v06", states=[{"name": "O", "occ_law": EXP, "not_a_field": 1}]
            )


class TestLawValidation:
    def test_first_state_delay_law_rejected(self, system):
        with pytest.raises(ValueError, match="exponential"):
            make(
                system,
                "v10",
                states=[DegState("O", occ_law={"cls": "delay", "time": 5})],
            )

    def test_lambda_vector_wrong_length_rejected(self, system):
        with pytest.raises(ValueError, match="length"):
            make(
                system,
                "v11",
                targets=["R1", "R2"],
                states=[DegState("O", occ_law={"cls": "exp", "rate": [0.1, 0.2, 0.3]})],
            )

    def test_lambda_scalar_means_order1_only(self, system):
        dm = make(
            system, "v12", targets=["R1", "R2"], states=[DegState("O", occ_law=EXP)]
        )
        assert dm.lambda_by_order == [0.1, 0.0]

    def test_vector_on_deeper_state_rejected(self, system):
        with pytest.raises(ValueError, match="scalar"):
            make(
                system,
                "v13",
                states=[
                    DegState("O", occ_law=EXP),
                    DegState("X1", occ_law={"cls": "exp", "rate": [0.1]}),
                ],
            )

    def test_vector_on_rep_law_rejected(self, system):
        with pytest.raises(ValueError, match="scalar"):
            make(
                system,
                "v14",
                states=[
                    DegState("O", occ_law=EXP, rep_law={"cls": "exp", "rate": [0.5]})
                ],
            )

    def test_unknown_law_cls_rejected(self, system):
        with pytest.raises(Exception, match="inst|discriminator|exp"):
            make(
                system,
                "v15",
                states=[DegState("O", occ_law={"cls": "inst", "probs": [1]})],
            )


class TestEffectsValidation:
    def test_clamp_pulse_overlap_rejected(self, system):
        with pytest.raises(ValueError, match="BOTH state-based"):
            make(
                system,
                "v20",
                states=[
                    DegState(
                        "O",
                        occ_law=EXP,
                        effects={"broken": True},
                        occ_effects_trans={"broken": True},
                    )
                ],
            )

    def test_rep_pulse_without_rep_law_rejected(self, system):
        with pytest.raises(ValueError, match="no rep_law"):
            make(
                system,
                "v21",
                states=[
                    DegState("O", occ_law=EXP, rep_effects_trans={"broken": False})
                ],
            )

    def test_unknown_effect_variable_rejected_at_construction(self, system):
        with pytest.raises(ValueError, match="not_a_var"):
            make(
                system,
                "v22",
                states=[DegState("O", occ_law=EXP, effects={"not_a_var": True})],
            )


class TestTargetsValidation:
    def test_missing_target_rejected(self, system):
        with pytest.raises(ValueError, match="not "):
            make(system, "v30", targets=["NoSuchComp"])

    def test_duplicate_targets_rejected(self, system):
        with pytest.raises(ValueError, match="duplicated targets"):
            make(system, "v31", targets=["R1", "R1"])

    def test_empty_targets_rejected(self, system):
        with pytest.raises(ValueError, match="non-empty"):
            make(system, "v32", targets=[])

    def test_mode_name_collision_on_target_rejected(self, system):
        make(system, "v33")
        with pytest.raises(ValueError, match="already"):
            ObjDegMode(
                fm_name="v33",
                targets=["R1"],
                target_name="R1bis",
                states=[DegState("O", occ_law=EXP)],
            )


class TestBaseSpecCompat:
    """FailureModeBaseSpec fields travelling through ObjFMGenericSpec."""

    def test_behaviour_internal_default_tolerated(self, system):
        # BaseSpec Pydantic default: indistinguishable from unset after
        # model_dump — treated as unset (documented limitation).
        make(system, "v40", behaviour="internal")

    def test_behaviour_external_rep_indep_accepted(self, system):
        make(system, "v41", behaviour="external_rep_indep")

    def test_behaviour_external_rejected(self, system):
        with pytest.raises(ValueError, match="behaviour"):
            make(system, "v42", behaviour="external")

    def test_failure_cond_is_wire_alias_of_occ_cond(self, system):
        cond = [{"attr": "broken", "value": False}]
        dm = make(system, "v43", failure_cond=cond)
        assert dm.occ_cond == cond

    def test_both_conds_set_rejected(self, system):
        cond = [{"attr": "broken", "value": False}]
        with pytest.raises(ValueError, match="exactly one"):
            make(system, "v44", failure_cond=cond, occ_cond=cond)

    def test_basespec_defaults_tolerated(self, system):
        make(
            system,
            "v45",
            failure_state="occ",
            repair_state="rep",
            failure_effects={},
            failure_effects_trans={},
            repair_cond=True,
            repair_effects={},
            repair_effects_trans={},
            failure_param_name=None,
            repair_param_name=None,
        )

    def test_basespec_explicit_value_rejected_not_ignored(self, system):
        with pytest.raises(ValueError, match="failure_effects"):
            make(system, "v46", failure_effects={"broken": True})

    def test_unknown_kwarg_rejected(self, system):
        with pytest.raises(TypeError, match="no_such_kwarg"):
            make(system, "v47", no_such_kwarg=1)


class TestMutableDefaultIsolation:
    def test_states_are_deep_copied(self, system):
        shared = [
            {"name": "O", "occ_law": dict(EXP), "effects": {"broken": True}},
        ]
        dm1 = make(system, "v50", targets=["R1"], states=shared)
        dm2 = make(system, "v51", targets=["R2"], states=shared)
        assert dm1.states is not dm2.states
        assert dm1.states[0] is not dm2.states[0]
        dm1.states[0].effects["extra"] = 1
        assert "extra" not in dm2.states[0].effects
