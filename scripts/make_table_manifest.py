"""Write the digest manifest of SEVN's stellar-track tables at one SEVN commit.

The tables are not shipped in the wheel: they are fetched file by file from the SEVN
repository at a pinned commit and checked against the SHA-256 recorded here
(see ``gwmock_sevn.tables``). Usage::

    python scripts/make_table_manifest.py /path/to/sevn/checkout

The checkout must be at the commit to pin; the manifest is written to
``src/gwmock_sevn/data/tables/<commit>.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PACKAGE_DATA = Path(__file__).resolve().parents[1] / "src" / "gwmock_sevn" / "data" / "tables"


def manifest(checkout: Path) -> tuple[str, dict]:
    """Describe every table file in *checkout* by path, size and SHA-256.

    Args:
        checkout: A SEVN git checkout.

    Returns:
        The checkout's commit, and the manifest keyed by table-set name.
    """
    commit = subprocess.run(  # noqa: S603 - fixed git command
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    root = checkout / "tables"
    sets: dict[str, dict[str, dict[str, object]]] = {}
    for table_set in sorted(path for path in root.iterdir() if path.is_dir()):
        files = {}
        for path in sorted(p for p in table_set.rglob("*") if p.is_file()):
            files[path.relative_to(table_set).as_posix()] = {
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        sets[table_set.name] = files
    return commit, {"repository": "https://gitlab.com/sevncodes/sevn", "commit": commit, "sets": sets}


def main() -> None:
    """Write the manifest for the checkout given on the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("checkout", type=Path)
    commit, content = manifest(parser.parse_args().checkout)
    PACKAGE_DATA.mkdir(parents=True, exist_ok=True)
    target = PACKAGE_DATA / f"{commit}.json"
    target.write_text(json.dumps(content, indent=1, sort_keys=True) + "\n")
    print(target)


if __name__ == "__main__":
    main()
