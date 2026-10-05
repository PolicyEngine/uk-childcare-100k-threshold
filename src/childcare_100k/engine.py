"""Population runs: one policyengine-uk microsimulation per process.

Each job (dataset, scenario) runs in its own Python process with its working
directory at ``.cache/worker``, so policyengine.py's managed loader finds the
dataset in ``./data`` (it reuses a file whose sha256 matches the release
bundle and downloads nothing). Microcosm needs ~20-40 GB per process, so jobs
run one at a time.

The job writes record-level arrays to ``.cache/runs/<dataset>__<scenario>.npz``.
Those files are gitignored and never published: ``aggregate.py`` turns them
into weighted totals before anything reaches ``data/results.json``.
"""

import argparse
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from .config import (
    FREE_HOURS_VARIABLES,
    HOURS_USAGE_VARIABLE,
    REFORM_PARAMETERS,
    RUNS,
    SCENARIOS,
    TFC_VARIABLE,
    VALIDATION_YEAR,
    WORKER,
    YEARS,
    parameter_changes,
)


def run_path(dataset, scenario):
    return RUNS / f"{dataset}__{scenario}.npz"


def meta_path(dataset, scenario):
    return RUNS / f"{dataset}__{scenario}.json"


def _simulation(dataset, scenario):
    from policyengine.tax_benefit_models.uk import managed_microsimulation
    from policyengine_uk.utils.scenario import Scenario

    spec = SCENARIOS[scenario]
    params = spec["params"]
    assert set(params) <= set(REFORM_PARAMETERS)
    if not params:
        sim = managed_microsimulation(dataset=dataset)
    else:
        sim = managed_microsimulation(
            dataset=dataset,
            scenario=Scenario(parameter_changes=parameter_changes(params), applied_before_data_load=True),
        )
    sim.baseline = None  # nothing in this analysis compares against the scenario's comparator
    for variable, value in spec["inputs"].items():
        entity = sim.tax_benefit_system.variables[variable].entity.key
        n = sim.populations[entity].count
        for y in [VALIDATION_YEAR] + YEARS:
            sim.set_input(variable, y, np.full(n, value))
    return sim


def _index(ids, values):
    order = np.argsort(ids)
    return order[np.searchsorted(ids, values, sorter=order)]


def extract(sim, year, baseline_extras=False):
    """Arrays for one year (household, benunit and person level)."""

    def calc(v, to=None):
        return np.asarray(sim.calculate(v, year, map_to=to).values) if to else np.asarray(sim.calculate(v, year).values)

    out = {}
    hh_ids = calc("household_id")
    out["hh_weight"] = calc("household_weight").astype(float)
    out["hh_country"] = np.asarray(calc("country"), dtype=str)
    out["hh_decile"] = calc("household_income_decile").astype(int)
    out["hh_net_income"] = calc("household_net_income").astype(float)
    out["hh_free"] = sum(calc(v, "household") for v in FREE_HOURS_VARIABLES).astype(float)
    out["hh_tfc"] = calc(TFC_VARIABLE, "household").astype(float)
    for v in FREE_HOURS_VARIABLES:  # components, to show the universal-to-extended switch
        out[f"hh_{v}"] = calc(v, "household").astype(float)
    out["hh_gov_balance"] = calc("gov_balance").astype(float)

    out["bu_weight"] = calc("benunit_weight").astype(float)
    out["bu_household"] = _index(hh_ids, calc("household_id", "benunit"))
    out["bu_free"] = sum(calc(v, "benunit") for v in FREE_HOURS_VARIABLES).astype(float)
    out["bu_tfc"] = calc(TFC_VARIABLE, "benunit").astype(float)

    out["bu_ext_eligible"] = calc("extended_childcare_entitlement_eligible").astype(bool)
    out["bu_hours_usage"] = calc(HOURS_USAGE_VARIABLE).astype(float)
    rates = sim.tax_benefit_system.parameters(f"{year}-06-01").gov.dfe.childcare_funding_rate
    out["rate_by_age"] = np.array([rates.calc(np.array([a]))[0] for a in (0, 1, 2, 3, 4)], dtype=float)

    bu_ids = calc("benunit_id")
    out["p_benunit"] = _index(bu_ids, calc("benunit_id", "person"))
    out["p_age"] = calc("age").astype(float)
    out["p_is_child"] = calc("is_child").astype(bool)
    out["p_free"] = (
        calc("is_child_receiving_extended_childcare").astype(bool)
        | calc("is_child_receiving_universal_childcare").astype(bool)
        | calc("is_child_receiving_targeted_childcare").astype(bool)
    )
    out["p_extended"] = calc("is_child_receiving_extended_childcare").astype(bool)
    out["p_tfc"] = calc("is_child_receiving_tax_free_childcare").astype(bool)
    if baseline_extras:
        ani = calc("adjusted_net_income").astype(float)
        relief = calc("pension_contributions_relief").astype(float)
        out["p_weight"] = calc("person_weight").astype(float)
        out["p_ani_over"] = ani > 100_000
        out["p_ani_at_least"] = ani >= 100_000
        out["p_ani_net_pension_over"] = (ani - relief) > 100_000
        out["bu_would_claim_extended"] = calc("would_claim_extended_childcare").astype(bool)
        out["bu_would_claim_tfc"] = calc("would_claim_tfc").astype(bool)
    return out


def run_job(dataset, scenario):
    t0 = time.time()
    sim = _simulation(dataset, scenario)
    load = time.time() - t0
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
    np.savez_compressed(run_path(dataset, scenario), **arrays)
    peak_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9  # bytes on macOS
    meta = {
        "dataset": dataset,
        "scenario": scenario,
        "seconds": round(time.time() - t0, 1),
        "load_seconds": round(load, 1),
        "peak_rss_gb": round(peak_gb, 1),
        "bundle": {k: v for k, v in sim.policyengine_bundle.items() if isinstance(v, (str, int, float))},
    }
    meta_path(dataset, scenario).write_text(json.dumps(meta, indent=1))
    return meta


def run_isolated(dataset, scenario, repo, log=print):
    """Run one job in a fresh process (cwd = the worker dir holding ./data)."""
    WORKER.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "childcare_100k.engine", dataset, scenario],
        cwd=WORKER,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(Path(repo) / "src")},
    )
    if result.returncode != 0:
        raise RuntimeError(f"{dataset}/{scenario} failed:\n{result.stderr[-4000:]}")
    meta = json.loads(meta_path(dataset, scenario).read_text())
    log(f"  {dataset}/{scenario}: {meta['seconds']}s, peak {meta['peak_rss_gb']} GB")
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("scenario", choices=list(SCENARIOS))
    a = ap.parse_args(argv)
    run_job(a.dataset, a.scenario)


if __name__ == "__main__":
    main()
