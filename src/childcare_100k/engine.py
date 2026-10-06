"""Population runs: one policyengine.py microsimulation per process.

Each job (scenario) runs in its own Python process on the pinned Microcosm
release (``datasets.py``), through policyengine.py's ``managed_microsimulation``
with the verified local file passed as an unmanaged dataset (policyengine.py
6.2.1's bundle does not register the certified release).

The job writes record-level arrays to ``.cache/runs/microcosm_uk_2024_25__<scenario>.npz``:
each entity's values, its weights (``hh_weight``, ``bu_weight``, ``p_weight``)
and the person-to-benefit-unit and benefit-unit-to-household index arrays
(``p_benunit``, ``bu_household``), so ``aggregate.py`` can build weighted
microdf series from them. The files are gitignored and never published.

Each run also stores a provenance key (dataset key, revision and sha256,
policyengine.py and policyengine-uk versions, a hash of the run definition and
the scenario). ``load_meta`` refuses a run whose key does not match the current
one, so a version bump, a new dataset or a changed run definition cannot reuse
stale arrays.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from . import config
from .config import (
    COUNTRIES,
    FREE_HOURS_VARIABLES,
    HOURS_USAGE_VARIABLE,
    REFORM_PARAMETERS,
    RUNS,
    SCENARIOS,
    TFC_VARIABLE,
    VALIDATION_YEAR,
    YEARS,
    parameter_changes,
)
from .datasets import MICROCOSM, dataset_path

SOURCE_DIR = Path(__file__).resolve().parent


def run_path(scenario):
    return RUNS / f"{MICROCOSM.key}__{scenario}.npz"


def meta_path(scenario):
    return RUNS / f"{MICROCOSM.key}__{scenario}.json"


def run_definition_hash():
    """Hash of everything a run's arrays depend on: this module, the dataset module and the run settings."""
    settings = {
        "years": YEARS,
        "validation_year": VALIDATION_YEAR,
        "scenarios": SCENARIOS,
        "reform_parameters": REFORM_PARAMETERS,
        "free_hours_variables": FREE_HOURS_VARIABLES,
        "tfc_variable": TFC_VARIABLE,
        "hours_usage_variable": HOURS_USAGE_VARIABLE,
        "removed": repr(config.REMOVED),
    }
    digest = hashlib.sha256()
    for name in ("engine.py", "datasets.py"):
        digest.update((SOURCE_DIR / name).read_bytes())
    digest.update(json.dumps(settings, sort_keys=True).encode())
    return digest.hexdigest()


def provenance(scenario):
    """What a cached run must match to be reused."""
    return {
        "dataset": MICROCOSM.key,
        "dataset_repo": MICROCOSM.repo_id,
        "dataset_revision": MICROCOSM.revision,
        "dataset_sha256": MICROCOSM.sha256,
        "policyengine": importlib.metadata.version("policyengine"),
        "policyengine_uk": importlib.metadata.version("policyengine-uk"),
        "run_definition_sha256": run_definition_hash(),
        "scenario": scenario,
    }


def _simulation(scenario):
    from policyengine.tax_benefit_models.uk import managed_microsimulation
    from policyengine_uk.utils.scenario import Scenario

    spec = SCENARIOS[scenario]
    params = spec["params"]
    assert set(params) <= set(REFORM_PARAMETERS)
    kwargs = {}
    if params:
        kwargs["scenario"] = Scenario(parameter_changes=parameter_changes(params), applied_before_data_load=True)
    sim = managed_microsimulation(dataset=str(dataset_path()), allow_unmanaged=True, **kwargs)
    sim.baseline = None  # nothing in this analysis compares against the scenario's comparator
    for variable, value in spec["inputs"].items():
        entity = sim.tax_benefit_system.variables[variable].entity.key
        n = sim.populations[entity].count
        for y in [VALIDATION_YEAR] + YEARS:
            sim.set_input(variable, y, np.full(n, value))
    return sim


def _index(ids, values):
    """Positions of ``values`` in ``ids`` (the entity each member belongs to)."""
    order = np.argsort(ids)
    pos = order[np.searchsorted(ids, values, sorter=order)]
    if not np.array_equal(ids[pos], values):
        raise ValueError("entity id mapping failed: a member's group id is not among the group ids")
    return pos


