"""Checks on the published results file and on the reform definition."""

import json
import math
import subprocess
from pathlib import Path

import pytest

from childcare_100k.config import FAMILY_TYPES, REFORM_PARAMETERS, REGIONS, SCENARIOS, YEARS, parameter_changes

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
    for key in ("policyengine", "policyengine_uk", "dataset", "dataset_release", "dataset_repo", "dataset_revision",
                "dataset_sha256", "dataset_management", "generated_at", "git_revision"):
        assert isinstance(m[key], str) and m[key]
    assert m["years"] == YEARS
    assert m["lead_year"] == 2027
    assert m["run_provenance"]["dataset_sha256"] == m["dataset_sha256"]
    assert m["dataset"] == "microcosm_uk_2024_25"
    assert m["dataset_revision"] == "f9d1922cddab6b54a0dd37794a9bac74e3780c88"
    assert m["dataset_sha256"] == "aa31bdf67c977927ea2b325567d1cf7a79d94381239bc79918a0a0fc9c9588af"
    assert not any("cross_check" in k for k in m)
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
    assert "variants" not in b  # the one-limit-only runs were dropped: nothing published used them
    assert not any("cross_check" in k for k in b)
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
        assert [c["region"] for c in d["by_region"]] == list(REGIONS.values())
        assert [c["family_type"] for c in d["by_family_type"]] == list(FAMILY_TYPES.values())
        assert "by_country" not in d  # nations are regions: one breakdown, so no cell is recoverable across two


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


def test_total_is_sum_of_schemes():
    b = RESULTS["budget"]["gross_bn"]
    for y in YEAR_KEYS:
        assert abs(b["thirty_hours"][y] + b["tax_free_childcare"][y] - b["total"][y]) <= 0.002


def test_net_close_to_gross():
    """Static reform: nothing else in the tax-benefit system responds to these two limits."""
    for y in YEAR_KEYS:
        assert abs(RESULTS["budget"]["net_bn"]["total"][y] - RESULTS["budget"]["gross_bn"]["total"][y]) <= 0.01


def test_range_brackets_central():
    r = RESULTS["budget"]["range_bn"]
    eff = RESULTS["budget"]["sensitivities"]["effects_bn"]
    for y in YEAR_KEYS:
        assert r["central"][y] == RESULTS["budget"]["gross_bn"]["total"][y]
        assert r["low"][y] <= r["central"][y] <= r["high"][y]
        low = r["central"][y] + eff["ani_net_of_pension_contributions_and_tfc_routed_share"][y]
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
            assert path.startswith(("/cliff_example", "/household_grid")) or len(value) <= 12, f"{path}/{key}"


def test_counts_are_rounded_aggregates():
    for y in YEAR_KEYS:
        r = RESULTS["recipients"][y]
        for v in (r["families_gaining"], r["children_gaining"], *r["by_scheme"].values()):
            assert v % 1000 == 0


def test_no_data_files_tracked():
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    assert not [f for f in tracked if f.endswith((".h5", ".npz", ".h5.metadata.json"))]


# ── Disclosure control ─────────────────────────────────────────────────────


def test_cell_with_no_gainers_but_one_loser_is_suppressed():
    from childcare_100k.aggregate import _cell_ok

    assert _cell_ok(0, 0)
    assert _cell_ok(12, 15)
    assert not _cell_ok(0, 1)  # no gainers, one losing record: its loss would be published
    assert not _cell_ok(3, 12)


def test_lone_suppressed_cell_gets_a_complement():
    from childcare_100k.aggregate import _complement

    cells = [
        {"region": "England", "total_change_bn": 0.5, "families_gaining": 150_000, "suppressed": False},
        {"region": "Scotland", "total_change_bn": 0.02, "families_gaining": 9_000, "suppressed": False},
        {"region": "Wales", "total_change_bn": None, "families_gaining": None, "suppressed": True},
        {"region": "Northern Ireland", "total_change_bn": 0.0, "families_gaining": 0, "suppressed": False},
    ]
    out = _complement(cells, [900, 40, 5, 0])
    # Northern Ireland has no change, so suppressing it protects nothing; Scotland is the next smallest.
    assert [c["suppressed"] for c in out] == [False, True, True, False]
    assert out[1]["total_change_bn"] is None and out[1]["families_gaining"] is None
    assert out[1]["region"] == "Scotland"


