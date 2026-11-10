"""Smoke tests before publishing to verify the wheel and source distribution."""

from __future__ import annotations

import subprocess
import sys

import gwmock_sevn


def test_basic_import() -> None:
    """Test basic import."""
    print(f"Python version: {sys.version}")
    print(f"Package version: {gwmock_sevn.__version__}")

    # Ensure it's not importing the local folder
    if "site-packages" not in gwmock_sevn.__file__ and "dist" not in gwmock_sevn.__file__:
        print(f"Warning: Package imported from unexpected location: {gwmock_sevn.__file__}")


def test_the_bundled_sevn_runs() -> None:
    """The wheel's SEVN program starts: without arguments it prints its parameters and exits 0."""
    result = subprocess.run([str(gwmock_sevn.executable())], capture_output=True, text=True, check=False)  # noqa: S603
    assert result.returncode == 0
    assert "SEVN" in result.stdout


if __name__ == "__main__":
    test_basic_import()
    print("Smoke test passed: Package is importable.")

    test_the_bundled_sevn_runs()
    print("Smoke test passed: The bundled SEVN program runs.")
