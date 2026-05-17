"""Sequence-dump loaders for ``cod3s-seq``.

Two input formats are supported:

* **XML** — raw ``sequences.xml`` produced by PyCATSHOO when
  ``setResultFileName`` is enabled before ``simulate``. Each ``<SEQ>``
  element holds an end-cause attribute and a list of ``<BR>``
  branches; each branch carries a time ``T`` and a list of ``<TR>``
  transitions identified by ``NAME="<obj>.<attr>"``.

* **JSON cod3s** — the canonical envelope written by
  :func:`cod3s.pycatshoo.sequence.persist_sequence_analysis_artifacts`
  (and by ``run-cod3s-study`` as ``sequences_all.json`` /
  ``sequences_minimal.json``). The envelope wraps a list of
  :class:`Sequence` dumps with a ``schema_version`` field.

Format detection is via the file extension; an explicit override is
available for callers that need to bypass it.
"""

from __future__ import annotations

import json
import typing
from pathlib import Path
from xml.etree import ElementTree as ET

from cod3s.pycatshoo.sequence import (
    SEQUENCE_ARTIFACT_SCHEMA_VERSION,
    SeqEvent,
    Sequence,
)


SourceFormat = typing.Literal["xml", "json-cod3s"]


class SequenceLoadError(ValueError):
    """Raised when a sequence dump cannot be loaded.

    Subclass of :class:`ValueError` so the TUI can catch it uniformly
    alongside Pydantic / XML errors.
    """


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


