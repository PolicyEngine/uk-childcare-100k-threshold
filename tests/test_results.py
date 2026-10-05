"""Checks on the published results file and on the reform definition."""

import json
import math
import subprocess
from pathlib import Path

import pytest

from childcare_100k.config import REFORM_PARAMETERS, SCENARIOS, YEARS, parameter_changes

REPO = Path(__file__).resolve().parents[1]
RESULTS = json.loads((REPO / "data" / "results.json").read_text())
YEAR_KEYS = [str(y) for y in YEARS]


def _number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


# ── Schema ─────────────────────────────────────────────────────────────────


def test_top_level_keys():
    for key in ("meta", "reform", "budget", "recipients", "distribution", "baseline_validation", "cliff_example",
                "benchmarks", "limitations"):
        assert key in RESULTS


def test_meta():
    m = RESULTS["meta"]
    for key in ("policyengine", "policyengine_uk", "dataset", "dataset_revision", "cross_check_dataset",
                "generated_at", "git_revision"):
        assert isinstance(m[key], str) and m[key]
    assert m["years"] == YEARS
    assert m["dataset"] == "enhanced_frs_2024_25"
    assert m["cross_check_dataset"] == "populace_uk_2023"
    assert "sample" not in m  # the dashboard fixture's flag; never set on real results


def test_reform_block():
    r = RESULTS["reform"]
    assert isinstance(r["title"], str) and isinstance(r["description"], str)
    assert [p["name"] for p in r["parameters"]] == REFORM_PARAMETERS
    for p in r["parameters"]:
        assert p["baseline"] == 100_000 and p["reform"] == "removed"


def _by_year(d):
    assert sorted(d) == YEAR_KEYS
    assert all(_number(v) for v in d.values())


def test_budget_shape():
    b = RESULTS["budget"]
    for k in ("thirty_hours", "tax_free_childcare", "total"):
        _by_year(b["gross_bn"][k])
    _by_year(b["net_bn"]["total"])
    _by_year(b["variants"]["thirty_hours_only"])
    _by_year(b["variants"]["tfc_only"])
    _by_year(b["cross_check"]["total"])
    for k in ("low", "central", "high"):
        _by_year(b["range_bn"][k])


def test_recipients_and_distribution_shape():
    for y in YEAR_KEYS:
        r = RESULTS["recipients"][y]
        for k in ("families_gaining", "children_gaining", "mean_gain_gbp"):
            assert _number(r[k])
        assert set(r["by_scheme"]) == {"thirty_hours", "tax_free_childcare"}
        d = RESULTS["distribution"][y]
        assert [row["decile"] for row in d["by_decile"]] == list(range(1, 11))
        for row in d["by_decile"]:
            keys = ("mean_change_gbp", "pct_change", "share_gaining_pct")
            if row.get("suppressed"):
                assert all(row[k] is None for k in keys)
            else:
                assert all(_number(row[k]) for k in keys)
                assert 0 <= row["share_gaining_pct"] <= 100  # a percentage, not a fraction
        assert {c["country"] for c in d["by_country"]} == {"England", "Scotland", "Wales", "Northern Ireland"}


def test_validation_benchmarks_cliff():
    for row in RESULTS["baseline_validation"]:
        for k in ("label", "unit", "source", "url"):
            assert isinstance(row[k], str) and row[k]
        assert isinstance(row["year"], int) and _number(row["model"]) and _number(row["official"])
    c = RESULTS["cliff_example"]
    n = len(c["earnings"])
    assert n == len(c["net_income_baseline"]) == len(c["net_income_reform"])
    assert c["year"] == 2027
    b = RESULTS["benchmarks"][0]
    assert b["source"] == "Conservative Party" and _number(b["ours"]) and b["url"].startswith("https://")
    assert all(isinstance(s, str) for s in RESULTS["limitations"])


# ── Totals add up ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("block", ["primary", "cross_check"])
def test_total_is_sum_of_schemes(block):
    b = RESULTS["budget"]["gross_bn"] if block == "primary" else RESULTS["budget"]["cross_check"]
    for y in YEAR_KEYS:
        assert abs(b["thirty_hours"][y] + b["tax_free_childcare"][y] - b["total"][y]) <= 0.002


