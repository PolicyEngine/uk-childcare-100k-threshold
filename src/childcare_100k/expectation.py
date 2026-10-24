"""The expected-mode pairs: every family claims the 30 hours, for the costs averaged over take-up.

The dataset draws each benefit unit's ``would_claim_extended_childcare`` once, at the
take-up contract's working-parent rate (``config.EXTENDED_TAKE_UP_RATE``), and nests
``would_claim_universal_childcare`` under it (the conditional universal rate is zero, so
the two flags are equal on every record). A single draw decides whether each of the few
heavily weighted newly eligible families claims. The expected cost averages over take-up
instead (PolicyEngine/uk-childcare-100k-threshold#7): each newly eligible family's or
child's cost if it takes up the hours, times the take-up rate (``config.TAKE_UP_BASES``).
This module runs the pairs that give the cost if it takes them up, both flags set to true
for every benefit unit in baseline and reform:

- ``claim_all`` (the contract basis): the extended-hours usage and the under-2 usage
  draws are held as drawn, and the contract's flat family rate applies on top;
- ``claim_use_all`` (the DfE and CenTax bases): every child also uses its hours
  (``max_free_entitlement_hours_used``, the under-2 usage draw, set to 30), because those
  rates are child-level take-up that already counts use; the family's weekly hours cap
  stays as drawn.

Families eligible today are eligible in both runs of a pair, so its change is the newly
eligible families'.

Each reform run nets the new funded hours off childcare spending as the central reform does
(``engine.net_new_hours``), and keeps the Tax-Free Childcare paid before that netting, for
each household and each person: it is what a family or child that does not take up the new
hours gets (aggregate.person_changes). Each run also stores each person's DfE age (31
December: the year less ``birth_year``) and funded hours by entitlement, for the rates by age.

The pairs are kept apart from ``config.SCENARIOS`` so that adding them does not change the
run definition hash and invalidate the other runs. Their cache files carry the same
provenance as the other runs plus a hash of this module, and are refused if either changes.
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

from .config import EXPECTED_SCENARIOS, REFORM_PARAMETERS, TFC_VARIABLE, YEARS, parameter_changes
from .corrections import apply_corrections, is_applied
from .datasets import POLICYENGINE_UK_VERSION, dataset_path
from .engine import PERSON_FREE_HOURS_VARIABLES, RUNS, extract, meta_path, person_free_value, provenance, run_path

SOURCE = Path(__file__).resolve()
JOBS = list(EXPECTED_SCENARIOS)
# engine.PERSON_FREE_HOURS_VARIABLES' per-person funded hours, keyed as aggregate.thirty_hours_components keys them.
FREE_HOURS_KEYS = ("extended", "universal", "targeted")


def module_hash():
    digest = hashlib.sha256(SOURCE.read_bytes())
    digest.update(json.dumps(EXPECTED_SCENARIOS, sort_keys=True).encode())
    return digest.hexdigest()


def _simulation(scenario):
    from policyengine.tax_benefit_models.uk import managed_microsimulation
    from policyengine_uk.utils.scenario import Scenario

    installed = importlib.metadata.version("policyengine-uk")
    if installed != POLICYENGINE_UK_VERSION:
        raise RuntimeError(f"policyengine-uk {installed} installed; the release pins {POLICYENGINE_UK_VERSION}")
    spec = EXPECTED_SCENARIOS[scenario]
    params = spec["params"]
    assert set(params) <= set(REFORM_PARAMETERS)
    run_scenario = Scenario(
        parameter_changes=parameter_changes(params) if params else None,
        simulation_modifier=apply_corrections,
        applied_before_data_load=True,
    )
    sim = managed_microsimulation(dataset=str(dataset_path()), allow_unmanaged=True, scenario=run_scenario)
    if not is_applied(sim.tax_benefit_system):
        raise RuntimeError(f"{scenario}: the correction did not reach the simulation")
    sim.baseline = None
    for variable, value in spec["inputs"].items():
        entity = sim.tax_benefit_system.variables[variable].entity.key
        n = sim.populations[entity].count
        for y in YEARS:
            sim.set_input(variable, y, np.full(n, value))
    return sim


def _net_new_hours(sim, base):
    """engine.net_new_hours against this module's baseline run (same method, scenario-agnostic).

    Returns, by year, the Tax-Free Childcare paid before netting on each household and on each person.
    """
    load_meta(base)
    z = np.load(run_path(base))
    ids = np.asarray(sim.calculate("person_id", YEARS[0])).astype(np.int64)
    before, before_person, netted = {}, {}, {}
    for y in YEARS:
        if not np.array_equal(z[f"{y}/p_id"], ids):
            raise ValueError(f"person order differs from the {base} run's")
        new = np.maximum(person_free_value(sim, y) - z[f"{y}/p_free_value"], 0.0)
        spend = np.asarray(sim.calculate("childcare_expenses", y)).astype(float)
        netted[y] = np.maximum(spend - new, 0.0)
        before_person[y] = np.asarray(sim.calculate(TFC_VARIABLE, y)).astype(float)
        before[y] = np.asarray(sim.calculate(TFC_VARIABLE, y, map_to="household")).astype(float)
    sim.reset_calculations()
    for y, value in netted.items():
        sim.set_input("childcare_expenses", y, value.astype(np.float32))
    return before, before_person


def run_job(scenario):
    t0 = time.time()
    sim = _simulation(scenario)
    load = time.time() - t0
    if sim.policyengine_bundle.get("managed_by") != "policyengine.py":
        raise RuntimeError(f"{scenario}: the simulation was not built by policyengine.py")
    spec = EXPECTED_SCENARIOS[scenario]
    arrays = {}
    if spec.get("base"):
        before, before_person = _net_new_hours(sim, spec["base"])
        for y in YEARS:
            arrays[f"{y}/hh_tfc_before_netting"] = before[y]
            arrays[f"{y}/p_tfc_before_netting"] = before_person[y]
    for y in YEARS:
        for k, v in extract(sim, y).items():
            arrays[f"{y}/{k}"] = v
        # Each person's DfE age (on 31 December of the year, as DfE's January census counts it) and funded hours by
        # entitlement, for the take-up rates by age (aggregate.person_changes).
        arrays[f"{y}/p_dfe_age"] = y - np.asarray(sim.calculate("birth_year", y)).astype(np.int64)
        for variable, key in zip(PERSON_FREE_HOURS_VARIABLES, FREE_HOURS_KEYS):
            arrays[f"{y}/p_free_{key}"] = np.asarray(sim.calculate(variable, y)).astype(float)
        for variable, value in spec["inputs"].items():  # the override reached the simulation
            if not np.all(np.asarray(sim.calculate(variable, y)) == value):
                raise RuntimeError(f"{scenario}: {variable} is not {value} for every record in {y}")
    if spec["params"]:
        p = sim.tax_benefit_system.parameters
        for name in spec["params"]:
            for y in YEARS:
                assert p.get_child(name)(f"{y}-06-01") == float("inf"), name
    RUNS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(run_path(scenario), **arrays)
    meta = {
        "scenario": scenario,
        "provenance": provenance(scenario),
        "expectation_sha256": module_hash(),
        "seconds": round(time.time() - t0, 1),
        "load_seconds": round(load, 1),
        "peak_rss_gb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 1),
        "bundle": {k: v for k, v in sim.policyengine_bundle.items() if isinstance(v, (str, int, float))},
    }
    meta_path(scenario).write_text(json.dumps(meta, indent=1))
    return meta


def load_meta(scenario):
    """A cached expected-mode run's metadata, refused unless both its provenance and this module's hash match."""
    path = meta_path(scenario)
    if not path.exists() or not run_path(scenario).exists():
        raise FileNotFoundError(f"no cached run for {scenario}; run it first")
    meta = json.loads(path.read_text())
    if meta.get("provenance") != provenance(scenario) or meta.get("expectation_sha256") != module_hash():
        raise RuntimeError(f"cached run {scenario} does not match the current data, versions or code; rerun it")
    return meta


def is_current(scenario):
    try:
        load_meta(scenario)
    except (FileNotFoundError, RuntimeError):
        return False
    return True


def run_isolated(scenario, repo, log=print):
    result = subprocess.run(
        [sys.executable, "-m", "childcare_100k.expectation", scenario],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(Path(repo) / "src")},
    )
    if result.returncode != 0:
        raise RuntimeError(f"{scenario} failed:\n{result.stderr[-4000:]}")
    meta = load_meta(scenario)
    log(f"  {scenario}: {meta['seconds']}s, peak {meta['peak_rss_gb']} GB")
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=JOBS)
    run_job(ap.parse_args(argv).scenario)


if __name__ == "__main__":
    main()
