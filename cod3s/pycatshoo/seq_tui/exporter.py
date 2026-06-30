"""Sequence-analyser exporters for ``cod3s-seq``.

Three output formats:

* **JSON cod3s** — the canonical envelope produced by
  :func:`cod3s.pycatshoo.sequence.persist_sequence_analysis_artifacts`.
  Identical to what ``run-cod3s-study`` writes; can be re-loaded with
  :func:`cod3s.pycatshoo.seq_tui.loader.load_sequences_from_json_cod3s`.

* **CSV** — one row per event (long format) via the existing
  ``SequenceAnalyser.to_df_long`` method. Suitable for spreadsheet
  analysis.

* **Markdown** — a top-level summary table followed by per-sequence
  detail sections. Suitable for inclusion in a written report.

All three are pure functions taking ``(analyser, path)``. Filesystem
errors propagate as the standard :class:`OSError`.
"""

from __future__ import annotations

from pathlib import Path

from cod3s.pycatshoo.sequence import persist_sequence_analysis_artifacts


# ---------------------------------------------------------------------------
# JSON cod3s
# ---------------------------------------------------------------------------


def export_json_cod3s(analyser, path) -> None:
    """Write the analyser to a JSON cod3s envelope file.

    Wraps :func:`persist_sequence_analysis_artifacts` — the format is
    bit-identical to what ``run-cod3s-study`` produces, ensuring the
    exported file can flow back into any cod3s-platform / analyst
    workflow without conversion.
    """
    persist_sequence_analysis_artifacts(analyser, Path(path))


# ---------------------------------------------------------------------------
# CSV (one row per event, long format)
# ---------------------------------------------------------------------------


def export_csv(analyser, path) -> None:
    """Write the analyser to a CSV file in long format (one row per event).

    Delegates to :meth:`SequenceAnalyser.to_df_long` for the dataframe
    shape, then writes UTF-8 CSV (no index, header included).
    """
    df = analyser.to_df_long()
    df.to_csv(str(path), index=False, encoding="utf-8")


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def export_markdown(analyser, path) -> None:
    """Write a Markdown report for the analyser.

    Structure::

        # Sequence analysis

        | # | weight | probability | target | events |
        |---|--------|-------------|--------|--------|
        | 1 |   3344 |    66.88 %  | top    | cc_12 → top.occ |
        | ...

        ## Sequence #1

        - weight: 3344
        - probability: 66.88 %
        - target_name: system_down_target
        - end_time: —

        | t       | obj    | attr      | type |
        |---------|--------|-----------|------|
        | 100.000 | fm     | occ__cc_1_2 | —   |
        | ...

    The top table is sorted by descending weight; each detail section
    follows the same order.
    """
    sequences = sorted(
        analyser.sequences, key=lambda s: s.weight, reverse=True
    )
    total = sum(s.weight for s in sequences)
    lines: list[str] = ["# Sequence analysis", ""]
    lines.append(f"_Total weight: {total} — {len(sequences)} distinct signatures_")
    lines.append("")

    # Top table
    lines.append("| # | weight | probability | target | events |")
    lines.append("|---|--------|-------------|--------|--------|")
    for i, s in enumerate(sequences, start=1):
        proba = (
            s.probability
            if s.probability is not None
            else (s.weight / total if total else 0.0)
        )
        signature = " → ".join(f"{e.obj}.{e.attr}" for e in s.events) or "_(empty)_"
        target = s.target_name or "—"
        lines.append(
            f"| {i} | {s.weight} | {proba:.4f} | {target} | {signature} |"
        )

    # Per-sequence detail sections
    for i, s in enumerate(sequences, start=1):
        lines.extend(["", f"## Sequence #{i}", ""])
        proba = (
            s.probability
            if s.probability is not None
            else (s.weight / total if total else 0.0)
        )
        lines.append(f"- weight: {s.weight}")
        lines.append(f"- probability: {proba:.4f}")
        lines.append(f"- target_name: {s.target_name or '—'}")
        end_time_str = "—" if s.end_time is None else f"{s.end_time:.3f}"
        lines.append(f"- end_time: {end_time_str}")
        if not s.events:
            lines.append("")
            lines.append("_(empty sequence — top event not reached)_")
            continue
        lines.append("")
        lines.append("| t | obj | attr | type |")
        lines.append("|---|-----|------|------|")
        for e in s.events:
            t_str = "—" if e.time is None else f"{e.time:.3f}"
            type_str = e.type or "—"
            lines.append(f"| {t_str} | {e.obj} | {e.attr} | {type_str} |")

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
