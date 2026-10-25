"""Checks on the published results file and on the reform definition."""

import json
import math
import subprocess
from pathlib import Path

import pytest

from childcare_100k.config import (
    FAMILY_TYPES,
    HEADLINE_TAKE_UP_BASIS,
    REFORM_PARAMETERS,
    REGIONS,
    SCENARIOS,
    TAKE_UP_BASES,
    YEARS,
    parameter_changes,
)

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
                "dataset_sha256", "dataset_management", "generated_at", "git_revision", "aggregation_sha256"):
        assert isinstance(m[key], str) and m[key]
    # The results were aggregated by the aggregation code in this checkout (cli._git_revision also refuses a build
    # with uncommitted source, so git_revision is the code that produced them).
    from childcare_100k.cli import _aggregation_hash

    assert m["aggregation_sha256"] == _aggregation_hash()
    assert m["years"] == YEARS
    assert m["lead_year"] == 2027
    assert m["run_provenance"]["dataset_sha256"] == m["dataset_sha256"]
    assert m["dataset"] == "microcosm_uk_2024_25"
    assert m["dataset_revision"] == "c3a751d911ac82e482d298dda0b6f2c949f4ed4d"
    assert m["dataset_release"] == "microcosm-uk-2024-25-national-20261023T075039Z-a133f37a"
    assert m["dataset_sha256"] == "64f83900ca3a1242fb017585234844ce89f743d32e41cd2b6558057777f914aa"
    assert m["policyengine_uk"] == "2.147.2"
    assert "dataset_certified" not in m
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
    for lim in RESULTS["limitations"]:
        assert set(lim) == {"title", "summary", "detail"} and all(isinstance(v, str) for v in lim.values())
        assert lim["title"] and lim["summary"].endswith(".")


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
        low = r["central"][y] + eff["tfc_routed_share"][y]
        high = r["central"][y] + eff["full_30_hour_usage"][y]
        assert abs(low - r["low"][y]) <= 0.004 and abs(high - r["high"][y]) <= 0.004


def test_expected_mode_headline_and_single_draw():
    """The headline is the expected cost on DfE's take-up by age; the contract basis is the claim-all pair times the
    contract rate."""
    b = RESULTS["budget"]
    t = b["take_up"]
    assert t["headline"] == HEADLINE_TAKE_UP_BASIS == "dfe"
    contract = t["bases"]["contract"]
    assert 0 < contract["rate"] < 1
    for y in YEAR_KEYS:
        c = b["thirty_hours_components_bn"]
        assert abs(c["extended"][y] + c["universal"][y] + c["targeted"][y] - b["gross_bn"]["thirty_hours"][y]) <= 0.002
        # Each point of the contract rate is a hundredth of the claim-all cost, which that basis is rate times.
        assert contract["per_point_m"][y] == pytest.approx(
            1000 * contract["gross_bn"]["thirty_hours"][y] / contract["rate"] / 100, abs=1)
        single = b["single_draw_bn"]
        assert abs(single["thirty_hours"][y] + single["tax_free_childcare"][y] - single["total"][y]) <= 0.002
    assert "thirty_hours_take_up" not in b  # moved into take_up.bases.contract


