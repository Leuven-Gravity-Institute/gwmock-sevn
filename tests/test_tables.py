"""The table manifest and the digest-checked fetch, without the network."""

from __future__ import annotations

import hashlib
import io
import tarfile
import urllib.error
from email.message import Message

import pytest

from gwmock_sevn import tables

pytestmark = pytest.mark.unit


def _archive(files: dict[str, bytes], table_set: str) -> bytes:
    """A GitLab-style archive: everything under ``<prefix>/tables/<set>/``."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for path, content in files.items():
            info = tarfile.TarInfo(f"sevn-abc-abc-tables-{table_set}/tables/{table_set}/{path}")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


@pytest.fixture
def fake_manifest(monkeypatch, tmp_path):
    """A one-set manifest with two files, and a cache in tmp_path."""
    files = {"0001/mass.dat": b"1 2 3\n", "0001/time.dat": b"4 5 6\n"}
    recorded = {
        path: {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()} for path, content in files.items()
    }
    manifest = {"repository": "x", "commit": "abc", "sets": {"tracks": recorded}}
    monkeypatch.setattr(tables, "manifest", lambda commit=tables.SEVN_COMMIT: manifest)
    monkeypatch.setenv("GWMOCK_SEVN_CACHE", str(tmp_path / "cache"))
    return files


def _serve(monkeypatch, payloads: list[bytes | urllib.error.HTTPError]) -> list[str]:
    """Answer successive downloads with *payloads*; return the URLs requested."""
    requested: list[str] = []

    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _urlopen(url, timeout):
        requested.append(url)
        payload = payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return _Response(payload)

    monkeypatch.setattr(tables.urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(tables.time, "sleep", lambda seconds: None)
    return requested


def test_the_bundled_manifest_names_the_vendored_commit():
    """The executable's SEVN commit has a manifest, and it lists the default track sets."""
    sets = tables.table_sets()
    assert "SEVNtracks_parsec_ov05_AGB" in sets
    assert "SEVNtracks_parsec_pureHe36" in sets
    recorded = tables.manifest()["sets"]["SEVNtracks_parsec_ov05_AGB"]
    assert all(len(entry["sha256"]) == 64 and entry["size"] > 0 for entry in recorded.values())


def test_the_installed_sevn_and_the_manifest_name_the_same_commit():
    """The tables default to the commit the installed executable was built from."""
    from importlib.resources import files

    vendored = (files("gwmock_sevn") / "data" / "VENDORED").read_text()
    assert f"commit = {tables.SEVN_COMMIT}" in vendored
    assert tables.manifest()["commit"] == tables.SEVN_COMMIT


def test_an_unknown_set_is_refused(fake_manifest):
    """An unknown set is refused."""
    with pytest.raises(ValueError, match="No table set 'other'"):
        tables.fetch("other")


def test_an_unknown_commit_is_refused():
    """An unknown commit is refused."""
    with pytest.raises(ValueError, match="No table manifest for SEVN commit"):
        tables.manifest("0" * 40)


def test_a_set_is_downloaded_once_and_verified(monkeypatch, fake_manifest):
    """A set is downloaded once and verified."""
    requested = _serve(monkeypatch, [_archive(fake_manifest, "tracks")])

    directory = tables.fetch("tracks")
    again = tables.fetch("tracks")

    assert directory == again
    assert len(requested) == 1
    assert f"sha={tables.SEVN_COMMIT}" in requested[0]
    assert requested[0].endswith("path=tables/tracks")
    assert (directory / "0001" / "mass.dat").read_bytes() == b"1 2 3\n"


def test_a_file_that_does_not_match_its_digest_is_refused(monkeypatch, fake_manifest, tmp_path):
    """A file that does not match its digest is refused."""
    tampered = dict(fake_manifest, **{"0001/mass.dat": b"9 9 9\n"})
    _serve(monkeypatch, [_archive(tampered, "tracks")])

    with pytest.raises(OSError, match="differ from their recorded SHA-256"):
        tables.fetch("tracks")
    # Nothing is left where a later run would take it for the verified set.
    assert not list((tmp_path / "cache").rglob("mass.dat"))


def test_a_missing_file_is_refused(monkeypatch, fake_manifest):
    """A missing file is refused."""
    _serve(monkeypatch, [_archive({"0001/mass.dat": fake_manifest["0001/mass.dat"]}, "tracks")])

    with pytest.raises(OSError, match="missing or differ"):
        tables.fetch("tracks")


def test_a_rate_limited_request_is_retried(monkeypatch, fake_manifest):
    """A rate limited request is retried."""
    limited = urllib.error.HTTPError("u", 429, "Too Many Requests", Message(), None)
    requested = _serve(monkeypatch, [limited, _archive(fake_manifest, "tracks")])

    tables.fetch("tracks")

    assert len(requested) == 2


def test_an_archive_entry_cannot_escape_the_cache(monkeypatch, fake_manifest, tmp_path):
    """Only manifest paths are extracted, so ``../`` entries are never written."""
    hostile = dict(fake_manifest, **{"../../escape.dat": b"x"})
    _serve(monkeypatch, [_archive(hostile, "tracks")])

    tables.fetch("tracks")

    assert not list(tmp_path.rglob("escape.dat"))
