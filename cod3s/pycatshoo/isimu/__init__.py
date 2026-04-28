"""Interactive simulator (``cod3s-isimu``) building blocks.

The TUI layer (``app``, ``panels``) is loaded lazily because it depends on the
optional ``textual`` package. The non-TUI helpers below — the engine wrapping
``PycSystem.isimu_*`` plus utilities for grouping, diffing and exporting — are
plain Python and importable without the ``[isimu]`` extra installed.
"""

from cod3s.pycatshoo.isimu.engine import FiredEvent, ISimuEngine
from cod3s.pycatshoo.isimu.grouping import group_fires_together

__all__ = [
    "FiredEvent",
    "ISimuEngine",
    "group_fires_together",
]