def test_take_up_bases_block():
    """Each take-up basis: its definition and source as config sets them, costs that add up, a range around its own
    total and totals-only recipients. The headline basis is the published headline."""
    t = RESULTS["budget"]["take_up"]
    assert t["order"] == list(TAKE_UP_BASES) == ["dfe", "centax", "contract"]
    assert set(t["bases"]) == set(TAKE_UP_BASES)
    assert "31 December" in t["age"]
    eff = RESULTS["budget"]["sensitivities"]["effects_bn"]
    for basis, spec in TAKE_UP_BASES.items():
        b = t["bases"][basis]
        for k in ("label", "short_label", "description", "source", "source_url", "unit"):
            assert b[k] == spec[k]
        if spec["unit"] == "child":
            assert b["rates_by_dfe_age"] == {str(a): r for a, r in spec["rates_by_dfe_age"].items()}
            assert b["rates_text"]
        else:
            assert b["rate"] == spec["rate"]
        g = b["gross_bn"]
        for y in YEAR_KEYS:
            assert abs(g["thirty_hours"][y] + g["tax_free_childcare"][y] - g["total"][y]) <= 0.002
            assert abs(b["net_bn"]["total"][y] - g["total"][y]) <= 0.01
            r = b["range_bn"]
            assert r["central"][y] == g["total"][y]
            assert r["low"][y] == pytest.approx(g["total"][y] + eff["tfc_routed_share"][y], abs=0.0015)
            assert r["high"][y] == pytest.approx(g["total"][y] + eff["full_30_hour_usage"][y], abs=0.0015)
            rec = b["recipients"][y]
            # Totals only, rounded: no breakdown by age, region or family is published on a take-up basis.
            assert set(rec) == {"families_gaining", "children_gaining", "by_scheme", "children_by_scheme", "mean_gain_gbp"}
            for v in (rec["families_gaining"], rec["children_gaining"], *rec["by_scheme"].values(),
                      *rec["children_by_scheme"].values()):
                assert v % 1000 == 0
            assert max(rec["by_scheme"].values()) <= rec["families_gaining"]
            assert _number(rec["mean_gain_gbp"])
    head = t["bases"][HEADLINE_TAKE_UP_BASIS]
    for k in ("thirty_hours", "tax_free_childcare", "total"):
        assert head["gross_bn"][k] == RESULTS["budget"]["gross_bn"][k]
    assert head["net_bn"]["total"] == RESULTS["budget"]["net_bn"]["total"]
    assert head["range_bn"] == RESULTS["budget"]["range_bn"]


def test_contract_gap_by_dfe_age_adds_up():
    """The split by DfE age of the gap between the contract basis and DfE's adds up to the gap in the 30 hours'
    cost, and the contract's effective rate is below its flat rate only where the usage draw bites (age 0)."""
    t = RESULTS["budget"]["take_up"]
    gap = t["contract_gap_by_dfe_age"]
    y = str(gap["year"])
    bases = t["bases"]
    total_m = 1000 * (bases["contract"]["gross_bn"]["thirty_hours"][y] - bases["dfe"]["gross_bn"]["thirty_hours"][y])
    assert gap["gap_total_m"] == pytest.approx(total_m, abs=2)
    assert sum(gap["gap_m"].values()) == pytest.approx(gap["gap_total_m"], abs=3)
    for k in gap["gap_m"]:
        assert gap["gap_m"][k] == pytest.approx(gap["contract_m"][k] - gap["dfe_m"][k], abs=1)
    rate = bases["contract"]["rate"]
    assert gap["contract_effective_rate"]["0"] < rate - 0.05
    for k in ("1", "2", "3-5"):
        assert gap["contract_effective_rate"][k] == pytest.approx(rate, abs=0.02)


def test_bootstrap_brackets_the_headline():
    u = RESULTS["budget"]["uncertainty"]
    assert u["draws"] == 2000
    assert list(u["by_year"]) == [str(y) for y in RESULTS["meta"]["years"]]
    bases = RESULTS["budget"]["take_up"]["bases"]
    for y, v in u["by_year"].items():
        assert "expected" not in v  # one block per take-up basis instead
        centrals = {"drawn": RESULTS["budget"]["single_draw_bn"], **{k: b["gross_bn"] for k, b in bases.items()}}
        for basis, central in centrals.items():
            for leg in ("thirty_hours", "tax_free_childcare", "total"):
                c = v[basis][leg]
                assert c["sd_bn"] > 0
                assert c["p5_bn"] < central[leg][y] < c["p95_bn"]
        assert 0 < v["effective_source_households_30_hours"] <= v["source_households_30_hours"]
    a = RESULTS["budget"]["age_profile_sensitivity"]
    assert a["even_spread_bn"] > 0 and a["centax_gradient_bn"] > 0


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
    for name in ("hours30", "routed", "tfc_all"):
        assert SCENARIOS[f"baseline_{name}"]["inputs"] == SCENARIOS[f"reform_{name}"]["inputs"]
        assert SCENARIOS[f"reform_{name}"]["base"] == f"baseline_{name}"
    # Every reform nets the new funded hours off childcare spending against its own baseline; no baseline does.
    for name, spec in SCENARIOS.items():
        assert spec.get("net_new_hours", False) == bool(spec["params"])
        assert "toggles" not in spec


