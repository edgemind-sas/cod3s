"""Interactive simulator (``cod3s-isimu``) building blocks.

The TUI layer (``app``, ``panels``) is loaded lazily but its dependency
(``textual``) is shipped as a default runtime requirement of the ``cod3s``
package. The non-TUI helpers below — the engine wrapping
``PycSystem.isimu_*`` plus utilities for grouping, diffing and exporting —
are pure Python and have no Textual dependency.

Versioning policy (see ``CLAUDE.md`` for the full rule):

* bump ``__version__`` by ``+0.0.1`` for a minor fix or doc-only change
* bump ``__version__`` by ``+0.1.0`` for a feature evolution (new bindings,
  new panel, new modal, breaking change in the engine API, etc.)

The version is independent from the parent ``cod3s`` package version; the
TUI ships its own cadence.
"""

__version__ = "0.3.0"

from cod3s.pycatshoo.isimu.engine import FiredEvent, ISimuEngine
from cod3s.pycatshoo.isimu.grouping import group_fires_together

__all__ = [
    "FiredEvent",
    "ISimuEngine",
    "__version__",
    "group_fires_together",
]
