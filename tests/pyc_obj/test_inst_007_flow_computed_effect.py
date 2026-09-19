"""An effect on a flow-computed variable is refused, not left to livelock.

A discrete output's ``<flow>_prod`` is re-assigned from
``<flow>_prod_available`` on every evaluation of the flow's own sensitive
method (``muscadet.flow``). An effect clamping it to another value
contradicts that assignment, each method sees a value that is not its own
and writes again, and the two wake each other for ever: the run never
ends AND prints nothing, which is indistinguishable from a slow
simulation. Two components are enough to reproduce it.

Measured before the guard, on a Source -> MR model with a mode clamping
``DISPO_prod``: ``simulate()`` ran past 90 s on 5 sequences over a 100 h
horizon, where the same model targeting ``DISPO_fed_available_out``
finishes in 0.00 s.

The refusal itself is unit-tested here rather than through a live system:
the failure it prevents is a non-terminating run, which no test can
observe without hanging, and the guard needs nothing from PyCATSHOO.
"""

import pytest

from cod3s.pycatshoo.component import ObjMode2S


class _FakeTarget:
    """The two things the guard reads off a target component."""

    def __init__(self, flows_out):
        self.flows_out = flows_out

    def name(self):
        return "S"


@pytest.mark.parametrize("var", ["DISPO_prod", "K.RAIL.CASSE_prod"])
def test_effect_on_a_flow_prod_is_refused(var):
    """The refusal names both variables an effect may target instead."""
    target = _FakeTarget({"DISPO": object(), "K.RAIL.CASSE": object()})
    with pytest.raises(ValueError, match="livelock") as exc:
        ObjMode2S._reject_flow_computed_effect(target, var)
    message = str(exc.value)
    assert "_prod_available" in message
    assert "_fed_available_out" in message


@pytest.mark.parametrize(
    "var",
    [
        "DISPO_prod_available",  # the real input of the computation
        "DISPO_fed_available_out",  # the output gate
        "DISPO_fed_out",  # not covered: only _prod is proven to livelock
        "DISPO",  # the flow itself, resolved elsewhere
        "some_business_prod",  # no flow of that name: not a flow variable
    ],
)
def test_everything_else_stays_accepted(var):
    """The guard is narrow on purpose: it refuses only what it has proven."""
    target = _FakeTarget({"DISPO": object()})
    ObjMode2S._reject_flow_computed_effect(target, var)


def test_a_target_without_flows_is_accepted():
    """A mode may target a component carrying no flow at all."""
    ObjMode2S._reject_flow_computed_effect(_FakeTarget({}), "anything_prod")
