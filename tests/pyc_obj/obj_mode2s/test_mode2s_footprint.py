"""``ObjMode2S.footprint`` counts what the constructor builds.

The count exists so a caller can bound or announce a model's size before
building it (cod3s-platform: combinatorics hard cap and failure-modes
table). It is only worth anything if it agrees with construction, so
every case below builds the mode and counts the automata and
transitions it really created, mirrors on the targets included.
"""

import math

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import ObjMode2S
from cod3s.pycatshoo.mode_footprint import mode_footprint
from cod3s.pycatshoo.system import PycSystem


class Equipment(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


@pytest.fixture
def pyc_session():
    yield
    cod3s.terminate_session()


def _built(n, behaviour, occ_law, not_occ_law, **kwargs):
    """(automata, transitions) of the mode, then of its mirrors, as built."""
    PycSystem(name="Footprint")
    targets = [Equipment(f"E{i}") for i in range(1, n + 1)]
    effects = {} if behaviour == "internal" else {"working": False}
    mode = ObjMode2S(
        mode_name="wear",
        targets=[t.name() for t in targets],
        behaviour=behaviour,
        occ_state="occ",
        not_occ_state="rep",
        occ_law=occ_law,
        not_occ_law=not_occ_law,
        occ_effects=effects,
        **kwargs,
    )
    own = list(mode.automata_d.values())
    mirrors = [t.automata_d["wear"] for t in targets if "wear" in t.automata_d]
    return (
        (len(own), sum(len(a.transitions) for a in own)),
        (len(mirrors), sum(len(a.transitions) for a in mirrors)),
    )


EXP = {"cls": "exp", "rate": 0.1}

#: (n, occ_law, not_occ_law, drop_inactive_automata), each run under the
#: three behaviours. Covers: every law on each direction, exp zero orders
#: dropped, None markers, delay 0 kept, inst certain (no re-arm) and
#: uncertain (re-arm), drop disabled.
CASES = {
    "exp-exp-single": (1, EXP, EXP, True),
    "exp-exp-ccf3": (
        3,
        {"cls": "exp", "rate": [1e-3, 1e-4, 1e-5]},
        {"cls": "exp", "rate": [0.1, 0.1, 0.1]},
        True,
    ),
    "exp-zero-orders-dropped": (
        3,
        {"cls": "exp", "rate": [1e-3, 0.0, 0.0]},
        {"cls": "exp", "rate": [0.1, 0.0, 0.0]},
        True,
    ),
    "exp-zero-orders-kept-without-drop": (
        3,
        {"cls": "exp", "rate": [1e-3, 0.0, 0.0]},
        {"cls": "exp", "rate": [0.1, 0.0, 0.0]},
        False,
    ),
    "delay-none-orders": (
        3,
        {"cls": "delay", "time": [100.0, None, None]},
        {"cls": "exp", "rate": [0.1, None, None]},
        True,
    ),
    "delay-zero-is-active": (
        2,
        {"cls": "delay", "time": [100.0, 0.0]},
        {"cls": "delay", "time": [5.0, 0.0]},
        True,
    ),
    "inst-occ-uncertain-ccf": (
        3,
        {"cls": "inst", "prob": [0.3, 0.1, 0.05]},
        {"cls": "exp", "rate": [0.1, 0.1, 0.1]},
        True,
    ),
    "inst-occ-certain": (
        2,
        {"cls": "inst", "prob": [1.0, 0.5]},
        {"cls": "exp", "rate": [0.1, 0.1]},
        True,
    ),
    "inst-return-uncertain": (1, EXP, {"cls": "inst", "prob": 0.4}, True),
    "inst-return-certain": (1, EXP, {"cls": "inst", "prob": 1.0}, True),
    "inst-both": (1, {"cls": "inst", "prob": 0.5}, {"cls": "inst", "prob": 0.5}, True),
}

BEHAVIOURS = ("internal", "external", "external_rep_indep")

#: What the constructor raises on a combination it does not build. An inst
#: return law under ``external_rep_indep`` ends in ``NotImplementedError``
#: (the mirror's return transition wants a backend law dict, which an inst
#: spec has none of), the other refusals in ``ValueError``.
REFUSALS = (ValueError, NotImplementedError)


@pytest.mark.parametrize("behaviour", BEHAVIOURS)
@pytest.mark.parametrize("case", sorted(CASES))
def test_the_footprint_is_what_the_constructor_builds(pyc_session, case, behaviour):
    n, occ_law, not_occ_law, drop = CASES[case]
    try:
        (own_aut, own_tr), (mir_aut, mir_tr) = _built(
            n, behaviour, occ_law, not_occ_law, drop_inactive_automata=drop
        )
    except REFUSALS as exc:
        pytest.skip(f"the constructor refuses this combination: {exc}")
    fp = ObjMode2S.footprint(
        n,
        behaviour=behaviour,
        occ_law=occ_law,
        not_occ_law=not_occ_law,
        drop_inactive_automata=drop,
    )
    assert (fp.mode_automata, fp.mode_transitions) == (own_aut, own_tr)
    assert (fp.mirror_automata, fp.mirror_transitions) == (mir_aut, mir_tr)


def test_the_matrix_is_not_mostly_refused(pyc_session):
    """The skip above must stay an exception: count the built cases."""
    built = 0
    for n, occ_law, not_occ_law, drop in CASES.values():
        for behaviour in BEHAVIOURS:
            try:
                _built(n, behaviour, occ_law, not_occ_law, drop_inactive_automata=drop)
                built += 1
            except REFUSALS:
                pass
            cod3s.terminate_session()
    assert built >= 0.8 * len(CASES) * len(BEHAVIOURS)


def test_a_ccf_order_costs_its_combinations_and_nothing_for_dropped_orders():
    fp = mode_footprint(
        6,
        occ_law={"cls": "exp", "rate": [1e-3, 1e-4, None, None, None, None]},
        not_occ_law={"cls": "exp", "rate": [0.1, 0.1, None, None, None, None]},
    )
    assert [o.combinations for o in fp.by_order] == [6, math.comb(6, 2), 0, 0, 0, 0]
    assert fp.transitions == 2 * (6 + 15)


def test_external_adds_two_transitions_per_target():
    """The case the platform's own count missed (cod3s#7)."""
    laws = dict(
        occ_law={"cls": "exp", "rate": [1e-3] + [None] * 5},
        not_occ_law={"cls": "exp", "rate": [0.1] + [None] * 5},
    )
    internal = mode_footprint(6, behaviour="internal", **laws)
    external = mode_footprint(6, behaviour="external", **laws)
    assert internal.transitions == 12
    assert external.transitions == 24
    assert external.order(1).transitions == 12


def test_explicit_params_take_precedence_over_the_law_vector():
    fp = mode_footprint(
        2,
        occ_law={"cls": "exp", "rate": [1e-3, 1e-4]},
        not_occ_law={"cls": "exp", "rate": [0.1, 0.1]},
        occ_param=[1e-3, 0.0],
        not_occ_param=[0.1, 0.0],
    )
    assert [o.combinations for o in fp.by_order] == [2, 0]


def test_a_vector_of_the_wrong_length_is_refused():
    with pytest.raises(ValueError, match="strict length"):
        mode_footprint(3, occ_law={"cls": "exp", "rate": [1e-3, 1e-4]}, not_occ_law=EXP)


def test_no_target_builds_nothing():
    fp = mode_footprint(0, occ_law=EXP, not_occ_law=EXP, behaviour="external")
    assert (fp.automata, fp.transitions) == (0, 0)