def test_net_close_to_gross():
    """Static reform: nothing else in the tax-benefit system responds to these two limits."""
    for y in YEAR_KEYS:
        assert abs(RESULTS["budget"]["net_bn"]["total"][y] - RESULTS["budget"]["gross_bn"]["total"][y]) <= 0.01


def test_variants_add_to_total():
    b = RESULTS["budget"]
    for y in YEAR_KEYS:
        both = b["variants"]["thirty_hours_only"][y] + b["variants"]["tfc_only"][y]
        assert abs(both - b["gross_bn"]["total"][y]) <= 0.005


def test_range_brackets_central():
    r = RESULTS["budget"]["range_bn"]
    eff = RESULTS["budget"]["sensitivities"]["effects_bn"]
    for y in YEAR_KEYS:
        assert r["central"][y] == RESULTS["budget"]["gross_bn"]["total"][y]
        assert r["low"][y] <= r["central"][y] <= r["high"][y]
        low = r["central"][y] + eff["ani_net_of_pension_contributions"][y] + eff["tfc_routed_share"][y]
        high = r["central"][y] + eff["full_30_hour_usage"][y] + eff["under_ones"][y]
        assert abs(low - r["low"][y]) <= 0.004 and abs(high - r["high"][y]) <= 0.004


# ── The reform changes only the two limits ────────────────────────────────


def test_scenarios_only_touch_the_two_limits():
    assert REFORM_PARAMETERS == [
        "gov.dfe.extended_childcare_entitlement.income.limit",
        "gov.hmrc.tax_free_childcare.income.income_limit",
    ]
    for spec in SCENARIOS.values():
        assert set(spec["params"]) <= set(REFORM_PARAMETERS)
        assert set(parameter_changes(spec["params"])) == set(spec["params"])
    assert set(SCENARIOS["reform"]["params"]) == set(REFORM_PARAMETERS)
    # Sensitivity overrides are identical in the baseline and reform run they are compared with.
    for name in ("hours30", "routed"):
        assert SCENARIOS[f"baseline_{name}"]["inputs"] == SCENARIOS[f"reform_{name}"]["inputs"]


def test_model_parameter_tree_differs_only_in_the_two_limits():
    """Snapshot every parameter, apply the reform to the same tree, and diff."""
    pytest.importorskip("policyengine_uk")
    from policyengine_core.parameters import Parameter
    from policyengine_uk import CountryTaxBenefitSystem
    from policyengine_uk.utils.parameters import uk_fiscal_year_period

    system = CountryTaxBenefitSystem()

    def apply(changes):  # as policyengine_uk.Simulation.apply_parameter_changes
        system.reset_parameters()
        for name, values in changes.items():
            for period, value in values.items():
                system.parameters.get_child(name).update(period=uk_fiscal_year_period(period), value=value)
        system.process_parameters()
        leaves = [p for p in system.parameters.get_descendants() if isinstance(p, Parameter)]
        return {(p.name, y): repr(p(f"{y}-10-01")) for p in leaves for y in YEARS}

    before = apply({})
    after = apply(parameter_changes(REFORM_PARAMETERS))
    changed = {name for (name, y), v in before.items() if after[(name, y)] != v}
    assert changed == set(REFORM_PARAMETERS)
    for name in REFORM_PARAMETERS:
        for y in YEARS:
            assert after[(name, y)] == "inf"


# ── No record-level data ──────────────────────────────────────────────────


FORBIDDEN_KEY_PARTS = ("_id", "weight", "record", "person_", "household_id", "benunit_id")


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}/{k}")
            yield path, k, v
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")


def test_no_record_level_keys_or_long_arrays():
    for path, key, value in _walk(RESULTS):
        assert not any(part in key.lower() for part in FORBIDDEN_KEY_PARTS), f"{path}/{key}"
        if isinstance(value, list) and value and all(_number(v) for v in value):
            # Only the synthetic cliff household's earnings grid may be a long numeric series.
            assert path.startswith("/cliff_example") or len(value) <= 12, f"{path}/{key}"


def test_counts_are_rounded_aggregates():
    for y in YEAR_KEYS:
        r = RESULTS["recipients"][y]
        for v in (r["families_gaining"], r["children_gaining"], *r["by_scheme"].values()):
            assert v % 1000 == 0


def test_no_data_files_tracked():
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.split()
    assert not [f for f in tracked if f.endswith((".h5", ".npz", ".h5.metadata.json"))]
