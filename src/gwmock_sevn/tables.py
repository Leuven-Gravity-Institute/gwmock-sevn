"""SEVN's stellar-track tables, fetched by digest rather than shipped in the wheel.

SEVN interpolates stellar evolution from look-up tables -- about 360 MB in all, in eight sets
(PARSEC and MIST H-rich tracks, pure-He tracks, Pop III tracks). They live in the SEVN
repository; gwmock-sevn records each file's SHA-256 at a pinned SEVN commit
(``data/tables/<commit>.json``) and downloads a set on first use, refusing any byte that does
not match. A run therefore names its tables by commit and set, and gets the same bytes every
time.

The tables are fetched from SEVN's own repository at that commit, not redistributed here.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

#: The SEVN commit the bundled executable is built from, and the default commit for tables.
SEVN_COMMIT = "bfd71ed7c7437e0d66d4af98f7b7f1998de4216e"

#: One archive per table set, filtered to that set's directory. GitLab generates the archive, so its
#: own bytes are not guaranteed stable; every file extracted from it is checked against the manifest.
_ARCHIVE_URL = (
    "https://gitlab.com/api/v4/projects/sevncodes%2Fsevn/repository/archive.tar.gz?sha={commit}&path=tables/{table_set}"
)
#: GitLab rate-limits archive requests (HTTP 429); a refused request is retried this many times.
_ATTEMPTS = 6
_TOO_MANY_REQUESTS = 429


def cache_root() -> Path:
    """Where fetched tables are kept: ``$GWMOCK_SEVN_CACHE``, else the user cache directory.

    Returns:
        The cache directory (not created here).
    """
    explicit = os.environ.get("GWMOCK_SEVN_CACHE")
    if explicit:
        return Path(explicit)
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "gwmock-sevn"


@cache
def manifest(commit: str = SEVN_COMMIT) -> dict[str, Any]:
    """The recorded size and SHA-256 of every table file at *commit*.

    Args:
        commit: A SEVN commit gwmock-sevn has a manifest for.

    Returns:
        The manifest: ``{"repository", "commit", "sets": {set: {path: {"size", "sha256"}}}}``.

    Raises:
        ValueError: If there is no manifest for *commit*.
    """
    resource = files("gwmock_sevn") / "data" / "tables" / f"{commit}.json"
    if not resource.is_file():
        known = sorted(item.name.removesuffix(".json") for item in (files("gwmock_sevn") / "data" / "tables").iterdir())
        raise ValueError(f"No table manifest for SEVN commit {commit!r}; known commits: {', '.join(known)}.")
    return json.loads(resource.read_text())


def table_sets(commit: str = SEVN_COMMIT) -> list[str]:
    """The names of the table sets recorded at *commit*.

    Args:
        commit: A SEVN commit gwmock-sevn has a manifest for.

    Returns:
        The set names, sorted.
    """
    return sorted(manifest(commit)["sets"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url: str, target: Path) -> None:
    """Download *url* to *target*, waiting and retrying while the server answers 429."""
    for attempt in range(_ATTEMPTS):
        try:
            with urllib.request.urlopen(url, timeout=300) as response, target.open("wb") as handle:  # noqa: S310 - fixed https URL
                shutil.copyfileobj(response, handle, 1 << 20)
            return
        except urllib.error.HTTPError as error:
            if error.code != _TOO_MANY_REQUESTS or attempt == _ATTEMPTS - 1:
                raise
            time.sleep(float(error.headers.get("Retry-After") or 15 * 2**attempt))


def _verified(directory: Path, recorded: dict[str, dict[str, Any]]) -> list[str]:
    """The recorded files missing from *directory* or differing from their recorded digest."""
    bad = []
    for path, expected in recorded.items():
        local = directory / path
        if not local.is_file() or local.stat().st_size != expected["size"] or _sha256(local) != expected["sha256"]:
            bad.append(path)
    return bad


def fetch(table_set: str, commit: str = SEVN_COMMIT) -> Path:
    """Make *table_set* at *commit* available locally and return its directory.

    A set already cached with every recorded digest is not downloaded again.

    Args:
        table_set: A set name from :func:`table_sets`, e.g. ``"SEVNtracks_parsec_ov05_AGB"``.
        commit: The SEVN commit whose tables to fetch.

    Returns:
        The directory holding the set's files, to pass to SEVN as ``tables`` or ``tables_HE``.

    Raises:
        ValueError: If *table_set* is not recorded at *commit*.
        OSError: If the downloaded files do not match the recorded digests.
    """
    recorded = manifest(commit)["sets"]
    if table_set not in recorded:
        raise ValueError(f"No table set {table_set!r} at SEVN commit {commit}; known: {', '.join(sorted(recorded))}.")
    files_of_set = recorded[table_set]
    directory = cache_root() / "tables" / commit / table_set
    directory.parent.mkdir(parents=True, exist_ok=True)
    # One fetcher per set at a time: a second process waits, then finds the set verified and leaves
    # it alone, so a set another run is reading is never replaced under it.
    with _locked(directory.with_suffix(".lock")):
        if directory.is_dir() and not _verified(directory, files_of_set):
            return directory
        _download_set(table_set, commit, files_of_set, directory)
    return directory


@contextlib.contextmanager
def _locked(path: Path):
    """Hold an exclusive advisory lock on *path* for the duration of the block."""
    with path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _download_set(table_set: str, commit: str, files_of_set: dict[str, dict[str, Any]], directory: Path) -> None:
    """Download, verify and publish *table_set* at *directory*; the caller holds the set's lock."""
    with tempfile.TemporaryDirectory(dir=directory.parent) as scratch:
        archive = Path(scratch) / "tables.tar.gz"
        _download(_ARCHIVE_URL.format(commit=commit, table_set=table_set), archive)
        staged = Path(scratch) / table_set
        marker = f"/tables/{table_set}/"
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                if not member.isfile() or marker not in member.name:
                    continue
                relative = member.name.split(marker, 1)[1]
                if relative not in files_of_set:
                    continue
                member.name = relative
                tar.extract(member, staged, filter="data")
        bad = _verified(staged, files_of_set)
        if bad:
            raise OSError(
                f"{len(bad)} file(s) of {table_set} at SEVN commit {commit} are missing or differ from their "
                f"recorded SHA-256, e.g. {bad[0]}; refusing the download."
            )
        if directory.exists():
            # Present but not verified (incomplete or altered); nobody else is fetching it.
            shutil.rmtree(directory)
        staged.replace(directory)
