"""Explicit inactive-order marker (``None`` vector entries, 1.14.4).

A ``delay`` law value of 0 is ACTIVE and IMMEDIATE — unlike the exp
rate, there is no magic value meaning « this CC order is undeclared ».
Padding a delay vector with 0 therefore built order-k combination
automata that all fired at t=0 (found by the cod3s-platform code
review on the 3x3 emission). ``None`` is the explicit marker: the
combination automata of that order are not built, whatever the law.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import ObjMode2S
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


def _mode(occ_law, not_occ_law, n=3, **kwargs):
    system = PycSystem(name="InactiveOrders")
    for i in range(1, n + 1):
        Equipment(f"E{i}")
    mode = ObjMode2S(
        mode_name="wear",
        targets=[f"E{i}" for i in range(1, n + 1)],
        occ_state="occ",
        not_occ_state="rep",
        occ_law=occ_law,
        not_occ_law=not_occ_law,
        occ_param_name="ttf",
        not_occ_param_name="mu",
        **kwargs,
    )
    return system, mode


def test_none_orders_build_no_automata_for_delay(pyc_session):
    """The order-1-only delay mode over 3 targets: WITHOUT the marker the
    padded orders 2/3 fired at t=0 (silent wrong model)."""
    system, mode = _mode(
        {"cls": "delay", "time": [10000.0, None, None]},
        {"cls": "exp", "rate": [0.1, None, None]},
    )
    # Only the C(3,1)=3 order-1 combinations exist.
    assert sorted(mode.automata_d) == ["wear__cc_1", "wear__cc_2", "wear__cc_3"]
    # The parameter variables of the inactive orders still exist (0.0).
    assert mode.variable("ttf__2_o_3").value() == 0.0


def test_none_orders_match_exp_zero_padding(pyc_session):
    """For exp laws, None and the historical 0 padding drop the same
    combinations — emitters may use either without behaviour change."""
    system_a, mode_a = _mode(
        {"cls": "exp", "rate": [0.1, 0.0, 0.0]},
        {"cls": "exp", "rate": [0.2, 0.0, 0.0]},
    )
    autos_zero = sorted(mode_a.automata_d)
    cod3s.terminate_session()
    system_b, mode_b = _mode(
        {"cls": "exp", "rate": [0.1, None, None]},
        {"cls": "exp", "rate": [0.2, None, None]},
    )
    assert sorted(mode_b.automata_d) == autos_zero == ["wear__cc_1", "wear__cc_2", "wear__cc_3"]


def test_asymmetric_none_on_kept_order_is_rejected(pyc_session):
    """None on exactly one direction of an otherwise-kept order would run
    the None direction at 0 (delay: IMMEDIATE) — refused loudly."""
    with pytest.raises(ValueError, match="exactly one"):
        _mode(
            {"cls": "delay", "time": [10.0, None]},
            {"cls": "exp", "rate": [0.1, 0.5]},
            n=2,
        )


def test_asymmetric_none_with_inactive_partner_is_fine(pyc_session):
    """None + an exp 0 partner: both directions inactive, order dropped —
    the historical exp shape stays accepted."""
    system, mode = _mode(
        {"cls": "delay", "time": [10.0, None]},
        {"cls": "exp", "rate": [0.1, 0.0]},
        n=2,
    )
    assert sorted(mode.automata_d) == ["wear__cc_1", "wear__cc_2"]


def test_delay_mc_has_no_t0_firings(pyc_session, tmp_path):
    """Seeded MC on the order-1-only delay mode: no event before the
    deterministic time — the t=0 mass-failure bug is dead."""
    system, mode = _mode(
        {"cls": "delay", "time": [50.0, None, None]},
        {"cls": "exp", "rate": [0.1, None, None]},
    )
    system.monitorTransition("#.*")
    seq_path = tmp_path / "seq.xml"
    system.setResultFileName(str(seq_path), False)
    system.setBinSeqFile(False)
    system.simulate({"nb_runs": 10, "seed": 42, "schedule": [100.0]})
    from cod3s.pycatshoo.sequence import SequenceAnalyser

    analyser = SequenceAnalyser.from_pyc_system(system)
    times = [ev.time for seq in analyser.sequences for ev in seq.events]
    assert times, "expected recorded events"
    assert min(times) >= 50.0
