"""Tests for the ``cod3s-seq`` entry-point.

Argparse logic is exercised through ``_build_parser``; ``--help`` and
``--version`` are verified via subprocess to ensure the console_script
is wired up correctly in ``pyproject.toml``.

The loader path is tested through ``main(argv)`` by pointing it at a
real JSON cod3s file produced via ``persist_sequence_analysis_artifacts``,
with the Textual ``run_seq_tui`` monkey-patched so no TUI mainloop runs.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cod3s.scripts.run_cod3s_seq import _build_parser, main


# ---------------------------------------------------------------------------
# Subprocess smoke (console_script)
# ---------------------------------------------------------------------------


def test_help_runs_via_subprocess() -> None:
    """``cod3s-seq --help`` must exit 0 and mention the key options."""
    result = subprocess.run(
        ["cod3s-seq", "--help"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    # Positional arg + most distinctive options.
    assert "sequences_file" in result.stdout
    assert "--pipeline" in result.stdout
    assert "--format" in result.stdout
    assert "Textual TUI" in result.stdout


def test_version_runs_via_subprocess() -> None:
    """``cod3s-seq --version`` prints the parent cod3s package version."""
    import cod3s

    result = subprocess.run(
        ["cod3s-seq", "--version"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert cod3s.__version__ in result.stdout


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------


def test_parser_requires_input_file() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_accepts_pipeline_option(tmp_path: Path) -> None:
    parser = _build_parser()
    ns = parser.parse_args(
        ["some.xml", "--pipeline", "pipe.yaml"]
    )
    assert ns.sequences_file == "some.xml"
    assert ns.pipeline == "pipe.yaml"
    assert ns.format is None  # auto-detect


def test_parser_format_choices() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["x.xml", "--format", "yaml"])  # not a choice


# ---------------------------------------------------------------------------
# main() — loader path with TUI bypassed
# ---------------------------------------------------------------------------


def _write_synthetic_json_cod3s(path: Path) -> None:
    """Write a minimal JSON cod3s envelope with 2 trivial sequences."""
    payload = {
        "schema_version": "1.0.0",
        "target_group_id": None,
        "sequences": [
            {
                "probability": 0.5,
                "weight": 1,
                "end_time": None,
                "target_name": "top",
                "events": [
                    {"obj": "a", "attr": "occ", "time": 1.0, "type": None},
                    {"obj": "top", "attr": "occ", "time": 2.0, "type": None},
                ],
            },
            {
                "probability": 0.5,
                "weight": 1,
                "end_time": None,
                "target_name": "top",
                "events": [
                    {"obj": "b", "attr": "occ", "time": 5.0, "type": None},
                    {"obj": "top", "attr": "occ", "time": 6.0, "type": None},
                ],
            },
        ],
        "meta": None,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_main_loads_json_cod3s_without_running_tui(
    tmp_path: Path, monkeypatch
) -> None:
    """End-to-end smoke: argparse → loader → state build → (no TUI).

    The Textual mainloop is stubbed via monkey-patch so the test exits
    immediately after the state is built.
    """
    seq_path = tmp_path / "seq.json"
    _write_synthetic_json_cod3s(seq_path)

    captured = {}

    def fake_run(state):
        captured["state"] = state

    monkeypatch.setattr("cod3s.pycatshoo.seq_tui.app.run_seq_tui", fake_run)

    rc = main([str(seq_path)])
    assert rc == 0
    assert "state" in captured
    assert len(captured["state"].analyser.sequences) == 2


def test_main_applies_startup_pipeline(tmp_path: Path, monkeypatch) -> None:
    """``--pipeline`` re-applies the YAML before handing off to the TUI."""
    seq_path = tmp_path / "seq.json"
    _write_synthetic_json_cod3s(seq_path)

    # Write a pipeline that groups the 2 sequences (no collapse — they
    # have different signatures — but the pipeline length should grow
    # to 1).
    pipe_path = tmp_path / "pipe.yaml"
    pipe_path.write_text(
        "version: '1.0.0'\nsteps:\n  - op: group_sequences\n",
        encoding="utf-8",
    )

    captured = {}

    def fake_run(state):
        captured["state"] = state

    monkeypatch.setattr("cod3s.pycatshoo.seq_tui.app.run_seq_tui", fake_run)

    rc = main([str(seq_path), "--pipeline", str(pipe_path)])
    assert rc == 0
    state = captured["state"]
    assert len(state.pipeline.steps) == 1
    # No collapse because the two sequences have different signatures.
    assert len(state.analyser.sequences) == 2


def test_parser_accepts_factory(tmp_path: Path) -> None:
    parser = _build_parser()
    ns = parser.parse_args(["x.xml", "--factory", "mod.path:fn"])
    assert ns.factory == "mod.path:fn"


def test_main_factory_invalid_module_errors_cleanly(
    tmp_path: Path, monkeypatch
) -> None:
    """An unknown factory module must surface a clean parser.error
    rather than crashing somewhere deep in the loader."""
    seq_path = tmp_path / "seq.json"
    _write_synthetic_json_cod3s(seq_path)

    # Stub the TUI so we never get there
    monkeypatch.setattr(
        "cod3s.pycatshoo.seq_tui.app.run_seq_tui", lambda state: None
    )

    with pytest.raises(SystemExit):
        main(
            [
                str(seq_path),
                "--factory",
                "nonexistent_module_xyzzy:build_system",
            ]
        )


def test_main_factory_resolves_and_attaches_system(
    tmp_path: Path, monkeypatch
) -> None:
    """A valid factory builds a PycSystem-like object that gets attached.

    We monkey-patch ``resolve_factory`` to return a stub system so this
    test stays free of the PyCATSHOO singleton — the contract under test
    is *the wiring between CLI and state*, not the PyCATSHOO API.
    """
    seq_path = tmp_path / "seq.json"
    _write_synthetic_json_cod3s(seq_path)

    class _FakeSystem:
        def name(self) -> str:
            return "fake-system"

        comp: dict = {}

        # Make discover_objfms a no-op by giving an empty comp dict —
        # the real cod3s ObjFM check loops over comp.values().

    fake_system = _FakeSystem()

    def fake_resolve(spec, **kwargs):
        return lambda: fake_system

    monkeypatch.setattr(
        "cod3s.scripts._common.resolve_factory", fake_resolve
    )

    captured = {}

    def fake_run(state):
        captured["state"] = state

    monkeypatch.setattr("cod3s.pycatshoo.seq_tui.app.run_seq_tui", fake_run)

    rc = main([str(seq_path), "--factory", "fake:build"])
    assert rc == 0
    state = captured["state"]
    # System attached to the analyser.
    assert state.analyser._system is fake_system
    # No ObjFM discovered (the fake has no .comp entries).
    assert state.available_objfms_internal == ()


def test_main_max_sequences_caps_load(tmp_path: Path, monkeypatch) -> None:
    seq_path = tmp_path / "seq.json"
    _write_synthetic_json_cod3s(seq_path)

    captured = {}

    def fake_run(state):
        captured["state"] = state

    monkeypatch.setattr("cod3s.pycatshoo.seq_tui.app.run_seq_tui", fake_run)

    rc = main([str(seq_path), "--max-sequences", "1"])
    assert rc == 0
    assert len(captured["state"].analyser.sequences) == 1