def extract(sim, year, baseline_extras=False):
    """Arrays for one year: household (hh_), benunit (bu_) and person (p_) values, weights and index arrays."""

    def calc(v, to=None):
        series = sim.calculate(v, year, map_to=to) if to else sim.calculate(v, year)
        return np.asarray(series)

    out = {}
    hh_ids = calc("household_id")
    out["hh_weight"] = calc("household_weight").astype(float)
    out["hh_country"] = calc("country").astype(str)
    out["hh_decile"] = calc("household_income_decile").astype(int)
    out["hh_net_income"] = calc("household_net_income").astype(float)
    for v in FREE_HOURS_VARIABLES:  # components, to show the universal-to-extended switch
        out[f"hh_{v}"] = calc(v, "household").astype(float)
    out["hh_free"] = sum(out[f"hh_{v}"] for v in FREE_HOURS_VARIABLES)
    out["hh_tfc"] = calc(TFC_VARIABLE, "household").astype(float)
    out["hh_gov_balance"] = calc("gov_balance").astype(float)

    bu_ids = calc("benunit_id")
    out["bu_weight"] = calc("benunit_weight").astype(float)
    bu_free = sum(calc(v, "benunit") for v in FREE_HOURS_VARIABLES).astype(float)
    out["bu_free"] = bu_free
    out["bu_tfc"] = calc(TFC_VARIABLE, "benunit").astype(float)
    out["bu_ext_eligible"] = calc("extended_childcare_entitlement_eligible").astype(bool)
    out["bu_hours_usage"] = calc(HOURS_USAGE_VARIABLE).astype(float)
    rates = sim.tax_benefit_system.parameters(f"{year}-06-01").gov.dfe.childcare_funding_rate
    out["rate_by_age"] = np.array([rates.calc(np.array([a]))[0] for a in (0, 1, 2, 3, 4)], dtype=float)

    # Index arrays. Group ids projected onto persons are exact, so each index comes from them;
    # mapping a household value to benefit units with map_to="benunit" does not return the
    # household's own value for about 22,000 of 76,363 benefit units in this release, so the
    # benefit-unit-to-household index is built from the members.
    out["p_weight"] = calc("person_weight").astype(float)
    out["p_benunit"] = _index(bu_ids, calc("benunit_id", "person"))
    out["p_household"] = _index(hh_ids, calc("household_id", "person"))
    bu_household = np.full(len(bu_ids), -1)
    bu_household[out["p_benunit"]] = out["p_household"]
    if (bu_household < 0).any():
        raise ValueError("a benefit unit has no members")
    if not np.array_equal(bu_household[out["p_benunit"]], out["p_household"]):
        raise ValueError("a benefit unit's members are in different households")
    out["bu_household"] = bu_household
    # Country of each benefit unit, as an integer code in config.COUNTRIES order.
    hh_code = np.array([list(COUNTRIES).index(c) for c in out["hh_country"]])
    out["bu_country"] = hh_code[bu_household]

    def any_member(person_flag):
        """Benefit units with at least one member flagged (simulation mapping, checked against the index)."""
        mapped = sim.map_result(np.asarray(person_flag, dtype=float), "person", "benunit", how="sum")
        exact = np.bincount(out["p_benunit"], weights=np.asarray(person_flag, dtype=float), minlength=len(bu_ids))
        if not np.allclose(mapped, exact):
            raise ValueError("person-to-benunit mapping disagrees with the member index")
        return mapped > 0

    def project(bu_values):
        """A benefit-unit value on each member (simulation mapping, checked against the index)."""
        mapped = sim.map_result(np.asarray(bu_values), "benunit", "person")
        if not np.allclose(mapped, np.asarray(bu_values)[out["p_benunit"]]):
            raise ValueError("benunit-to-person projection disagrees with the member index")
        return mapped

    age = calc("age").astype(float)
    is_child = calc("is_child").astype(bool)
    out["p_age"] = age
    out["p_is_child"] = is_child
    out["bu_n_age0"] = sim.map_result((is_child & (age < 1)).astype(float), "person", "benunit", how="sum")
    out["p_extended"] = calc("is_child_receiving_extended_childcare").astype(bool)
    out["p_universal"] = calc("is_child_receiving_universal_childcare").astype(bool)
    out["p_targeted"] = calc("is_child_receiving_targeted_childcare").astype(bool)
    out["p_free"] = out["p_extended"] | out["p_universal"] | out["p_targeted"]
    out["p_tfc"] = calc("is_child_receiving_tax_free_childcare").astype(bool)
    out["p_bu_free"] = project(bu_free)  # the family's free hours, on each member
    out["p_bu_tfc"] = project(out["bu_tfc"])

    ani = calc("adjusted_net_income").astype(float)
    relief = calc("pension_contributions_relief").astype(float)
    out["p_ani"] = ani
    out["p_pension_relief"] = relief
    out["p_ani_over"] = ani > 100_000
    out["p_ani_at_least"] = ani >= 100_000
    out["p_ani_net_pension_over"] = (ani - relief) > 100_000
    out["bu_any_over"] = any_member(out["p_ani_over"])
    out["bu_any_over_law"] = any_member(out["p_ani_net_pension_over"])  # ANI net of pension contributions
    out["bu_child_under_5"] = any_member(is_child & (age < 5))
    out["bu_child_under_12"] = any_member(is_child & (age < 12))
    if baseline_extras:
        out["bu_would_claim_extended"] = calc("would_claim_extended_childcare").astype(bool)
        out["bu_would_claim_tfc"] = calc("would_claim_tfc").astype(bool)
        out["p_routed_share"] = calc("tax_free_childcare_spend_routed_share").astype(float)
        out["bu_routed_share"] = calc("tax_free_childcare_spend_routed_share", "benunit").astype(float)
    return out


