"""Shared loaders for COD3S CLI scripts.

These helpers were extracted from ``run_cod3s_study.py`` so that other entry-points
(notably the interactive simulator ``cod3s-isimu``) can reuse the YAML-based model
loading without duplicating code.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Optional

import yaml


def import_module_from_path(
    import_path: Path,
    target_namespace: dict,
    logger: Any = None,
) -> str:
    """Dynamically load a Python module from a file path.

    Public names from the loaded module are merged into ``target_namespace``.

    Args:
        import_path: Path to the ``.py`` file to import.
        target_namespace: Mutable mapping that will receive the public names of
            the loaded module (typically a caller-supplied dict, e.g.
            ``globals()`` of a CLI script).
        logger: Optional COD3S logger.

    Returns:
        A short message describing the import.

    Raises:
        FileNotFoundError: ``import_path`` does not exist.
        ImportError: the file could not be loaded as a Python module.
    """
    import_path = Path(import_path)
    if not import_path.exists():
        raise FileNotFoundError(f"Import file not found: {import_path}")

    import_dir = import_path.parent
    if str(import_dir) not in sys.path:
        sys.path.insert(0, str(import_dir))

    module_name = import_path.stem
    spec = importlib.util.spec_from_file_location(module_name, import_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for {import_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    for name in dir(module):
        if not name.startswith("_"):
            target_namespace[name] = getattr(module, name)

    msg = f"Dynamically imported: {import_path}"
    if logger is not None:
        logger.info(msg)
    return msg


def _resolve_imports(
    model_specs: dict,
    model_path: Path,
    namespace: dict,
    logger: Any = None,
) -> None:
    """Resolve the ``imports:`` list of a model YAML into ``namespace``.

    Each entry is searched first as an absolute/relative path from the current
    working directory, then relative to the model file's directory.
    """
    for import_file in model_specs.get("imports") or []:
        candidates = [
            Path(import_file).resolve(),
            (model_path.parent / import_file).resolve(),
        ]
        for candidate in candidates:
            if candidate.exists():
                import_module_from_path(candidate, namespace, logger=logger)
                break
        else:
            error_msg = (
                f"Import file not found: {import_file} "
                "(searched in current directory and model directory)"
            )
            if logger is not None:
                logger.error(error_msg)
            raise FileNotFoundError(error_msg)


def build_system_from_model(
    model_path: Path,
    namespace: Optional[dict] = None,
    logger: Any = None,
):
    """Build and populate a system from a YAML model file.

    The YAML must follow the same layout as the one consumed by
    ``run-cod3s-study``: ``imports:`` (list of Python files to load), ``system:``
    (with ``python_class`` and other constructor kwargs), ``components:`` and
    ``connections:``.

    Args:
        model_path: Path to the model YAML file.
        namespace: Mutable dict where dynamic imports will be exposed. If
            ``None``, a fresh dict is created. Pass an existing ``globals()``
            when running inside a CLI script that needs to keep references.
        logger: Optional COD3S logger.

    Returns:
        The populated system instance (``PycSystem`` or subclass).

    Raises:
        FileNotFoundError: model file or one of its imports is missing.
        NameError: declared ``python_class`` cannot be resolved.
    """
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model specification file '{model_path}' not found!")

    with open(model_path, "r") as f:
        model_specs = yaml.safe_load(f) or {}

    if logger is not None:
        logger.info2(f"Loaded model specifications from '{model_path}'")

    if namespace is None:
        namespace = {}

    _resolve_imports(model_specs, model_path, namespace, logger=logger)

    system_specs = dict(model_specs.get("system") or {})
    system_cls_name = system_specs.pop("python_class", "PycSystem")

    if system_cls_name in namespace:
        system_cls = namespace[system_cls_name]
    elif system_cls_name == "PycSystem":
        from cod3s.pycatshoo.system import PycSystem

        system_cls = PycSystem
    else:
        raise NameError(
            f"System class '{system_cls_name}' not found. "
            "Make sure to import the file containing this class "
            "using the 'imports' key in the YAML model file."
        )

    system = system_cls(**system_specs)
    if logger is not None:
        logger.info1(f"{system.__class__.__name__} {system.name()} created")

    if logger is not None:
        logger.info1("Add components")
    system.add_components(model_specs.get("components") or [], logger=logger)
    if logger is not None:
        logger.info1("Add connections")
    system.add_connections(model_specs.get("connections") or [], logger=logger)

    return system


def load_study_specs(study_specs_path: Path, logger: Any = None) -> dict:
    """Load a study specifications YAML if it exists.

    Returns an empty dict when the file is absent (matching the behavior of
    ``run-cod3s-study``: missing study specs is not fatal).
    """
    study_specs_path = Path(study_specs_path)
    if not study_specs_path.exists():
        if logger is not None:
            logger.warning(f"Study specifications file '{study_specs_path}' not found!")
        return {}
    with open(study_specs_path, "r") as f:
        data = yaml.safe_load(f) or {}
    if logger is not None:
        logger.info2(f"Loaded study specifications from '{study_specs_path}'")
    return data
