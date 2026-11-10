"""Evolve binaries with SEVN.

The wheel carries SEVN's own binary-evolution program (``sevnB``), built from the vendored source
(``data/VENDORED`` names the commit). :func:`evolve_binaries` writes the binaries to a SEVN input
list, runs that program, and reads its output back as columns -- the same program, options and
input a SEVN user would run by hand, so the result is SEVN's, not a re-implementation of it.

Every binary carries its own random seed: SEVN's kicks and other stochastic choices are drawn
from it, so a run is reproducible binary by binary, however the batch is split across processes.
"""

from __future__ import annotations

import csv
import itertools
import os
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

import numpy as np

from gwmock_sevn.tables import SEVN_COMMIT, fetch

#: The columns of SEVN's binary input list, in order (SEVN's "new" list format with a seed).
INPUT_COLUMNS = (
    "mass_0",
    "metallicity_0",
    "spin_0",
    "supernova_0",
    "start_0",
    "mass_1",
    "metallicity_1",
    "spin_1",
    "supernova_1",
    "start_1",
    "semimajor",
    "eccentricity",
    "end",
    "output_times",
    "seed",
)

#: Options gwmock-sevn sets itself; passing them in ``options`` is refused.
_RESERVED = frozenset({"list", "tables", "tables_HE", "o", "omode", "rseed", "nthreads", "ibmode"})


@dataclass(frozen=True)
class EvolutionResult:
    """What SEVN wrote for a batch of binaries.

    Attributes:
        output: SEVN's output table, one row per binary per output time, as columns keyed by
            SEVN's column names (``ID`` is the binary's position in the input batch).
        events: SEVN's logfile, one entry per logged event: ``ID`` (the binary's position in the
            input), ``kind`` (``"B"`` binary or ``"S"`` star), ``star`` (``0`` or ``1`` for a star
            event, ``None`` for a binary one), ``event`` (e.g. ``"BSN"``, ``"CE"``, ``"MERGER"``),
            ``time`` in Myr and ``details``, the event's own colon-separated fields.
        failed: Positions of the binaries SEVN could not initialise.
        options: The full SEVN command line used, without the paths.
    """

    output: dict[str, np.ndarray]
    events: list[dict[str, Any]]
    failed: list[int]
    options: list[str]


def executable() -> Path:
    """The bundled ``sevnB`` program.

    Returns:
        Its path.

    Raises:
        FileNotFoundError: If the package was installed without it.
    """
    path = Path(str(files("gwmock_sevn") / "bin" / "sevnB.x"))
    if not path.is_file():
        raise FileNotFoundError(f"The SEVN executable is missing from the installation ({path}).")
    return path


def _format(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (float, np.floating)):
        return repr(float(value))
    return str(value)


def _write_list(path: Path, binaries: Mapping[str, Sequence[Any]], rows: range) -> None:
    with path.open("w") as handle:
        for index in rows:
            handle.write(" ".join(_format(binaries[column][index]) for column in INPUT_COLUMNS) + "\n")


def _read_output(directory: Path) -> dict[str, list[str]]:
    columns: dict[str, list[str]] = {}
    for path in sorted(directory.glob("output_*.csv")):
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                for key, value in row.items():
                    columns.setdefault(key, []).append(value)
    return columns


def _read_events(directory: Path, positions: Mapping[str, int]) -> list[dict[str, Any]]:
    """Read SEVN's logfile, identifying each event's binary by its ``name``.

    A logfile line is ``kind;name;ID;event;time;details``. ``ID`` is the binary's index in its own
    run for a binary event but the star's index (0 or 1) for a star event, so the binary is
    identified through ``name``, which SEVN writes in the output table as well.
    """
    events = []
    for path in sorted(directory.glob("logfile_*.dat")):
        for line in path.read_text().splitlines():
            fields = line.split(";")
            if len(fields) < 5:  # noqa: PLR2004 - kind;name;ID;event;time;details
                continue
            kind = fields[0]
            events.append(
                {
                    "ID": positions[fields[1]],
                    "kind": kind,
                    "star": int(fields[2]) if kind == "S" else None,
                    "event": fields[3],
                    "time": float(fields[4]),
                    "details": fields[5] if len(fields) > 5 else "",  # noqa: PLR2004
                }
            )
    return events


def _read_failed(directory: Path) -> list[int]:
    failed = []
    for path in sorted(directory.glob("failed_initialisation_*.dat")):
        for line in path.read_text().splitlines()[1:]:
            fields = line.split()
            if fields and fields[0].lstrip("-").isdigit():
                failed.append(int(fields[0]))
    return failed


def _positions_by_name(columns: Mapping[str, Sequence[str]]) -> dict[str, int]:
    """Map each binary's SEVN ``name`` to its position in the batch.

    Raises:
        RuntimeError: If two binaries share a name. SEVN names a binary from its seed, and the logfile
            identifies a star's events only by that name, so their events could not be told apart.
    """
    positions: dict[str, int] = {}
    for name, identifier in zip(columns.get("name", []), columns.get("ID", []), strict=True):
        if positions.setdefault(name, int(identifier)) != int(identifier):
            raise RuntimeError(
                f"SEVN gave binaries {positions[name]} and {identifier} the same name {name}; their logfile "
                "events cannot be told apart. Give them different seeds."
            )
    return positions


