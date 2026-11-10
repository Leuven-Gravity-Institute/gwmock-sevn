"""SEVN binary population synthesis as an installable Python package.

The wheel carries SEVN's binary-evolution program built from a pinned SEVN commit; the
stellar-track tables are fetched by digest on first use. See :func:`evolve_binaries`.
"""

from __future__ import annotations

# PEP 810: defer importlib.metadata (loaded by version.py) on 3.15+.
# Ignored on 3.13/3.14 where the lazy import machinery does not exist.
__lazy_modules__ = ["gwmock_sevn.version"]

from gwmock_sevn.evolve import INPUT_COLUMNS, EvolutionResult, evolve_binaries, executable
from gwmock_sevn.tables import SEVN_COMMIT, fetch, table_sets
from gwmock_sevn.version import __version__

__all__ = [
    "INPUT_COLUMNS",
    "SEVN_COMMIT",
    "EvolutionResult",
    "__version__",
    "evolve_binaries",
    "executable",
    "fetch",
    "table_sets",
]