def test_tax_free_childcare_leg_and_reconciliation():
    t = RESULTS["budget"]["tax_free_childcare_bn"]
    for k in ("central", "before_netting", "take_up_newly_eligible_low", "take_up_newly_eligible_all"):
        _by_year(t[k])
    assert t["take_up_newly_eligible_low_rate"] == 0.7
    for y in YEAR_KEYS:
        assert t["central"][y] == RESULTS["budget"]["gross_bn"]["tax_free_childcare"][y]
        # Netting the new funded hours off spending can only lower the top-up.
        assert t["central"][y] <= t["before_netting"][y]
        assert t["take_up_newly_eligible_low"][y] == pytest.approx(0.7 * t["take_up_newly_eligible_all"][y], abs=0.0015)
    for gone in ("centax_basis_bn", "bootstrap_sd_bn"):
        assert gone not in RESULTS["budget"]
    r = RESULTS["reconciliation"]
    assert "thirty_hours_reception_excluded_bn" not in r
    for y in YEAR_KEYS:
        assert 0 < r["concentration"][y]["top_ten_share_pct"] <= 100
        assert r["concentration"][y]["kish_effective_sample_size"] <= r["concentration"][y]["gaining_sample_size"]
        assert r["parents_over_100k_with_child_under_5_thousands"][y] % 1000 == 0
    assert "ours_centax_basis" not in RESULTS["benchmarks"][0]


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
    text = " ".join(f"{x['summary']} {x['detail']}" for x in RESULTS["limitations"])
    assert "same for families above and below" not in text
    assert "expects" in text  # the realised-for-expected income proxy is disclosed


def test_modelling_assumptions_carry_the_tested_effects():
    rows = {r["id"]: r for r in RESULTS["modelling_assumptions"]}
    eff = RESULTS["budget"]["sensitivities"]["effects_bn"]
    assert rows["hours"]["effect_bn"] == eff["full_30_hour_usage"]
    assert "effect_bn" not in rows["under_ones"]  # in the model since policyengine-uk#2570
    assert rows["income_test"]["effect_bn"] == eff["tfc_routed_share"]
    t = RESULTS["budget"]["tax_free_childcare_bn"]
    bases = RESULTS["budget"]["take_up"]["bases"]
    for y in YEAR_KEYS:
        assert rows["tfc_take_up"]["effect_bn"][y] == pytest.approx(
            t["take_up_newly_eligible_low"][y] - t["central"][y], abs=1e-9)
        # The 30 hours' take-up alternatives: CenTax's two rates and the contract's flat rate, against DfE's by age.
        for row, basis in (("take_up", "centax"), ("take_up_contract", "contract")):
            assert rows[row]["effect_bn"][y] == pytest.approx(
                bases[basis]["gross_bn"]["total"][y] - bases["dfe"]["gross_bn"]["total"][y], abs=1e-9)
    for r in rows.values():
        assert r["title"] and r["modelled"]
        assert ("alternative" in r) == ("effect_bn" in r)


def test_cliff_example_is_the_grid_default():
    g, c = RESULTS["household_grid"], RESULTS["cliff_example"]
    d = g["default"]
    s = g["series"][f"{d['parent']}|{d['children']}|{d['spend_per_child']}"]
    assert c["earnings"] == g["earnings"] and c["net_income_baseline"] == s["baseline"]


# ── Behaviour ───────────────────────────────────────────────────────────────


def test_no_labour_supply_response_is_published():
    # The costs are static: the labour supply job (parents' hours, partners moving into work) is not published.
    assert "labour_supply" not in RESULTS
    row = next(r for r in RESULTS["modelling_assumptions"] if r["id"] == "static")
    assert "effect_bn" not in row and "alternative" not in row
    assert "bunching" in row["modelled"] and "partners moving into work" in row["modelled"]


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


def test_limitation_splits_at_the_first_sentence():
    from childcare_100k.cli import limitation

    t = "Rule (SI 2015/448 reg 15(1)). Then pp. 5-6 here. Last."
    assert limitation("T", t) == {"title": "T", "summary": "Rule (SI 2015/448 reg 15(1)).", "detail": "Then pp. 5-6 here. Last."}
    assert limitation("T", "One sentence.")["detail"] == ""
