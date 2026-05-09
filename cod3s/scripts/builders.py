"""System builders for the COD3S study runner.

A :class:`SystemBuilder` is anything that can produce a populated
``PycSystem`` ready for simulation. Decoupling system construction
from the rest of the study pipeline lets consumers plug their own
builder (eg. a JSON-export-driven one) without forking the runner.

Available implementations:

* :class:`YamlModelBuilder` — default, reads a YAML model file in the
  layout consumed by ``run-cod3s-study`` (``imports:`` /
  ``system:`` / ``components:`` / ``connections:``).
* External builders (eg. ``muscadet.builders.PlatformExportBuilder``)
  must satisfy the :class:`SystemBuilder` Protocol and live in their
  own package — cod3s-lib does not import third-party modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

from cod3s.scripts._common import build_system_from_model


@runtime_checkable
class SystemBuilder(Protocol):
    """Anything that can build a populated ``PycSystem``.

    The builder is invoked exactly once per study run, before the
    failure modes / events / indicators are wired. Builders are free
    to do their own validation (raise early) or be lazy.

    Implementations should accept a ``logger`` kwarg in :meth:`build`
    so the runner can stream progress messages.
    """

    def build(self, *, logger: Any = None) -> Any:
        """Construct and return the ``PycSystem`` (or subclass).

        Returns:
            A populated system. The type is intentionally ``Any``
            because cod3s-lib must work with both ``PycSystem`` and
            user-defined subclasses.

        Raises:
            Any exception relevant to the underlying construction
            failure (file not found, malformed input, …). The runner
            catches these and surfaces them via the logger.
        """


class YamlModelBuilder:
    """Default builder: reads a YAML model file.

    The YAML must follow the layout described in
    ``cod3s.scripts._common.build_system_from_model``:

    .. code-block:: yaml

        imports:
          - my_classes.py    # python files defining custom classes
        system:
          python_class: MySystem
          name: my_system
        components:
          - cls: MyComponent
            name: comp1
        connections:
          - source: comp1
            target: comp2
            flow_name: my_flow

    Args:
        model_path: Path to the YAML model file.
        namespace: Optional dict that receives dynamically-imported
            symbols (typically a CLI ``globals()``). When omitted, a
            fresh dict is allocated and discarded after :meth:`build`.

    Why ``namespace`` matters: the YAML's ``imports:`` clause loads
    Python files via ``import_module_from_path``, which exposes
    public names in the caller-supplied dict. A CLI script that
    references those names elsewhere must pass its own ``globals()``.
    """

    def __init__(
        self,
        model_path: Path | str,
        namespace: Optional[dict] = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.namespace = namespace

    def build(self, *, logger: Any = None) -> Any:
        return build_system_from_model(
            self.model_path,
            namespace=self.namespace if self.namespace is not None else {},
            logger=logger,
        )

    def __repr__(self) -> str:
        return f"YamlModelBuilder(model_path={str(self.model_path)!r})"


__all__ = ["SystemBuilder", "YamlModelBuilder"]
