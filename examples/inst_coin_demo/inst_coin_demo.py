"""Minimal instantaneous-branching demo for ``cod3s-isimu``.

A single ``coin`` component that repeatedly tosses with two equal-probability
outcomes (``heads`` and ``tails``). Designed to be the simplest possible
walkthrough of the inst pending UX:

* No effects, no extra variables — the result is just the active state of
  the coin's automaton.
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
coin        (none)                      tossing, heads, tails
==========  ==========================  ============================

Brainstorm 2026-05-05 (key decisions #1, #2, #3): one source state, one
guard implicit (always ``True`` here), N branches with distinct target
states; identifiers are state names — no separate "branch name".
"""

from __future__ import annotations

import cod3s
from cod3s.pycatshoo.automaton import PycAutomaton


def build_system() -> cod3s.PycSystem:
    """Build the coin-toss showcase.

    Returns a populated ``PycSystem`` ready to be passed to
    ``cod3s.pycatshoo.isimu.app.run_isimu`` (entry-point used by
    ``cod3s-isimu --factory``).
    """
    system = cod3s.PycSystem(name="InstCoinDemo")

    coin = system.add_component(name="coin", cls="PycComponent")

    aut = PycAutomaton(
        name="aut_coin",
        states=["tossing", "heads", "tails"],
        init_state="tossing",
        transitions=[
            # Inst transition: 50/50 between heads and tails.
            {
                "name": "toss",
                "source": "tossing",
                "target": [
                    {"state": "heads", "prob": 0.5},
                    {"state": "tails", "prob": 0.5},
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

    return system


if __name__ == "__main__":
    # Convenience: run the file directly to launch the TUI.
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
