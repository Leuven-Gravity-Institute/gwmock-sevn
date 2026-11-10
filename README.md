# gwmock-sevn

[![Python CI](https://github.com/Leuven-Gravity-Institute/gwmock-sevn/actions/workflows/ci.yml/badge.svg)](https://github.com/Leuven-Gravity-Institute/gwmock-sevn/actions/workflows/ci.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Leuven-Gravity-Institute/gwmock-sevn/main.svg)](https://results.pre-commit.ci/latest/github/Leuven-Gravity-Institute/gwmock-sevn/main)
[![Documentation Status](https://github.com/Leuven-Gravity-Institute/gwmock-sevn/actions/workflows/documentation.yml/badge.svg)](https://leuven-gravity-institute.github.io/gwmock-sevn/)
[![codecov](https://codecov.io/gh/leuven-gravity-institute/gwmock-sevn/graph/badge.svg)](https://codecov.io/gh/leuven-gravity-institute/gwmock-sevn)
[![PyPI Version](https://img.shields.io/pypi/v/gwmock-sevn)](https://pypi.org/project/gwmock-sevn/)
[![Python Versions](https://img.shields.io/pypi/pyversions/gwmock-sevn)](https://pypi.org/project/gwmock-sevn/)
[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![SPEC 0 — Minimum Supported Dependencies](https://img.shields.io/badge/SPEC-0-green?labelColor=%23004811&color=%235CA038)](https://scientific-python.org/specs/spec-0000/)

[SEVN](https://gitlab.com/sevncodes/sevn) (Stellar EVolution for N-body), the
binary population-synthesis code of Iorio et al. 2023, as an installable Python
package.

Each wheel carries SEVN's binary-evolution program, compiled from a pinned SEVN
release. The stellar-track tables (about 360 MB in all) are not in the wheel:
each set is fetched on first use from SEVN's repository at the same commit, and
every file is checked against its recorded SHA-256.

## Installation

```bash
pip install gwmock-sevn
```

Wheels are built for Linux (x86_64, aarch64) and macOS (arm64). Elsewhere,
installing from source needs a C++14 compiler. Windows is not supported.

## Usage

```python
from gwmock_sevn import evolve_binaries

result = evolve_binaries(
    {
        "mass_0": [30.0],
        "metallicity_0": [0.002],
        "spin_0": [0.0],
        "supernova_0": ["rapid"],
        "start_0": ["zams"],
        "mass_1": [20.0],
        "metallicity_1": [0.002],
        "spin_1": [0.0],
        "supernova_1": ["rapid"],
        "start_1": ["zams"],
        "semimajor": [500.0],
        "eccentricity": [0.1],
        "end": ["end"],
        "output_times": ["end"],
        "seed": [12345],
    },
    options={"ce_alpha": 1.0},
    processes=4,
)
result.output["RemnantType_0"], result.events
```

The columns are SEVN's input list, in SEVN's units (Msun, Rsun, Myr). `options`
passes any further SEVN parameter by name. Every binary carries its own seed, so
a run is reproducible binary by binary, however it is split across processes.
Tables are cached under `$GWMOCK_SEVN_CACHE`, or `~/.cache/gwmock-sevn` by
default.

## Relation to SEVN

The SEVN source is vendored in `extern/sevn` from the release named in
`extern/sevn/VENDORED`. It carries two changes, in `patches/`. The first lets
the installed program find its auxiliary data through `SEVN_PATH`, rather than
through the path it was compiled in. The second makes SEVN's build report SEVN's
own commit when it is built inside this package, and keeps its generated header
out of the source tree. SEVN is distributed under its own MIT licence, installed
with the package as `gwmock_sevn/data/SEVN_LICENSE`.

If you use this package, cite SEVN: Iorio et al. 2023, MNRAS 524, 426, and the
references in SEVN's documentation.
