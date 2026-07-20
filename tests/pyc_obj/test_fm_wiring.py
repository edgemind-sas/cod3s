"""Direct contract tests for the shared FM wiring bricks.

``fm_wiring`` is consumed by two classes (ObjFM today, ObjDegMode next):
the obj_fm suite locks it indirectly, these tests lock it directly so a
future change cannot drift for one consumer without failing here.
"""

import pytest

import Pycatshoo as Pyc

import cod3s
from cod3s.pycatshoo.fm_wiring import (
    FmWiringMixin,
    cc_comb_suffix,
    order_param_name,
)
from cod3s.pycatshoo.system import PycSystem


@pytest.fixture(autouse=True, scope="module")
def _release_pycatshoo_singleton():
    yield
    cod3s.terminate_session()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestOrderParamName:
    def test_single_target_keeps_bare_name(self):
        assert order_param_name("lambda", 1, 1) == "lambda"

    def test_multi_target_appends_order_suffix(self):
        assert order_param_name("lambda", 1, 3) == "lambda__1_o_3"
        assert order_param_name("lambda", 3, 3) == "lambda__3_o_3"

    def test_custom_format(self):
        assert order_param_name("mu", 2, 4, fmt="_k{order}") == "mu_k2"


class TestCcCombSuffix:
    def test_single_target_yields_empty_suffix(self):
        assert cc_comb_suffix((0,), 1) == ""

    def test_indices_are_one_based_and_underscore_separated(self):
        assert cc_comb_suffix((0,), 3) == "__cc_1"
        assert cc_comb_suffix((0, 1), 3) == "__cc_1_2"
        assert cc_comb_suffix((0, 1, 2), 3) == "__cc_1_2_3"

    def test_ten_plus_targets_stay_unambiguous(self):
        # The underscore separation is what disambiguates 10+ targets
        # (cod3s 1.9.0 convention): (0, 11) is targets 1 and 12.
        assert cc_comb_suffix((0, 11), 12) == "__cc_1_12"

    def test_format_string_fields(self):
        assert (
            cc_comb_suffix((0, 2), 3, trans_name_prefix="__bin_{target_binary}")
            == "__bin_101"
        )
        assert (
            cc_comb_suffix((1,), 3, trans_name_prefix="__o{order}_of_{order_max}")
            == "__o1_of_3"
        )

    def test_callable_takes_precedence(self):
        def fun(**kwargs):
            return f"__custom_{kwargs['target_comb_u']}_{kwargs['order']}"

        assert cc_comb_suffix((0, 1), 2, trans_name_prefix_fun=fun) == "__custom_1_2_2"


# ---------------------------------------------------------------------------
# Mixin wiring (hand-built minimal component, no ObjFM involved)
# ---------------------------------------------------------------------------


class WiringHost(FmWiringMixin, cod3s.PycComponent):
    """Minimal host exercising the mixin outside any ObjFM."""

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.gate = self.addVariable("gate", Pyc.TVarType.t_bool, False)
        self.gate.setReinitialized(True)
        self.level = self.addVariable("level", Pyc.TVarType.t_int, 0)
        self.level.setReinitialized(True)


@pytest.fixture(scope="module")
def wired_system():
    system = PycSystem(name="FmWiringTest")
    host = WiringHost("H1")

    aut = host.add_automaton(
        name="deg",
        states=["idle", "active"],
        init_state="idle",
        transitions=[
            {
                "name": "go",
                "source": "idle",
                "target": "active",
                "occ_law": {"cls": "delay", "time": 2.0},
            },
            {
                "name": "back",
                "source": "active",
                "target": "idle",
                "occ_law": {"cls": "delay", "time": 2.0},
            },
        ],
    )

    # State clamp: level=1 while 'active'; pulse: gate=True once on 'go'.
    records_level = host._resolve_target_effects(
        host, "H1", {"level": 1}, kind="state_effects"
    )
    host._wire_state_effects(aut, "active", records_level, trans_name="go")
    records_pulse = host._resolve_target_effects(
        host, "H1", {"gate": True}, kind="trans_effects"
    )
    host._wire_transition_effects(aut, "go", records_pulse)

    yield system, host
    cod3s.terminate_session()


class TestMixinWiring:
    def test_resolve_unknown_variable_raises_with_context(self, wired_system):
        _, host = wired_system
        with pytest.raises(ValueError, match="not_a_var"):
            host._resolve_target_effects(
                host, "H1", {"not_a_var": 1}, kind="state_effects"
            )

    def test_state_clamp_and_pulse(self, wired_system):
        system, host = wired_system
        system.isimu_start()

        # Fire 'go' at t=2: clamp applies (level=1), pulse fires (gate=True).
        system.isimu_set_transition(0, date=2.0)
        system.isimu_step_forward()
        assert host.level.value() == 1
        assert host.gate.value() is True

        # A pulse is one-shot: clearing the gate by hand must NOT be undone
        # while the state clamp keeps re-applying its own variable.
        host.gate.setValue(False)
        # Fire 'back' at t=4: the clamp stops maintaining level, the pulse
        # does not re-fire.
        system.isimu_set_transition(0, date=4.0)
        system.isimu_step_forward()
        assert host.gate.value() is False
        system.isimu_stop()