@pytest.mark.parametrize("year", YEAR_KEYS)
def test_no_lone_suppressed_cell_in_published_breakdowns(year):
    """A single suppressed cell could be recovered from the published UK total less the other cells."""
    dist = RESULTS["distribution"][year]
    for cells in (dist["by_decile"], dist["by_region"], dist["by_family_type"]):
        assert sum(c["suppressed"] for c in cells) != 1
        for c in cells:
            if c["suppressed"]:
                assert all(v is None for k, v in c.items() if k not in ("decile", "region", "family_type", "suppressed"))


def test_benchmark_and_take_up_wording():
    b = RESULTS["benchmarks"][0]
    assert "like-for-like comparison is our static cost of the 30 funded hours" in b["like_for_like"]
    assert b["ours"] == RESULTS["budget"]["gross_bn"]["thirty_hours"][str(b["year"])]
    assert "CenTax" in b["like_for_like"] and b["underlying_source_url"].startswith("https://centax.org.uk/")
    text = " ".join(RESULTS["limitations"])
    assert "same for families above and below" not in text
    assert "expects" in text  # the realised-for-expected income proxy is disclosed


def test_modelling_assumptions_carry_the_tested_effects():
    rows = {r["id"]: r for r in RESULTS["modelling_assumptions"]}
    eff = RESULTS["budget"]["sensitivities"]["effects_bn"]
    assert rows["hours"]["effect_bn"] == eff["full_30_hour_usage"]
    assert rows["under_ones"]["effect_bn"] == eff["under_ones"]
    for r in rows.values():
        assert r["title"] and r["modelled"]
        assert ("alternative" in r) == ("effect_bn" in r)


def test_cliff_example_is_the_grid_default():
    g, c = RESULTS["household_grid"], RESULTS["cliff_example"]
    d = g["default"]
    s = g["series"][f"{d['parent']}|{d['children']}|{d['spend_per_child']}"]
    assert c["earnings"] == g["earnings"] and c["net_income_baseline"] == s["baseline"]


# ── Labour supply ───────────────────────────────────────────────────────────


def test_labour_supply_block():
    ls = RESULTS["labour_supply"]
    static = RESULTS["budget"]["gross_bn"]["total"]
    for bound in ("central", "low", "high"):
        for block in ("extensive", "intensive", "intensive_over_limit"):
            _by_year(ls[block]["offset_bn"][bound])
            _by_year(ls[block]["ftes"][bound])
        _by_year(ls["extensive"]["entrants"][bound])
        for y in YEAR_KEYS:
            total = ls["extensive"]["offset_bn"][bound][y] + ls["intensive"]["offset_bn"][bound][y]
            assert ls["total_offset_bn"][bound][y] == pytest.approx(total, abs=0.0015)
            # The dynamic cost is the published static total less both margins (not the over-limit sensitivity).
            assert ls["dynamic_cost_bn"][bound][y] == pytest.approx(static[y] - ls["total_offset_bn"][bound][y], abs=0.0015)
            # The reform only adds work-conditional support, so (to rounding) nobody leaves work.
            assert ls["extensive"]["leavers"][bound][y] <= 100
            assert ls["extensive"]["entrants"][bound][y] >= 0
    for y in YEAR_KEYS:
        lo, mid, hi = (ls["intensive"]["offset_bn"][b][y] for b in ("low", "central", "high"))
        assert lo <= mid <= hi
        assert ls["population"][y]["adults_moved_outside_population"] == 0
    assert "bunching" in ls["not_modelled"]


def test_static_assumption_carries_the_labour_supply_effect():
    row = next(r for r in RESULTS["modelling_assumptions"] if r["id"] == "static")
    assert row["alternative"].startswith("Parents respond")
    offset = RESULTS["labour_supply"]["total_offset_bn"]["central"]
    for y in YEAR_KEYS:
        assert row["effect_bn"][y] == pytest.approx(-offset[y], abs=0.0005)


@pytest.mark.parametrize("year", YEAR_KEYS)
def test_gender_breakdown_adds_up_and_is_suppressed_safely(year):
    g = RESULTS["gender"][year]
    cells = g["families_gaining_by_earner"]
    assert sum(c["suppressed"] for c in cells) != 1
    shown = sum(c["families_gaining"] for c in cells if not c["suppressed"])
    assert shown <= RESULTS["recipients"][year]["families_gaining"] + 2_000  # cells rounded to the nearest thousand
    for p in g["partner_not_working"]:
        if not p["suppressed"]:
            assert 0 <= p["partner_not_working_pct"] <= 100
