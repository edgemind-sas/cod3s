"""Minimal instantaneous-branching demo for ``cod3s-isimu``.

A single ``coin`` component that repeatedly tosses with two equal-probability
outcomes (``heads`` and ``tails``). Designed to be the simplest possible
walkthrough of the inst pending UX:

* One integer variable ``face`` recording the most recent outcome
  (``0`` initially, ``1`` for heads, ``-1`` for tails). The Components panel
  shows ``coin.face`` cycling as the user resolves successive tosses —
  this is the per-branch effects pattern in its simplest form.
* The toss is implemented as one inst transition with two branches; after
  landing on ``heads`` or ``tails``, a ``delay(1)`` returns to ``tossing``,
  re-arming the inst transition for the next toss.

How to run
----------

With ``uv`` (recommended)::

    PYTHONPATH="examples/inst_coin_demo:$PYTHONPATH" \\
        uv run cod3s-isimu --factory inst_coin_demo:build_system

Or directly::

    PYTHONPATH="examples/inst_coin_demo:$PYTHONPATH" \\
        uv run python examples/inst_coin_demo/inst_coin_demo.py

What you should see
-------------------

At t=0 the **fireable transitions** panel switches to *inst pending* mode
(a tree, not a table). One root entry::

    coin.toss   (2 branches)
      [●] → heads  (p=0.500)
      [ ] → tails  (p=0.500)

The first branch is selected by default (highest probability — here a tie
broken by order of declaration). To change the choice, navigate the tree
and press **Enter** on the desired leaf. To submit, press **s** — both
candidates are sent in one atomic call to PyCATSHOO and the active state
of ``aut_coin`` updates accordingly.

Once the inst is resolved the panel reverts to its **timed** mode and you
see the next ``delay(1)`` transition that brings the coin back to
``tossing`` for the next toss.

Try it
------

#. ``s``                 → accept defaults, the coin lands on ``heads``.
#. ``Enter`` then ``s``  → re-arm ``tossing`` and submit a new toss
                            (the inst panel is back).
#. Navigate to ``tails`` then ``s``  → force a heads/tails alternation.

Layout
------

==========  ==========================  ============================
Component   Variable                    Automaton states
==========  ==========================  ============================
coin        face (int, initial 0)       tossing, heads, tails
==========  ==========================  ============================

Brainstorm 2026-05-05 (key decisions #1, #2, #3): one source state, one
guard implicit (always ``True`` here), N branches with distinct target
states; identifiers are state names — no separate "branch name".
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s
from cod3s.pycatshoo.automaton import PycAutomaton


class Coin(cod3s.PycComponent):
    """Coin component with a single integer ``face`` variable.

    ``face`` records the most recent toss outcome (``0`` initially,
    ``1`` for heads, ``-1`` for tails). Updated by per-branch effects
    on the inst transition.
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.face = self.addVariable("face", Pyc.TVarType.t_int, 0)


def build_system() -> cod3s.PycSystem:
    """Build the coin-toss showcase.

    Returns a populated ``PycSystem`` ready to be passed to
    ``cod3s.pycatshoo.isimu.app.run_isimu`` (entry-point used by
    ``cod3s-isimu --factory``).
    """
    system = cod3s.PycSystem(name="InstCoinDemo")

    coin = system.add_component(name="coin", cls="Coin")

    aut = PycAutomaton(
        name="aut_coin",
        states=["tossing", "heads", "tails"],
        init_state="tossing",
        transitions=[
            # Inst transition: 50/50 between heads and tails. Each branch
            # carries its own per-branch effect on the ``face`` variable.
            {
                "name": "toss",
                "source": "tossing",
                "target": [
                    {"state": "heads", "prob": 0.5, "effects": {"face": 1}},
                    {"state": "tails", "prob": 0.5, "effects": {"face": -1}},
                ],
            },
            # Re-arm: delay(1) returns to tossing from each landing state.
            {
                "name": "heads_done",
                "source": "heads",
                "target": "tossing",
                "occ_law": {"cls": "delay", "time": 1},
            },
            {
                "name": "tails_done",
                "source": "tails",
                "target": "tossing",
                "occ_law": {"cls": "delay", "time": 1},
            },
        ],
    )
    aut.update_bkd(coin)
    # Wire the per-branch effects on the target states.
    coin.register_branch_effects(aut, "toss", aut.transitions[0].target)

    return system


if __name__ == "__main__":
    # Convenience: run the file directly to launch the TUI.
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
