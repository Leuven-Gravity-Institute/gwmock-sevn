"""Evolving binaries with the bundled SEVN program.

These run SEVN, so they fetch the default PARSEC and pure-He track sets (about 47 MB, cached).
"""

from __future__ import annotations

import numpy as np
import pytest

from gwmock_sevn import INPUT_COLUMNS, evolve_binaries

pytestmark = pytest.mark.unit

N_BINARIES = 60


def _binaries(count: int = N_BINARIES, seed: int = 1) -> dict[str, list]:
    """Massive binaries at Z = 0.002 that mostly end as compact objects."""
    rng = np.random.default_rng(seed)
    primary = rng.uniform(10, 60, count)
    return {
        "mass_0": list(primary),
        "metallicity_0": [2e-3] * count,
        "spin_0": [0.0] * count,
        "supernova_0": ["rapid"] * count,
        "start_0": ["zams"] * count,
        "mass_1": list(primary * rng.uniform(0.1, 1, count)),
        "metallicity_1": [2e-3] * count,
        "spin_1": [0.0] * count,
        "supernova_1": ["rapid"] * count,
        "start_1": ["zams"] * count,
        "semimajor": list(10 ** rng.uniform(1, 4, count)),
        "eccentricity": list(rng.uniform(0, 0.9, count)),
        "end": ["end"] * count,
        "output_times": ["end"] * count,
        "seed": list(rng.integers(1, 2**48, count)),
    }


def _same(first, second) -> bool:
    if set(first.output) != set(second.output):
        return False
    for key, values in first.output.items():
        other = second.output[key]
        nan_aware = values.dtype.kind == "f"
        if values.shape != other.shape or not np.array_equal(values, other, equal_nan=nan_aware):
            return False
    return first.events == second.events and first.failed == second.failed


@pytest.fixture(scope="module")
def reference():
    """The batch every test below compares against."""
    return evolve_binaries(_binaries())


def test_every_binary_is_evolved_to_its_end(reference):
    """With output at ``"end"``, SEVN writes each binary's initial and final state, in batch order."""
    initialised = sorted(set(range(N_BINARIES)) - set(reference.failed))
    assert reference.output["ID"].tolist() == [index for index in initialised for _ in range(2)]
    initial, final = reference.output["Worldtime_0"][::2], reference.output["Worldtime_0"][1::2]
    assert np.all(initial == 0.0)
    assert np.all(final > 0.0)
    compact = (reference.output["RemnantType_0"] >= 5) & (reference.output["RemnantType_1"] >= 5)
    assert compact.any(), "no binary ended as two compact objects, so the batch tests too little"


def test_the_result_does_not_depend_on_how_the_batch_is_split(reference):
    """Each binary has its own seed, so the processes it lands in change nothing."""
    assert _same(reference, evolve_binaries(_binaries(), processes=3))


def test_the_same_seeds_give_the_same_result(reference):
    """The same seeds give the same result."""
    assert _same(reference, evolve_binaries(_binaries()))


def test_a_binary_s_seed_drives_only_that_binary(reference):
    """Changing one seed changes that binary and leaves every other one as it was."""
    binaries = _binaries()
    changed = int(np.argmax(reference.output["RemnantType_0"] >= 5))
    binaries["seed"][changed] += 1
    result = evolve_binaries(binaries)

    rows = reference.output["ID"] != changed
    for key, values in reference.output.items():
        if key == "name":
            continue
        assert np.array_equal(values[rows], result.output[key][rows], equal_nan=values.dtype.kind == "f"), key
    differs = [
        key
        for key, values in reference.output.items()
        if not np.array_equal(values[~rows], result.output[key][~rows], equal_nan=values.dtype.kind == "f")
    ]
    assert differs, "the changed seed changed nothing about its own binary"


def test_events_name_the_binary_and_the_star(reference):
    """Star events carry the star (0 or 1); every event points at a binary of the batch."""
    assert {event["kind"] for event in reference.events} <= {"B", "S"}
    assert all(0 <= event["ID"] < N_BINARIES for event in reference.events)
    stars = {event["star"] for event in reference.events if event["kind"] == "S"}
    assert stars <= {0, 1}
    assert stars
    assert all(event["star"] is None for event in reference.events if event["kind"] == "B")


def test_a_sevn_parameter_changes_the_evolution(reference):
    """``options`` reach SEVN: a different common-envelope efficiency gives a different result."""
    assert not _same(reference, evolve_binaries(_binaries(), options={"ce_alpha": 5.0}))


def test_a_binary_sevn_cannot_initialise_is_reported():
    """A binary sevn cannot initialise is reported."""
    binaries = _binaries(4)
    binaries["mass_0"][2] = 0.5  # below the tracks' lowest mass
    result = evolve_binaries(binaries)

    assert result.failed == [2]
    assert 2 not in result.output["ID"].tolist()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda b: b.pop("seed"), "Missing input columns: seed"),
        (lambda b: b["seed"].pop(), "same length"),
        (lambda b: [b[column].clear() for column in INPUT_COLUMNS], "No binaries"),
    ],
)
def test_malformed_input_is_refused(change, message):
    """Malformed input is refused."""
    binaries = _binaries(3)
    change(binaries)
    with pytest.raises(ValueError, match=message):
        evolve_binaries(binaries)


@pytest.mark.parametrize("name", ["tables", "list", "rseed", "o"])
def test_a_parameter_gwmock_sevn_sets_is_refused(name):
    """A parameter gwmock sevn sets is refused."""
    with pytest.raises(ValueError, match="set by gwmock-sevn"):
        evolve_binaries(_binaries(2), options={name: "x"})


def test_two_binaries_with_one_seed_are_refused():
    """SEVN names a binary from its seed; two equal seeds would merge their logfile events."""
    binaries = _binaries(3)
    binaries["seed"][2] = binaries["seed"][0]
    with pytest.raises(ValueError, match="its own seed"):
        evolve_binaries(binaries)


def test_two_binaries_sevn_named_alike_are_refused():
    """A name shared by two binaries is an error, not a silent attribution to one of them."""
    from gwmock_sevn.evolve import _positions_by_name

    assert _positions_by_name({"name": ["a", "a", "b"], "ID": ["0", "0", "1"]}) == {"a": 0, "b": 1}
    with pytest.raises(RuntimeError, match="the same name a"):
        _positions_by_name({"name": ["a", "b", "a"], "ID": ["0", "1", "2"]})


def test_an_integer_column_beyond_int64_is_kept():
    """Too wide for int64, a column falls back to floats instead of failing the run."""
    from gwmock_sevn.evolve import _as_array

    assert _as_array(["1", "2"]).dtype == np.int64
    assert _as_array(["9223372036854775808", "1"]).dtype == np.float64
    assert _as_array(["rapid", "1"]).dtype.kind == "U"


def test_the_program_reports_the_vendored_sevn_commit():
    """The bundled program's own provenance names SEVN's commit, not this package's."""
    import subprocess

    from gwmock_sevn import SEVN_COMMIT, executable

    info = subprocess.run([str(executable())], capture_output=True, text=True, check=True).stdout  # noqa: S603
    assert SEVN_COMMIT in info
