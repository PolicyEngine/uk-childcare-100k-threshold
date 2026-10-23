"""Population runs: one policyengine.py microsimulation per process.

Each job (scenario) runs in its own Python process on the pinned Microcosm
release (``datasets.py``), through policyengine.py's ``managed_microsimulation``
with the verified local file passed as an unmanaged dataset (no policyengine.py
bundle registers the release yet), on the policyengine-uk version the release
pins (2.147.2).

A reform that names its baseline (``config.SCENARIOS``, ``net_new_hours``) nets the
value of each child's new funded hours off that child's ``childcare_expenses`` before
anything else is computed (``net_new_hours``): ``childcare_expenses`` is a fixed survey
input, so otherwise a newly eligible child would get the new funded hours and Tax-Free
Childcare on the whole of the care they replace. The baseline's run must be cached
first; its person ids are checked against the reform's.

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
    FAMILY_TYPES,
    REGIONS,
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
from . import labour_supply
from .corrections import apply_corrections, is_applied
from .datasets import MICROCOSM, POLICYENGINE_UK_VERSION, dataset_path

SOURCE_DIR = Path(__file__).resolve().parent
# The labour supply job (labour_supply.py): builds the central baseline and reform
# simulations itself and stores aggregates, not record-level arrays.
LABOUR_SUPPLY_JOB = "labour_supply"
JOBS = list(SCENARIOS) + [LABOUR_SUPPLY_JOB]
LSR_SETTINGS = (
    "HOURS_FOR_NEW_ENTRANTS", "FULL_TIME_HOURS", "LSR_WEEKS_PER_YEAR", "ELASTICITY_SCALES",
    "PARTICIPATION_CHANGE_BOUND", "HOURS_PRICE_ELASTICITY", "FREE_HOURS_DISPLACEMENT", "FREE_HOURS_DISPLACEMENT_RANGE",
    "YOUNGEST_CHILD_MAX_AGE", "INCOME_BASIS", "INCOME_BASIS_SENSITIVITIES", "PRICE_BASIS",
    "PRICE_BASIS_SENSITIVITIES", "YOUNGEST_CHILD_BANDS",
)


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
        "labour_supply": {k: getattr(config, k) for k in LSR_SETTINGS},
    }
    digest = hashlib.sha256()
    for name in ("engine.py", "datasets.py", "corrections.py", "labour_supply.py", "hours_response.py"):
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

    installed = importlib.metadata.version("policyengine-uk")
    if installed != POLICYENGINE_UK_VERSION:
        raise RuntimeError(f"policyengine-uk {installed} installed; the release pins {POLICYENGINE_UK_VERSION}")
    spec = SCENARIOS[scenario]
    params = spec["params"]
    assert set(params) <= set(REFORM_PARAMETERS)
    # Every run, baseline and reform alike, carries the model correction (corrections.py).
    run_scenario = Scenario(
        parameter_changes=parameter_changes(params) if params else None,
        simulation_modifier=apply_corrections,
        applied_before_data_load=True,
    )
    sim = managed_microsimulation(dataset=str(dataset_path()), allow_unmanaged=True, scenario=run_scenario)
    if not is_applied(sim.tax_benefit_system):
        raise RuntimeError(f"{scenario}: the correction did not reach the simulation")
    sim.baseline = None  # nothing in this analysis compares against the scenario's comparator
    for variable, value in spec["inputs"].items():
        entity = sim.tax_benefit_system.variables[variable].entity.key
        n = sim.populations[entity].count
        for y in [VALIDATION_YEAR] + YEARS:
            sim.set_input(variable, y, np.full(n, value))
    return sim


def person_free_value(sim, year):
    """Each person's funded hours at their funding value (£ a year): all three entitlements."""
    return sum(np.asarray(sim.calculate(v, year)).astype(float) for v in PERSON_FREE_HOURS_VARIABLES)


def net_new_hours(sim, scenario):
    """Net each child's new funded hours off its childcare spending in the reform (every analysis year).

    The value of a child's newly funded hours (reform less baseline, at their funding value)
    comes off that child's ``childcare_expenses``, floored at zero. Fees are above funding
    rates, so this is conservative. Funded hours do not depend on childcare spending, so
    the reform's own free-hours values are unchanged by it. Returns, by year, the Tax-Free
    Childcare paid on each household before netting (£), so the netting's effect can be
    reported. The simulation is left with the netted spending and no cached calculations.
    """
    base = run_path(SCENARIOS[scenario]["base"])
    load_meta(SCENARIOS[scenario]["base"])  # the baseline run must be current
    z = np.load(base)
    ids = np.asarray(sim.calculate("person_id", YEARS[0])).astype(np.int64)
    before, netted = {}, {}
    for y in YEARS:
        if not np.array_equal(z[f"{y}/p_id"], ids):
            raise ValueError(f"{scenario}: person order differs from the baseline run's")
        new = np.maximum(person_free_value(sim, y) - z[f"{y}/p_free_value"], 0.0)
        spend = np.asarray(sim.calculate("childcare_expenses", y)).astype(float)
        netted[y] = np.maximum(spend - new, 0.0)
        before[y] = np.asarray(sim.calculate(TFC_VARIABLE, y, map_to="household")).astype(float)
    sim.reset_calculations()
    for y, value in netted.items():
        sim.set_input("childcare_expenses", y, value.astype(np.float32))
    return before


