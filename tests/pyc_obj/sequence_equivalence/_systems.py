"""Variants of test systems used to validate that ``from_pyc_system``
and the XML round-trip produce identical sequence analyses.

Each factory builds a self-contained ``PycSystem`` exercising a
different facet of the ObjFM API. Naming convention:

* ``build_<name>_system()`` — returns a ``PycSystem`` ready to
  simulate (target wired, monitorTransition active for the XML path).
* The factory does not register a ``setResultFileName`` — the test
  harness does it on a temp directory.
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


class Pump(cod3s.PycComponent):
    """Pump with a single ``working`` boolean variable, flipped by
    ``failure_effects`` and restored by ``setReinitialized(True)`` on
    repair."""

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


class Sensor(cod3s.PycComponent):
    """Sensor with a separate ``healthy`` variable so we can have
    two ObjFM acting on different attributes."""

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.healthy = self.addVariable("healthy", Pyc.TVarType.t_bool, True)
        self.healthy.setReinitialized(True)


# ---------------------------------------------------------------------------
# System 1 — CCF order-2 internal mode (the canonical bug reproducer)
# ---------------------------------------------------------------------------


def build_ccf_order2_internal_system(name="CCF_O2_Internal"):
    """2 pumps + 1 order-2 CCF in internal mode.

    Top event: both pumps simultaneously ``working=False``.
    """
    system = cod3s.PycSystem(name=name)
    system.add_component(name="pump_1", cls="Pump")
    system.add_component(name="pump_2", cls="Pump")
    system.add_component(
        cls="ObjFMExp",
        fm_name="def",
        targets=["pump_1", "pump_2"],
        behaviour="internal",
        failure_effects={"working": False},
        failure_param=[(2.79e-04,), (4.19e-05,)],
        repair_param=[(6.72e-03,), (3.76e-01,)],
    )
    system.add_component(
        cls="ObjEvent",
        name="system_down",
        cond=[[
            {"obj": "pump_1", "attr": "working", "ope": "==", "value": False},
            {"obj": "pump_2", "attr": "working", "ope": "==", "value": False},
        ]],
    )
    system.addTarget("system_down_target", "system_down.occ", "ST")
    system.monitorTransition("#.*")
    return system


# ---------------------------------------------------------------------------
# System 2 — CCF order-3 internal mode (more combos)
# ---------------------------------------------------------------------------


def build_ccf_order3_internal_system(name="CCF_O3_Internal"):
    """3 pumps + 1 order-3 CCF in internal mode.

    Generates 2^3 - 1 = 7 ObjFM automata: cc_1, cc_2, cc_3, cc_12,
    cc_13, cc_23, cc_123. Top event: 2 of 3 pumps down.
    """
    system = cod3s.PycSystem(name=name)
    for n in ("pump_1", "pump_2", "pump_3"):
        system.add_component(name=n, cls="Pump")
    system.add_component(
        cls="ObjFMExp",
        fm_name="def",
        targets=["pump_1", "pump_2", "pump_3"],
        behaviour="internal",
        failure_effects={"working": False},
        # order 1, 2, 3 rates
        failure_param=[(3e-04,), (5e-05,), (8e-06,)],
        repair_param=[(7e-03,), (4e-01,), (5e-01,)],
    )
    # Top: at least 2 of 3 pumps down (a "2 out of 3" voting failure).
    system.add_component(
        cls="ObjEvent",
        name="degraded",
        cond=[
            [
                {"obj": "pump_1", "attr": "working", "ope": "==", "value": False},
                {"obj": "pump_2", "attr": "working", "ope": "==", "value": False},
            ],
            [
                {"obj": "pump_1", "attr": "working", "ope": "==", "value": False},
                {"obj": "pump_3", "attr": "working", "ope": "==", "value": False},
            ],
            [
                {"obj": "pump_2", "attr": "working", "ope": "==", "value": False},
                {"obj": "pump_3", "attr": "working", "ope": "==", "value": False},
            ],
        ],
    )
    system.addTarget("degraded_target", "degraded.occ", "ST")
    system.monitorTransition("#.*")
    return system


# ---------------------------------------------------------------------------
# System 3 — mixed internal + external on disjoint targets
# ---------------------------------------------------------------------------


def build_mixed_internal_external_system(name="Mixed_Int_Ext"):
    """Two component groups: pumps with an internal-mode ObjFM, sensors
    with an external-mode ObjFM. Top event combines both.

    Stresses the auto-discovery dispatch (the two ObjFM are routed to
    different buckets in ``_discover_objfm_specs``) and the
    independence of the filters.
    """
    system = cod3s.PycSystem(name=name)
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")
    # Pumps with an internal-mode CCF (order 2).
    for n in ("pump_1", "pump_2"):
        system.add_component(name=n, cls="Pump")
    system.add_component(
        cls="ObjFMExp",
        fm_name="pump_def",
        targets=["pump_1", "pump_2"],
        behaviour="internal",
        failure_effects={"working": False},
        failure_param=[(2.79e-04,), (4.19e-05,)],
        repair_param=[(6.72e-03,), (3.76e-01,)],
    )
    # Sensors with an external-mode ObjFM (order 1, single target each).
    for n in ("sensor_1", "sensor_2"):
        system.add_component(name=n, cls="Sensor")
    system.add_component(
        cls="ObjFMExp",
        fm_name="sensor_def",
        targets=["sensor_1"],
        behaviour="external",
        failure_param=2.0e-04,
        repair_param=1.0e-02,
    )
    system.add_component(
        cls="ObjFMExp",
        fm_name="sensor_def",
        targets=["sensor_2"],
        behaviour="external",
        failure_param=2.0e-04,
        repair_param=1.0e-02,
    )
    # Top: both pumps down OR both sensors down.
    system.add_component(
        cls="ObjEvent",
        name="mixed_top",
        cond=[
            [
                {"obj": "pump_1", "attr": "working", "ope": "==", "value": False},
                {"obj": "pump_2", "attr": "working", "ope": "==", "value": False},
            ],
            [
                {"obj": "sensor_1", "attr": "healthy", "ope": "==", "value": False},
                {"obj": "sensor_2", "attr": "healthy", "ope": "==", "value": False},
            ],
        ],
    )
    system.addTarget("mixed_top_target", "mixed_top.occ", "ST")
    system.monitorTransition("#.*")
    return system


# ---------------------------------------------------------------------------
# System 4 — external_rep_indep mode
# ---------------------------------------------------------------------------


def build_external_rep_indep_system(name="ExtRepIndep"):
    """2 pumps + ObjFMDelay external_rep_indep (the trigger model).

    Uses delays rather than exponentials, which gives a determinism
    that's good for cross-check at small N — but still exercises the
    full filter pipeline including the ``rm_events_by_obj`` for the
    ObjFM-side events.
    """
    system = cod3s.PycSystem(name=name)
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")
    for n in ("pump_1", "pump_2"):
        system.add_component(name=n, cls="Pump")
    system.add_component(
        cls="ObjFMDelay",
        fm_name="def",
        targets=["pump_1", "pump_2"],
        behaviour="external_rep_indep",
        failure_effects={"working": False},
        # order-1 ttf (per pump independent) + order-2 ttf
        failure_param=[(20.0,), (50.0,)],
        repair_param=[(10.0,), (10.0,)],
    )
    system.add_component(
        cls="ObjEvent",
        name="both_down",
        cond=[[
            {"obj": "pump_1", "attr": "working", "ope": "==", "value": False},
            {"obj": "pump_2", "attr": "working", "ope": "==", "value": False},
        ]],
    )
    system.addTarget("both_down_target", "both_down.occ", "ST")
    system.monitorTransition("#.*")
    return system