def detect_format(path) -> SourceFormat:
    """Detect the source format from the file extension and a small
    content sniff.

    Args:
        path: Filesystem path (``str`` or :class:`Path`).

    Returns:
        ``"xml"`` or ``"json-cod3s"``.

    Raises:
        SequenceLoadError: If the format cannot be determined or the
            file does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise SequenceLoadError(f"File not found: {p}")
    suffix = p.suffix.lower()
    if suffix == ".xml":
        return "xml"
    if suffix == ".json":
        # Quick content sniff to distinguish a cod3s envelope from any
        # other JSON the user might have on disk.
        with p.open("r", encoding="utf-8") as fp:
            head = fp.read(512)
        if '"schema_version"' in head and '"sequences"' in head:
            return "json-cod3s"
        raise SequenceLoadError(
            f"{p.name}: looks like JSON but is missing the cod3s envelope "
            f'fields ("schema_version", "sequences"). Use ``--format`` to '
            f"force a specific reader."
        )
    raise SequenceLoadError(
        f"{p.name}: cannot detect format from extension {suffix!r}. "
        f"Supported: .xml, .json. Use ``--format`` to force."
    )


# ---------------------------------------------------------------------------
# XML loader
# ---------------------------------------------------------------------------


def load_sequences_from_xml(
    path,
    *,
    max_sequences: int | None = None,
) -> list[Sequence]:
    """Parse a PyCATSHOO ``sequences.xml`` dump into cod3s
    :class:`Sequence` objects.

    Uses streaming ``ElementTree.iterparse`` so a 30 MB file stays in
    bounded memory. Each ``<SEQ>`` element is processed then cleared.

    Args:
        path: Filesystem path to the XML file.
        max_sequences: Optional cap on the number of sequences read
            (useful for fast smoke-tests on very large dumps).

    Returns:
        list[Sequence]: One ``Sequence`` per ``<SEQ>`` element, in
        source order. Each event time defaults to 0.0 when the
        ``<BR T=...>`` attribute is missing or unparseable. Each
        sequence has weight 1 (grouping happens later in the pipeline).

    Raises:
        SequenceLoadError: On malformed XML or missing file.
    """
    p = Path(path)
    if not p.exists():
        raise SequenceLoadError(f"File not found: {p}")

    sequences: list[Sequence] = []
    try:
        # iterparse with "end" events streams through ``<SEQ>`` elements
        # one at a time. We clear each element after processing so the
        # tree never grows beyond the current sequence.
        context = ET.iterparse(str(p), events=("end",))
        for _, elem in context:
            if elem.tag != "SEQ":
                continue
            events = []
            for br in elem.findall("BR"):
                try:
                    t = float(br.get("T") or 0.0)
                except (TypeError, ValueError):
                    t = 0.0
                for tr in br.findall("TR"):
                    name = tr.get("NAME", "")
                    obj, _, attr = name.partition(".")
                    events.append(
                        SeqEvent(
                            obj=obj or name,
                            attr=attr or name,
                            time=t,
                            type=None,
                        )
                    )
            sequences.append(
                Sequence(
                    probability=None,
                    weight=1,
                    end_time=None,
                    target_name=elem.get("C") or "Normal",
                    events=events,
                )
            )
            # Free the parsed subtree.
            elem.clear()
            if max_sequences is not None and len(sequences) >= max_sequences:
                break
    except ET.ParseError as exc:
        raise SequenceLoadError(f"{p.name}: malformed XML: {exc}") from exc
    return sequences


# ---------------------------------------------------------------------------
# JSON cod3s loader
# ---------------------------------------------------------------------------


def load_sequences_from_json_cod3s(
    path,
    *,
    strict_schema: bool = False,
) -> list[Sequence]:
    """Parse a cod3s JSON sequence envelope into cod3s
    :class:`Sequence` objects.

    The envelope shape is the one produced by
    :func:`cod3s.pycatshoo.sequence.persist_sequence_analysis_artifacts`::

        {
            "schema_version": "1.0.0",
            "target_group_id": ...,
            "sequences": [<Sequence.model_dump(mode="json")>...],
            "meta": {...}
        }

    Args:
        path: Filesystem path to the ``.json`` file.
        strict_schema: When ``True``, raise on any
            ``schema_version`` that does not match
            :data:`SEQUENCE_ARTIFACT_SCHEMA_VERSION`. When ``False``
            (default), a mismatch is silently accepted — the loader
            still attempts to read the ``sequences`` list and lets
            Pydantic raise if individual sequences are incompatible.

    Returns:
        list[Sequence]: Reconstructed sequences. Weights and
        probabilities are taken as-is from the dump (i.e. **not**
        reset to 1: the JSON envelope is expected to come from an
        already-grouped/minimised analyser).

    Raises:
        SequenceLoadError: On malformed JSON, missing required
            envelope keys, or schema mismatch in strict mode.
    """
    p = Path(path)
    if not p.exists():
        raise SequenceLoadError(f"File not found: {p}")

    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SequenceLoadError(f"{p.name}: malformed JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise SequenceLoadError(
            f"{p.name}: top-level JSON must be an object, got {type(payload).__name__}"
        )

    schema_version = payload.get("schema_version")
    if schema_version is None:
        raise SequenceLoadError(
            f'{p.name}: missing "schema_version" — not a cod3s sequence envelope'
        )
    if schema_version != SEQUENCE_ARTIFACT_SCHEMA_VERSION and strict_schema:
        raise SequenceLoadError(
            f"{p.name}: schema_version mismatch "
            f"(got {schema_version!r}, expected {SEQUENCE_ARTIFACT_SCHEMA_VERSION!r})"
        )

    seq_dicts = payload.get("sequences")
    if seq_dicts is None:
        raise SequenceLoadError(
            f'{p.name}: missing "sequences" array in envelope'
        )
    if not isinstance(seq_dicts, list):
        raise SequenceLoadError(
            f'{p.name}: "sequences" must be an array, got {type(seq_dicts).__name__}'
        )

    sequences: list[Sequence] = []
    for i, d in enumerate(seq_dicts):
        try:
            sequences.append(Sequence.model_validate(d))
        except Exception as exc:
            raise SequenceLoadError(
                f"{p.name}: sequences[{i}] failed validation: {exc}"
            ) from exc
    return sequences