def _index(ids, values):
    """Positions of ``values`` in ``ids`` (the entity each member belongs to)."""
    order = np.argsort(ids)
    pos = order[np.searchsorted(ids, values, sorter=order)]
    if not np.array_equal(ids[pos], values):
        raise ValueError("entity id mapping failed: a member's group id is not among the group ids")
    return pos


PERSON_FREE_HOURS_VARIABLES = (
    "extended_childcare_entitlement_per_child",
    "universal_childcare_entitlement",
    "targeted_childcare_entitlement",
)


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
    out["bu_tfc_claim"] = calc("would_claim_tfc").astype(bool)
    out["hh_gov_balance"] = calc("gov_balance").astype(float)

    bu_ids = calc("benunit_id")
    out["bu_weight"] = calc("benunit_weight").astype(float)
    bu_free = sum(calc(v, "benunit") for v in FREE_HOURS_VARIABLES).astype(float)
    out["bu_free"] = bu_free
    out["bu_tfc"] = calc(TFC_VARIABLE, "benunit").astype(float)
    out["bu_ext_eligible"] = calc("extended_childcare_entitlement_eligible").astype(bool)
    out["bu_hours_usage"] = calc(HOURS_USAGE_VARIABLE).astype(float)
    # The rates the year's formulas use: a year's formulas read parameters at 1 January of its key.
    rates = sim.tax_benefit_system.parameters(f"{year}-01-01").gov.dfe.childcare_funding_rate
    out["rate_by_age"] = np.array([rates.calc(np.array([a]))[0] for a in (0, 1, 2, 3, 4)], dtype=float)

    # Index arrays. Group ids projected onto persons are exact, so each index comes from them;
    # mapping a household value to benefit units with map_to="benunit" does not return the
    # household's own value for many benefit units (about 22,000 of 76,363 in the 2 October 2026 release), so the
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
    # Region of each household and benefit unit, as an integer code in config.REGIONS order.
    out["hh_region"] = calc("region").astype(str)
    region_code = np.array([list(REGIONS).index(r) for r in out["hh_region"]])
    out["bu_region"] = region_code[bu_household]

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
    out["p_id"] = calc("person_id").astype(np.int64)
    out["p_age"] = age
    out["p_spend"] = calc("childcare_expenses").astype(float)
    out["bu_spend"] = calc("childcare_expenses", "benunit").astype(float)
    out["p_is_child"] = is_child
    out["p_extended"] = calc("is_child_receiving_extended_childcare").astype(bool)
    out["p_universal"] = calc("is_child_receiving_universal_childcare").astype(bool)
    out["p_targeted"] = calc("is_child_receiving_targeted_childcare").astype(bool)
    out["p_free"] = out["p_extended"] | out["p_universal"] | out["p_targeted"]
    out["p_tfc"] = calc("is_child_receiving_tax_free_childcare").astype(bool)
    out["p_bu_free"] = project(bu_free)  # the family's free hours, on each member
    out["p_bu_tfc"] = project(out["bu_tfc"])

    # Each person's own free-hours and Tax-Free Childcare value, so a child is counted as
    # gaining only if their own entitlement rises (not a sibling's). All are person-level in
    # policyengine-uk 2.147.2 (the extended entitlement is the benefit-unit sum of
    # extended_childcare_entitlement_per_child), checked to sum back to the benefit units.
    out["p_free_value"] = person_free_value(sim, year)
    if not np.allclose(np.bincount(out["p_benunit"], weights=out["p_free_value"], minlength=len(bu_ids)), bu_free, atol=0.01):
        raise ValueError(f"{year}: per-person free-hours values do not sum to the benefit units' values")
    out["p_tfc_value"] = calc(TFC_VARIABLE).astype(float)
    if not np.allclose(np.bincount(out["p_benunit"], weights=out["p_tfc_value"], minlength=len(bu_ids)), out["bu_tfc"], atol=0.01):
        raise ValueError(f"{year}: per-person TFC values do not sum to the benefit units' values")

    # The income both limits test: adjusted net income, which policyengine-uk 2.147.2 takes after pension
    # contributions (Income Tax Act 2007 s.58). Total income before deductions (net_income, before Gift Aid
    # and pension contributions) is HMRC's basis for its income bands (validation.py).
    ani = calc("adjusted_net_income").astype(float)
    out["p_ani"] = ani
    out["p_ani_over"] = ani > 100_000
    out["p_income_before_deductions_at_least"] = calc("net_income").astype(float) >= 100_000
    out["bu_any_over"] = any_member(out["p_ani_over"])
    out["bu_child_under_5"] = any_member(is_child & (age < 5))
    out["bu_child_under_12"] = any_member(is_child & (age < 12))
    # For the breakdown by sex of the higher earner: each person's sex and whether they have earnings.
    out["p_female"] = calc("gender").astype(str) == "FEMALE"
    out["p_in_work"] = (calc("employment_income").astype(float) + calc("self_employment_income").astype(float)) > 0
    # Family type, as an integer code in config.FAMILY_TYPES order: lone parent, or a couple by number of children.
    n_children = np.bincount(out["p_benunit"], weights=is_child.astype(float), minlength=len(bu_ids))
    family = calc("family_type").astype(str)
    keys = list(FAMILY_TYPES)
    out["bu_family_type"] = np.select(
        [family == "LONE_PARENT", (family == "COUPLE_WITH_CHILDREN") & (n_children == 1),
         (family == "COUPLE_WITH_CHILDREN") & (n_children == 2), (family == "COUPLE_WITH_CHILDREN") & (n_children >= 3)],
        [keys.index("LONE_PARENT"), keys.index("COUPLE_1"), keys.index("COUPLE_2"), keys.index("COUPLE_3")],
        default=keys.index("OTHER"),
    )
    if baseline_extras:
        out["bu_would_claim_extended"] = calc("would_claim_extended_childcare").astype(bool)
        out["bu_would_claim_tfc"] = calc("would_claim_tfc").astype(bool)
        out["p_routed_share"] = calc("tax_free_childcare_spend_routed_share").astype(float)
        out["bu_routed_share"] = calc("tax_free_childcare_spend_routed_share", "benunit").astype(float)
        # For the DfE census rows (validation.py), measured as the release's calibration rows are: children with
        # gross working-parent hours in the year's spring term (1 January), by DfE's age (on 31 December, the
        # year less the birth year). The spring term is funded if it starts after the child reaches the minimum
        # age (term share above zero: the terms run April, September, January) and before it starts school.
        from policyengine_core.periods import period as as_period
        from policyengine_uk.utils.dates import birth_day

        born = np.asarray(birth_day(sim.populations["person"], as_period(str(year)))).astype(np.int64)
        out["p_dfe_age"] = year - born // 10_000
        out["p_wpe_spring"] = (
            (calc("extended_childcare_entitlement_total_per_child").astype(float) > 0)
            & (calc("extended_childcare_entitlement_term_share").astype(float) > 0)
            & (calc("early_years_term_share_before_school").astype(float) >= 1)
        )
    return out