def run_job(scenario):
    t0 = time.time()
    sim = _simulation(scenario)
    load = time.time() - t0
    if sim.policyengine_bundle.get("managed_by") != "policyengine.py":
        raise RuntimeError(f"{scenario}: the simulation was not built by policyengine.py")
    years = ([VALIDATION_YEAR] if scenario == "baseline" else []) + YEARS
    arrays = {}
    for y in years:
        for k, v in extract(sim, y, baseline_extras=scenario == "baseline").items():
            arrays[f"{y}/{k}"] = v
    if SCENARIOS[scenario]["params"]:  # confirm the reform reached the parameters
        p = sim.tax_benefit_system.parameters
        for name in SCENARIOS[scenario]["params"]:
            for y in YEARS:
                assert p.get_child(name)(f"{y}-06-01") == float("inf"), name
    RUNS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(run_path(scenario), **arrays)
    peak_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9  # bytes on macOS
    meta = {
        "dataset": MICROCOSM.key,
        "scenario": scenario,
        "provenance": provenance(scenario),
        "seconds": round(time.time() - t0, 1),
        "load_seconds": round(load, 1),
        "peak_rss_gb": round(peak_gb, 1),
        "bundle": {k: v for k, v in sim.policyengine_bundle.items() if isinstance(v, (str, int, float))},
    }
    meta_path(scenario).write_text(json.dumps(meta, indent=1))
    return meta


def load_meta(scenario):
    """A cached run's metadata, refused unless its provenance matches the current data, versions and run definition."""
    path = meta_path(scenario)
    if not path.exists() or not run_path(scenario).exists():
        raise FileNotFoundError(f"no cached run for {scenario}; run it first")
    meta = json.loads(path.read_text())
    expected = provenance(scenario)
    if meta.get("provenance") != expected:
        raise RuntimeError(
            f"cached run {scenario} does not match the current data, versions or run definition "
            f"(stored {meta.get('provenance')}, expected {expected}); rerun it"
        )
    return meta


def is_current(scenario):
    """True if a cached run exists and its provenance matches; a mismatched run is rerun, never reused."""
    try:
        load_meta(scenario)
    except (FileNotFoundError, RuntimeError):
        return False
    return True


def run_isolated(scenario, repo, log=print):
    """Run one job in a fresh process."""
    result = subprocess.run(
        [sys.executable, "-m", "childcare_100k.engine", scenario],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,  # the return code is checked below, with the job's stderr
        env={**os.environ, "PYTHONPATH": str(Path(repo) / "src")},
    )
    if result.returncode != 0:
        raise RuntimeError(f"{scenario} failed:\n{result.stderr[-4000:]}")
    meta = load_meta(scenario)
    log(f"  {scenario}: {meta['seconds']}s, peak {meta['peak_rss_gb']} GB")
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=list(SCENARIOS))
    a = ap.parse_args(argv)
    run_job(a.scenario)


if __name__ == "__main__":
    main()
