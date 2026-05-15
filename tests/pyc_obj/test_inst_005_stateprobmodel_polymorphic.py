"""Regression test for T11a: ``StateProbModel`` is an ``ObjCOD3S``.

Before T11a, ``StateProbModel`` inherited directly from
``pydantic.BaseModel``, so it lacked the ``cls`` discriminator stamped by
``ObjCOD3S.model_dump``. The serialised form therefore had no way to
identify the concrete class on reload — any subclass (e.g. a future
``WeightedStateProbModel``) would silently down-cast to the base. Now
that ``StateProbModel`` inherits ``ObjCOD3S`` and the ``target`` field
on ``TransitionModel`` is ``SerializeAsAny[...]``, round-trip is
faithful.
"""

import pytest

from cod3s.core import ObjCOD3S
from cod3s.pycatshoo.automaton import StateProbModel, PycTransition


def test_state_prob_model_is_objcod3s():
    """``StateProbModel`` must be a subclass of ``ObjCOD3S`` to enable
    polymorphic serialisation."""
    assert issubclass(StateProbModel, ObjCOD3S)


def test_state_prob_model_dump_carries_cls():
    """``model_dump`` must emit the ``cls`` discriminator."""
    branch = StateProbModel(state="ok", prob=0.7)
    dumped = branch.model_dump()
    assert dumped["cls"] == "StateProbModel"
    assert dumped["state"] == "ok"
    assert dumped["prob"] == 0.7


def test_state_prob_model_roundtrip_via_from_dict():
    """A dumped branch must reload as a ``StateProbModel`` instance."""
    original = StateProbModel(state="ok", prob=0.7, effects={"x": 1})
    rebuilt = ObjCOD3S.from_dict(original.model_dump())
    assert isinstance(rebuilt, StateProbModel)
    assert rebuilt.state == "ok"
    assert rebuilt.prob == 0.7
    assert rebuilt.effects == {"x": 1}


def test_transition_target_branches_carry_cls_after_dump():
    """When dumped as part of a ``PycTransition``, each branch must
    include its ``cls`` discriminator (via ``SerializeAsAny`` on the
    ``target`` field)."""
    trans = PycTransition(
        name="branch",
        source="src",
        target=[
            {"state": "a", "prob": 0.4},
            {"state": "b", "prob": 0.6},
        ],
    )
    dumped = trans.model_dump()
    assert isinstance(dumped["target"], list)
    for branch in dumped["target"]:
        assert branch["cls"] == "StateProbModel"


def test_transition_validator_accepts_stateprobmodel_instances():
    """The ``TransitionModel`` validator must accept ``target`` as a list
    of already-built ``StateProbModel`` instances (not just plain dicts).
    This path is taken when the transition is rebuilt from a dumped
    representation that has been partially deserialised by
    ``ObjCOD3S.from_dict``.
    """
    branches = [
        StateProbModel(state="a", prob=0.4),
        StateProbModel(state="b", prob=0.6),
    ]
    trans = PycTransition(name="branch", source="src", target=branches)
    assert len(trans.target) == 2
    for branch in trans.target:
        assert isinstance(branch, StateProbModel)
    assert trans.target[0].state == "a"
    assert trans.target[0].prob == pytest.approx(0.4)
    assert trans.target[1].state == "b"
    assert trans.target[1].prob == pytest.approx(0.6)


def test_transition_validator_accepts_mixed_branches():
    """The validator must accept a list mixing ``StateProbModel``
    instances and raw dicts in the same call. This shape is unusual but
    valid: callers can build half their branches from existing models
    and half from user-supplied dicts."""
    branches = [
        StateProbModel(state="a", prob=0.3),
        {"state": "b", "prob": 0.5},
        {"state": "c"},  # complement-share branch
    ]
    trans = PycTransition(name="branch", source="src", target=branches)
    assert len(trans.target) == 3
    for branch in trans.target:
        assert isinstance(branch, StateProbModel)
    # The complement branch should receive the residual 1 - 0.3 - 0.5 = 0.2.
    assert trans.target[0].prob == pytest.approx(0.3)
    assert trans.target[1].prob == pytest.approx(0.5)
    assert trans.target[2].prob == pytest.approx(0.2)
