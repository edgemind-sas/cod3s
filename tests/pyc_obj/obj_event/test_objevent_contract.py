"""ObjEvent characterization contract (pre-ObjMode2S refactor safety net).

``tests/pyc_obj/obj_event/`` had no live tests (only stale, never-committed
``.pyc`` files) when the ObjMode2S chantier started. This suite pins the
CURRENT observable behaviour of ``ObjEvent`` so the façade rewrite
(plan ``docs/plans/2026-07-20-feat-objmode2s-...``) has an oracle:

* automaton structure and naming: automaton ``ev``, states ``not_occ`` /
  ``occ`` (init ``not_occ``), transitions literally named ``occ`` and
  ``not_occ``, both delay laws carrying ``tempo_occ`` / ``tempo_not_occ``,
  both interruptible;
* the attribute surface consumed by sequence auto-discovery
  (``event_aut_name`` / ``occ_state_name`` / ``not_occ_state_name``);
* the zero-overhead contract: no variables, no start-method and no
  sensitive-method registration at construction;
* cond compilation: callable cond drives ``occ`` and its automatic
  negation drives ``not_occ``; structured cond (attr tree) works;
  ``inner_logic`` / ``outer_logic`` accept the documented ``"all"`` /
  ``"any"`` strings.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s.pycatshoo.automaton import DelayOccDistribution
from cod3s.pycatshoo.component import PycComponent
from cod3s.pycatshoo.system import PycSystem


class EvtSource(cod3s.PycComponent):
    """Minimal component carrying a boolean an ObjEvent can condition on."""

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


@pytest.fixture
def pyc_session():
    yield
    cod3s.terminate_session()


def _fire_by_name(system, name, comp_name=None):
    trs = system.isimu_fireable_transitions()
    idx = next(
        i
        for i, t in enumerate(trs)
        if t is not None
        and t.name == name
        and (comp_name is None or t.comp_name == comp_name)
    )
    system.isimu_set_transition(idx)
    return [t.name for t in system.isimu_step_forward()]


def test_default_construction_grammar(pyc_session):
    system = PycSystem(name="EvtContractDefault")
    system.add_component(name="box", cls="EvtSource")
    box = system.comp["box"]

    system.add_component(
        cls="ObjEvent",
        name="system_down",
        cond=lambda: box.working.value() is False,
    )
    ev = system.comp["system_down"]

    # Attribute surface consumed by SequenceAnalyser auto-discovery.
    assert ev.event_aut_name == "ev"
    assert ev.occ_state_name == "occ"
    assert ev.not_occ_state_name == "not_occ"

    # Automaton grammar.
    assert list(ev.automata_d) == ["ev"]
    aut = ev.automata_d["ev"]
    assert [st.name for st in aut.states] == ["not_occ", "occ"]
    assert aut.init_state == "not_occ"

    tr_occ = aut.get_transition_by_name("occ")
    assert tr_occ.source == "not_occ"
    assert tr_occ.target == "occ"
    assert isinstance(tr_occ.occ_law, DelayOccDistribution)
    assert tr_occ.occ_law.time == 0
    assert tr_occ.is_interruptible is True

    tr_not_occ = aut.get_transition_by_name("not_occ")
    assert tr_not_occ.source == "occ"
    assert tr_not_occ.target == "not_occ"
    assert isinstance(tr_not_occ.occ_law, DelayOccDistribution)
    assert tr_not_occ.occ_law.time == 0
    assert tr_not_occ.is_interruptible is True


def test_tempo_values_carried_by_delay_laws(pyc_session):
    system = PycSystem(name="EvtContractTempo")
    system.add_component(name="box", cls="EvtSource")
    box = system.comp["box"]

    system.add_component(
        cls="ObjEvent",
        name="alarm",
        cond=lambda: box.working.value() is False,
        tempo_occ=2.5,
        tempo_not_occ=1.5,
    )
    aut = system.comp["alarm"].automata_d["ev"]
    assert aut.get_transition_by_name("occ").occ_law.time == 2.5
    assert aut.get_transition_by_name("not_occ").occ_law.time == 1.5


def test_custom_names(pyc_session):
    system = PycSystem(name="EvtContractCustom")
    system.add_component(name="box", cls="EvtSource")
    box = system.comp["box"]

    system.add_component(
        cls="ObjEvent",
        name="alarm",
        cond=lambda: box.working.value() is False,
        event_aut_name="myev",
        occ_state_name="up",
        not_occ_state_name="down",
    )
    ev = system.comp["alarm"]
    assert ev.event_aut_name == "myev"
    assert ev.occ_state_name == "up"
    assert ev.not_occ_state_name == "down"

    aut = ev.automata_d["myev"]
    assert [st.name for st in aut.states] == ["down", "up"]
    assert aut.init_state == "down"
    # Transition names follow the state names (frozen contract used by
    # the sequence filter: monitored basename == state name).
    assert aut.get_transition_by_name("up").source == "down"
    assert aut.get_transition_by_name("down").source == "up"


def test_zero_overhead_contract(pyc_session, monkeypatch):
    """ObjEvent registers no variables, no start/sensitive methods."""
    start_calls = []
    sensitive_calls = []

    orig_start = Pyc.CComponent.addStartMethod
    orig_var_sensitive = Pyc.IVariable.addSensitiveMethod
    orig_trans_sensitive = Pyc.ITransition.addSensitiveMethod

    def spy_start(self, name, fn):
        start_calls.append(name)
        return orig_start(self, name, fn)

    def spy_var_sensitive(self, name, fn):
        sensitive_calls.append(name)
        return orig_var_sensitive(self, name, fn)

    def spy_trans_sensitive(self, name, fn):
        sensitive_calls.append(name)
        return orig_trans_sensitive(self, name, fn)

    monkeypatch.setattr(Pyc.CComponent, "addStartMethod", spy_start)
    monkeypatch.setattr(Pyc.IVariable, "addSensitiveMethod", spy_var_sensitive)
    monkeypatch.setattr(Pyc.ITransition, "addSensitiveMethod", spy_trans_sensitive)

    system = PycSystem(name="EvtContractOverhead")
    system.add_component(name="box", cls="EvtSource")
    box = system.comp["box"]

    system.add_component(
        cls="ObjEvent",
        name="system_down",
        cond=lambda: box.working.value() is False,
    )
    ev = system.comp["system_down"]

    assert [v.basename() for v in ev.variables()] == []
    assert start_calls == []
    assert sensitive_calls == []


def test_callable_cond_drives_occ_and_negation(pyc_session):
    """cond drives occ; its automatic negation drives not_occ.

    The condition flip is driven by a real ObjFMDelay transition (a
    manual ``setValue`` does not wake the scheduler for timed
    transitions — isimu conditions re-evaluate on transition firings).
    """
    system = PycSystem(name="EvtContractCond")
    system.add_component(name="box", cls="EvtSource")
    box = system.comp["box"]
    cod3s.ObjFMDelay(
        fm_name="frun",
        targets=["box"],
        failure_param=2.0,
        repair_param=3.0,
        failure_effects={"working": False},
    )
    system.add_component(
        cls="ObjEvent",
        name="system_down",
        cond=lambda: box.working.value() is False,
    )
    aut = system.comp["system_down"].automata_d["ev"]

    system.isimu_start()

    # cond false -> only the ObjFMDelay failure is fireable.
    assert [
        (t.name, t.comp_name)
        for t in system.isimu_fireable_transitions()
        if t is not None
    ] == [("occ", "box__frun")]
    assert aut.get_state_by_name("not_occ")._bkd.isActive()

    # box fails at t=2 -> cond true -> the event occ (delay 0) fires.
    _fire_by_name(system, "occ", comp_name="box__frun")
    assert box.working.value() is False
    fired = _fire_by_name(system, "occ", comp_name="system_down")
    assert fired == ["occ"]
    assert aut.get_state_by_name("occ")._bkd.isActive()

    # box repairs at t=5 -> cond falls -> the negated condition drives
    # the return transition.
    _fire_by_name(system, "rep", comp_name="box__frun")
    assert box.working.value() is True
    fired = _fire_by_name(system, "not_occ", comp_name="system_down")
    assert fired == ["not_occ"]
    assert aut.get_state_by_name("not_occ")._bkd.isActive()

    system.isimu_stop()


def test_structured_cond_and_logic_strings(pyc_session):
    """Structured cond (attr tree) + 'all'/'any' logic strings compile."""
    system = PycSystem(name="EvtContractStruct")
    system.add_component(name="box", cls="EvtSource")
    box = system.comp["box"]
    cod3s.ObjFMDelay(
        fm_name="frun",
        targets=["box"],
        failure_param=2.0,
        repair_param=3.0,
        failure_effects={"working": False},
    )
    system.add_component(
        cls="ObjEvent",
        name="system_down",
        cond=[[{"obj": "box", "attr": "working", "ope": "==", "value": False}]],
        inner_logic="all",
        outer_logic="any",
    )
    aut = system.comp["system_down"].automata_d["ev"]

    system.isimu_start()
    _fire_by_name(system, "occ", comp_name="box__frun")
    assert box.working.value() is False
    fired = _fire_by_name(system, "occ", comp_name="system_down")
    assert fired == ["occ"]
    assert aut.get_state_by_name("occ")._bkd.isActive()
    system.isimu_stop()