def run_labour_supply_job():
    """The labour supply response (labour_supply.py), stored as aggregates in the run cache."""
    t0 = time.time()
    bundle = {}

    def build(scenario):
        sim = _simulation(scenario)
        if sim.policyengine_bundle.get("managed_by") != "policyengine.py":
            raise RuntimeError(f"{scenario}: the simulation was not built by policyengine.py")
        bundle.update({k: v for k, v in sim.policyengine_bundle.items() if isinstance(v, (str, int, float))})
        return sim

    arrays = labour_supply.run(build, log=lambda m: print(m, flush=True))
    RUNS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(run_path(LABOUR_SUPPLY_JOB), **{k: np.asarray(v) for k, v in arrays.items()})
    meta = {
        "dataset": MICROCOSM.key,
        "scenario": LABOUR_SUPPLY_JOB,
        "provenance": provenance(LABOUR_SUPPLY_JOB),
        "seconds": round(time.time() - t0, 1),
        "load_seconds": None,
        "peak_rss_gb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 1),
        "bundle": bundle,
    }
    meta_path(LABOUR_SUPPLY_JOB).write_text(json.dumps(meta, indent=1))
    return meta


def run_job(scenario):
    if scenario == LABOUR_SUPPLY_JOB:
        return run_labour_supply_job()
    t0 = time.time()
    sim = _simulation(scenario)
    load = time.time() - t0
    if sim.policyengine_bundle.get("managed_by") != "policyengine.py":
        raise RuntimeError(f"{scenario}: the simulation was not built by policyengine.py")
    # The baselines that feed baseline_validation also hold the validation year (2025-26).
    years = ([VALIDATION_YEAR] if scenario in ("baseline", "baseline_hours30") else []) + YEARS
    arrays = {}
    if SCENARIOS[scenario].get("net_new_hours"):
        for y, value in net_new_hours(sim, scenario).items():
            arrays[f"{y}/hh_tfc_before_netting"] = value
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
    ap.add_argument("scenario", choices=JOBS)
    a = ap.parse_args(argv)
    run_job(a.scenario)


if __name__ == "__main__":
    main()