def _run_chunk(
    command: list[str], environment: dict[str, str], binaries: Mapping[str, Sequence[Any]], rows: range, scratch: Path
) -> tuple[dict[str, list[str]], list[dict[str, Any]], list[int]]:
    """Run SEVN on *rows* of the batch in *scratch* and return its parsed output, IDs shifted to the batch."""
    listing = scratch / "binaries.dat"
    output = scratch / "output"
    _write_list(listing, binaries, rows)
    completed = subprocess.run(  # noqa: S603 - our own executable and arguments
        [*command, "-list", str(listing), "-o", str(output)],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"SEVN exited with status {completed.returncode}:\n{completed.stderr[-4000:]}")
    columns = _read_output(output)
    if "ID" in columns:
        columns["ID"] = [str(int(value) + rows.start) for value in columns["ID"]]
    positions = _positions_by_name(columns)
    events = _read_events(output, positions)
    return columns, events, [index + rows.start for index in _read_failed(output)]


def _as_array(values: list[str]) -> np.ndarray:
    try:
        return np.asarray(values, dtype=np.int64)
    except (ValueError, OverflowError):
        pass
    try:
        return np.asarray(values, dtype=np.float64)
    except ValueError:
        return np.asarray(values, dtype=str)


def evolve_binaries(
    binaries: Mapping[str, Sequence[Any]],
    *,
    tables: str = "SEVNtracks_parsec_ov05_AGB",
    tables_he: str = "SEVNtracks_parsec_pureHe36",
    options: Mapping[str, Any] | None = None,
    processes: int = 1,
) -> EvolutionResult:
    """Evolve a batch of binaries with SEVN.

    Args:
        binaries: One sequence per column of :data:`INPUT_COLUMNS`, all the same length, in
            SEVN's units and conventions (Msun, Rsun, Myr; ``supernova_*`` a SEVN supernova model
            such as ``"rapid"``; ``start_*`` e.g. ``"zams"``; ``end`` and ``output_times`` as in a
            SEVN list, e.g. ``"end"`` and ``"all"``; ``seed`` a positive integer, different
            for every binary).
        tables: The H-rich track set, fetched by :func:`gwmock_sevn.tables.fetch` at the commit the
            bundled program is built from, so program and tables always match.
        tables_he: The pure-He track set.
        options: Further SEVN parameters, by SEVN's name without the leading dash, e.g.
            ``{"star_lambda": -1, "ce_alpha": 1.0}``.
        processes: Number of SEVN processes to split the batch across. The output does not
            depend on it: each binary has its own seed.

    Returns:
        SEVN's output, logfile events and failed initialisations for the batch.

    Raises:
        ValueError: If a column is missing, the columns differ in length, two binaries share a seed,
            or ``options`` names a parameter gwmock-sevn sets itself.
        RuntimeError: If SEVN fails, or gives two binaries the same name.
    """
    missing = [column for column in INPUT_COLUMNS if column not in binaries]
    if not missing:
        seeds = [int(seed) for seed in binaries["seed"]]
        if len(set(seeds)) != len(seeds):
            # SEVN names each binary from its seed, and that name is what ties a star's logfile events to
            # its binary; two equal seeds would also give two identical random streams.
            raise ValueError("Every binary needs its own seed; the batch repeats one.")
    if missing:
        raise ValueError(f"Missing input columns: {', '.join(missing)}.")
    lengths = {len(binaries[column]) for column in INPUT_COLUMNS}
    if len(lengths) != 1:
        raise ValueError("Every input column must have the same length.")
    count = lengths.pop()
    if count == 0:
        raise ValueError("No binaries to evolve.")
    reserved = sorted(_RESERVED & set(options or {}))
    if reserved:
        raise ValueError(f"These SEVN parameters are set by gwmock-sevn: {', '.join(reserved)}.")
    processes = max(1, min(processes, count))

    settings = ["-omode", "csv", "-rseed", "true", "-nthreads", "1", "-ibmode", "new"]
    for key, value in (options or {}).items():
        settings += [f"-{key}", _format(value)]

    with as_file(files("gwmock_sevn") / "data") as data, tempfile.TemporaryDirectory() as scratch:
        # SEVN reads auxiliary_data/ from the folder SEVN_PATH names (patches/0001); without it, it
        # would look in the build tree the executable was compiled in.
        environment = {**os.environ, "SEVN_PATH": str(data)}
        command = [
            str(executable()),
            "-tables",
            str(fetch(tables, SEVN_COMMIT)),
            "-tables_HE",
            str(fetch(tables_he, SEVN_COMMIT)),
            *settings,
        ]
        bounds = np.linspace(0, count, processes + 1).astype(int)
        chunks = [range(int(start), int(stop)) for start, stop in itertools.pairwise(bounds)]
        directories = []
        for index in range(len(chunks)):
            directory = Path(scratch) / f"chunk-{index}"
            directory.mkdir()
            directories.append(directory)
        with ThreadPoolExecutor(max_workers=processes) as pool:
            results = list(
                pool.map(
                    lambda job: _run_chunk(command, environment, binaries, *job), zip(chunks, directories, strict=True)
                )
            )

    columns: dict[str, list[str]] = {}
    events: list[dict[str, Any]] = []
    failed: list[int] = []
    for chunk_columns, chunk_events, chunk_failed in results:
        for key, values in chunk_columns.items():
            columns.setdefault(key, []).extend(values)
        events.extend(chunk_events)
        failed.extend(chunk_failed)
    return EvolutionResult(
        output={key: _as_array(values) for key, values in columns.items()},
        events=events,
        failed=failed,
        options=settings,
    )
