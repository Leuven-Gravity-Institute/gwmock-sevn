"""Copy the parts of SEVN that gwmock-sevn builds from into ``extern/sevn``.

SEVN is vendored rather than added as a submodule so that a source distribution builds
offline. Only what the build reads is copied: the CMake files, the C++ sources and headers,
the executables' sources and the auxiliary data the executable reads at run time. The
stellar-track tables (about 360 MB) are not copied; they are fetched by digest at run time
(see ``gwmock_sevn.tables``).

Usage::

    python scripts/vendor_sevn.py v2.17.5

The tag is resolved to its commit, and both are written to ``extern/sevn/VENDORED`` so the
build and its provenance name the exact SEVN source. Every patch in ``patches/`` is then applied
in name order and listed there too, so the vendored source is SEVN's own plus named changes.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = "https://gitlab.com/sevncodes/sevn.git"
#: What the build reads, relative to the SEVN repository root.
COPIED = ("CMakeLists.txt", "cmake", "src", "include", "main", "auxiliary_data", "LICENSE", "changelog.txt")
ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "extern" / "sevn"
PATCHES = ROOT / "patches"


def vendor(tag: str) -> str:
    """Replace ``extern/sevn`` with the SEVN source at *tag* and return its commit.

    Args:
        tag: The SEVN tag to vendor, e.g. ``"v2.17.5"``.

    Returns:
        The full commit hash the tag points at.
    """
    with tempfile.TemporaryDirectory() as scratch:
        checkout = Path(scratch) / "sevn"
        subprocess.run(  # noqa: S603 - fixed git command
            ["git", "clone", "--quiet", "--depth", "1", "--branch", tag, REPOSITORY, str(checkout)],  # noqa: S607
            check=True,
        )
        commit = subprocess.run(  # noqa: S603 - fixed git command
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],  # noqa: S607
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if DESTINATION.exists():
            shutil.rmtree(DESTINATION)
        DESTINATION.mkdir(parents=True)
        for name in COPIED:
            source = checkout / name
            if source.is_dir():
                shutil.copytree(source, DESTINATION / name)
            else:
                shutil.copy2(source, DESTINATION / name)
        # Generated at configure time by SEVN's own CMake; a stale copy would misreport the version.
        (DESTINATION / "include" / "sevn_version.h").unlink(missing_ok=True)
    patches = sorted(PATCHES.glob("*.patch"))
    for patch in patches:
        subprocess.run(  # noqa: S603 - fixed git command
            ["git", "apply", f"--directory={DESTINATION.relative_to(ROOT)}", str(patch)],  # noqa: S607
            check=True,
            cwd=ROOT,
        )
    applied = "".join(f"patch = {patch.name}\n" for patch in patches)
    (DESTINATION / "VENDORED").write_text(f"repository = {REPOSITORY}\ntag = {tag}\ncommit = {commit}\n{applied}")
    return commit


def main() -> None:
    """Vendor the tag given on the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="SEVN tag, e.g. v2.17.5")
    print(vendor(parser.parse_args().tag))


if __name__ == "__main__":
    main()
