"""Auto-discovery of ObjFM via the attached ``PycSystem``.

When the analyser is built from a live system (typically through
``SequenceAnalyser.from_pyc_system(system)``), the system is stored
as a private attribute. ``filter_objfm_cycles()`` called with neither
``objfm_internal`` nor ``objfm_external`` then introspects the system
and discovers the ObjFM automatically, dispatching them by
``behaviour`` and honouring each one's ``failure_state`` /
``repair_state``.
"""

import pytest

import cod3s
from cod3s.pycatshoo.sequence import SeqEvent, Sequence, SequenceAnalyser
from cod3s.pycatshoo.system import PycSystem


@pytest.fixture(autouse=True)
def cleanup():
    yield
    cod3s.terminate_session()


def _ev(obj, attr, t=0.0):
    return SeqEvent(obj=obj, attr=attr, time=t, type=None)


def _seq(*events, target="top", weight=1):
    return Sequence(
        probability=None,
        weight=weight,
        end_time=None,
        target_name=target,
        events=list(events),
    )


# ---------------------------------------------------------------------------
# Auto-discovery: internal mode
# ---------------------------------------------------------------------------


def test_autodiscover_internal_objfm_from_system():
    """An ObjFM in internal mode is auto-discovered and its
    occ__cc_X / rep__cc_X pairs are filtered without the caller
    specifying any name."""
    system = PycSystem(name="AutoDiscoverInternal")
    for n in ("c1", "c2"):
        system.add_component(name=n, cls="PycComponent")
    system.add_component(
        cls="ObjFMExp",
        fm_name="def_pump",
        targets=["c1", "c2"],
        behaviour="internal",
        failure_param=[(0.1,), (0.01,)],
        repair_param=[(0.5,), (0.1,)],
    )

    # The ObjFM's component name is target_name__fm_name; with c1+c2,
    # target_name is "cX" (factorisation: common char + 'X' separator).
    fm_obj = "cX__def_pump"

    # Build an analyser with a paired cc_1 occ/rep then an unrepaired
    # cc_2 occ and the top event.
    seq = _seq(
        _ev(fm_obj, "occ__cc_1"),
        _ev(fm_obj, "rep__cc_1"),
        _ev(fm_obj, "occ__cc_2"),
        _ev("top", "occ"),
    )
    analyser = SequenceAnalyser(sequences=[seq])
    analyser._system = system  # simulate from_pyc_system attaching the ref

    result = analyser.filter_objfm_cycles(inplace=False)  # ← no args
    assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
        (fm_obj, "occ__cc_2"),
        ("top", "occ"),
    ]


def test_from_pyc_system_attaches_the_system():
    """``from_pyc_system`` must set ``_system`` so subsequent
    introspecting methods can use it."""
    system = PycSystem(name="AutoDiscoverAttach")
    system.add_component(name="c1", cls="PycComponent")
    analyser = SequenceAnalyser.from_pyc_system(system)
    assert analyser._system is system


def test_autodiscover_external_objfm_from_system():
    """An ObjFM in external mode is auto-discovered, its own events
    are dropped, and target-side prefixed pairs are filtered."""
    from kb_test import ObjFlow  # noqa: F401

    system = PycSystem(name="AutoDiscoverExternal")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")
    system.add_component(name="C1", cls="ObjFlow")
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        behaviour="external",
        failure_param=0.1,
        repair_param=0.1,
    )

    fm_obj = "C1__frun"
    seq = _seq(
        _ev(fm_obj, "occ"),
        _ev("C1", "frun__occ"),
        _ev("C1", "frun__rep"),
        _ev(fm_obj, "rep"),
        _ev(fm_obj, "occ"),  # unrepaired ObjFM event (will be dropped)
        _ev("C1", "frun__occ"),  # unrepaired target event (will be kept)
        _ev("top", "occ"),
    )
    analyser = SequenceAnalyser(sequences=[seq])
    analyser._system = system

    result = analyser.filter_objfm_cycles(inplace=False)
    assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
        ("C1", "frun__occ"),
        ("top", "occ"),
    ]


