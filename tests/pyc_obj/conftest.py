"""Shared fixtures for ``tests/pyc_obj/obj_fm/``.

Every test in this directory builds at least one ``PycSystem`` (the
ObjFM machinery has no purpose without one). PyCATSHOO is a
process-level singleton, so each test module must release it on
teardown — otherwise the next module fails with ``Il existe déjà un
système ...``. This fixture enforces the release at module scope,
removing the need for each test file to declare its own
``yield system + terminate_session()`` finaliser.

Test files that build their own per-function ``PycSystem`` (e.g. via
fixtures that also call ``terminate_session()``) are still safe —
``terminate()`` is idempotent when no system exists.
"""

import pytest

import cod3s


@pytest.fixture(autouse=True, scope="module")
def _release_pycatshoo_singleton():
    """Release the PyCATSHOO singleton at module teardown.

    Module scope (not function) because most fixtures in this directory
    build the system once per module and reuse it across tests. A
    function-scoped teardown would tear down the system between tests
    in the same module, breaking ordering.
    """
    yield
    cod3s.terminate_session()
