"""Test fixtures for tests/scripts/.

PyCATSHOO is a process-level singleton. Any test that builds a ``PycSystem``
must clean up via ``terminate_session()`` so subsequent test modules get a
fresh slate.
"""

import pytest


@pytest.fixture
def terminate_pyc_after():
    """Ensure ``Pycatshoo.CSystem.terminate()`` is called when the test ends.

    Use as ``def test_foo(tmp_path, terminate_pyc_after): ...``. Tests that do
    not instantiate a ``PycSystem`` should not request this fixture.
    """
    yield
    from cod3s import terminate_session

    terminate_session()