def test_autodiscover_mixed_internal_and_external():
    """A system with one ObjFM internal and one external is partitioned
    correctly: the internal pairs are filtered as ObjFM-side, the
    external one drops the ObjFM events and the prefixed target pairs."""
    from kb_test import ObjFlow  # noqa: F401

    system = PycSystem(name="AutoDiscoverMixed")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")
    system.add_component(name="C1", cls="ObjFlow")
    system.add_component(name="C2", cls="ObjFlow")

    # Internal ObjFM on C1
    system.add_component(
        cls="ObjFMExp",
        fm_name="fm_int",
        targets=["C1"],
        behaviour="internal",
        failure_param=0.1,
        repair_param=0.1,
    )
    # External ObjFM on C2
    system.add_component(
        cls="ObjFMExp",
        fm_name="fm_ext",
        targets=["C2"],
        behaviour="external",
        failure_param=0.1,
        repair_param=0.1,
    )

    fm_int_obj = "C1__fm_int"
    fm_ext_obj = "C2__fm_ext"

    seq = _seq(
        _ev(fm_int_obj, "occ"),  # internal-mode: paired
        _ev(fm_int_obj, "rep"),
        _ev(fm_ext_obj, "occ"),  # external-mode: dropped entirely
        _ev("C2", "fm_ext__occ"),  # external-mode target: paired
        _ev("C2", "fm_ext__rep"),
        _ev(fm_ext_obj, "rep"),
        _ev("top", "occ"),
    )
    analyser = SequenceAnalyser(sequences=[seq])
    analyser._system = system

    result = analyser.filter_objfm_cycles(inplace=False)
    # All non-top events have been filtered: the internal pair, the
    # external ObjFM events, and the external target pair.
    assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
        ("top", "occ"),
    ]


def test_explicit_lists_override_autodiscover():
    """Passing one of the lists explicitly disables auto-discovery for
    BOTH buckets (the caller has taken control)."""
    system = PycSystem(name="OverrideAutoDiscover")
    for n in ("c1", "c2"):
        system.add_component(name=n, cls="PycComponent")
    system.add_component(
        cls="ObjFMExp",
        fm_name="fm",
        targets=["c1", "c2"],
        behaviour="internal",
        failure_param=[(0.1,), (0.01,)],
        repair_param=[(0.5,), (0.1,)],
    )
    fm_obj = "cX__fm"

    seq = _seq(
        _ev(fm_obj, "occ__cc_1"),
        _ev(fm_obj, "rep__cc_1"),
        _ev("top", "occ"),
    )
    analyser = SequenceAnalyser(sequences=[seq])
    analyser._system = system

    # Pass empty internal list explicitly → auto-discovery disabled →
    # the cc_1 pair is NOT filtered.
    result = analyser.filter_objfm_cycles(objfm_internal=[], inplace=False)
    assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
        (fm_obj, "occ__cc_1"),
        (fm_obj, "rep__cc_1"),
        ("top", "occ"),
    ]


def test_filter_objfm_cycles_preserves_system_ref_through_chaining():
    """The not-inplace path returns a new analyser; the system ref
    must propagate so chained calls keep auto-discovery."""
    system = PycSystem(name="ChainedRef")
    system.add_component(name="c1", cls="PycComponent")
    analyser = SequenceAnalyser(sequences=[])
    analyser._system = system
    result = analyser.filter_objfm_cycles(inplace=False)
    assert result._system is system


def test_no_system_attached_no_args_is_noop():
    """When neither a system is attached nor any list is passed, the
    call only re-groups — equivalent to ``group_sequences()``."""
    s1 = _seq(_ev("c1", "occ"))
    s2 = _seq(_ev("c1", "occ"))
    analyser = SequenceAnalyser(sequences=[s1, s2])
    assert analyser._system is None  # no system attached
    result = analyser.filter_objfm_cycles(inplace=False)
    # Just group_sequences was called; the two identical sequences
    # collapse into one with weight=2.
    assert len(result.sequences) == 1
    assert result.sequences[0].weight == 2
