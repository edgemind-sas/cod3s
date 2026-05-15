"""Interactive simulator (``cod3s-isimu``) building blocks.

The TUI layer (``app``, ``panels``) is loaded lazily but its dependency
(``textual``) is shipped as a default runtime requirement of the ``cod3s``
package. The non-TUI helpers below — the engine wrapping
``PycSystem.isimu_*`` plus utilities for grouping, diffing and exporting —
are pure Python and have no Textual dependency.

The interactive simulator does not ship its own version: it follows the
parent ``cod3s`` package (see ``cod3s.version``).
"""

from cod3s.pycatshoo.isimu.engine import FiredEvent, ISimuEngine
from cod3s.pycatshoo.isimu.grouping import group_fires_together

__all__ = [
    "FiredEvent",
    "ISimuEngine",
    "group_fires_together",
]
