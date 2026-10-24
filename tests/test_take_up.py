"""Unit tests for the 30-hours take-up bases (config.TAKE_UP_BASES; aggregate.person_changes, household_changes,
basis_recipients). They run on small synthetic runs, so they need no population data."""

import numpy as np
import pytest

from childcare_100k import aggregate as A
from childcare_100k.config import (
    EXPECTED_SCENARIOS,
    EXTENDED_TAKE_UP_RATE,
    HEADLINE_TAKE_UP_BASIS,
    TAKE_UP_BASES,
)

YEAR = 2027


class FakeRun:
    """A run's arrays for one year, keyed like ``engine.extract``'s output."""

    def __init__(self, **arrays):
        self.arrays = arrays

    def __call__(self, year, name):
        assert year == YEAR
        return self.arrays[name]


# ── The rates ───────────────────────────────────────────────────────────────


def test_headline_is_dfe_and_the_rates_are_the_sources():
    assert HEADLINE_TAKE_UP_BASIS == "dfe"
    assert list(TAKE_UP_BASES) == ["dfe", "centax", "contract"]
    assert TAKE_UP_BASES["dfe"]["rates_by_dfe_age"] == {0: 0.42, 1: 0.70, 2: 0.84, 3: 0.91, 4: 0.91, 5: 0.91}
    assert TAKE_UP_BASES["centax"]["rates_by_dfe_age"] == {0: 0.73, 1: 0.73, 2: 0.73, 3: 0.91, 4: 0.91, 5: 0.91}
    assert TAKE_UP_BASES["contract"]["rate"] == EXTENDED_TAKE_UP_RATE == 0.8361
    for spec in TAKE_UP_BASES.values():
        assert spec["source_url"].startswith("https://")
        assert all(s in EXPECTED_SCENARIOS for s in spec["pair"])


@pytest.mark.parametrize(
    ("dfe_age", "dfe", "centax"),
    [
        (-1, None, None),  # born after 31 December: no funded hours in the year
        (0, 0.42, 0.73),  # the 9-11-month-olds of the spring term
        (1, 0.70, 0.73),
        (2, 0.84, 0.73),  # the last age under 3
        (3, 0.91, 0.91),  # the first 3-and-4 age
        (4, 0.91, 0.91),
        (5, 0.91, 0.91),  # born September to December, funded for the summer term before reception (aged 4 then)
        (6, None, None),
    ],
)
def test_rate_by_dfe_age_at_the_boundaries(dfe_age, dfe, centax):
    for basis, expected in (("dfe", dfe), ("centax", centax)):
        got = A.dfe_age_rates(TAKE_UP_BASES[basis]["rates_by_dfe_age"], np.array([dfe_age]))[0]
        if expected is None:
            assert np.isnan(got)
        else:
            assert got == expected


def test_dfe_age_5_keeps_the_3_and_4_rate_on_every_child_level_basis():
    # DfE age 5 (the summer term before reception) is in DfE's 3-and-4 group, not a band of its own.
    for spec in TAKE_UP_BASES.values():
        if spec["unit"] == "child":
            rates = spec["rates_by_dfe_age"]
            assert rates[5] == rates[4] == rates[3]


def test_the_two_child_level_bases_differ_only_under_3():
    dfe, centax = (TAKE_UP_BASES[b]["rates_by_dfe_age"] for b in ("dfe", "centax"))
    assert [a for a in dfe if dfe[a] != centax[a]] == [0, 1, 2]


def test_the_claim_and_use_pair_sets_every_child_using_the_hours_and_keeps_the_hours_cap():
    for name in ("baseline_claim_use_all", "reform_claim_use_all"):
        inputs = EXPECTED_SCENARIOS[name]["inputs"]
        assert inputs["would_claim_extended_childcare"] is True and inputs["would_claim_universal_childcare"] is True
        assert inputs["max_free_entitlement_hours_used"] == 30
        assert "maximum_extended_childcare_hours_usage" not in inputs
    assert EXPECTED_SCENARIOS["reform_claim_use_all"]["base"] == "baseline_claim_use_all"
    # The contract basis's pair is unchanged, so its figures stay reproducible.
    assert EXPECTED_SCENARIOS["baseline_claim_all"]["inputs"] == {
        "would_claim_extended_childcare": True, "would_claim_universal_childcare": True}


# ── A toy population ────────────────────────────────────────────────────────
#
# Household 0 (weight 10,000): an adult, a child of DfE age 0 and a child of DfE age 2, all newly eligible.
# Household 1 (weight 20,000): an adult, a child of DfE age 4 newly eligible for the extra 15 hours (it keeps its
# universal 1,000), and a child of DfE age 6 whose Tax-Free Childcare does not depend on the hours.

HH_W = np.array([10_000.0, 20_000.0])
P_HH = np.array([0, 0, 0, 1, 1, 1])
P_W = HH_W[P_HH]
FREE_BEFORE = np.array([0.0, 0.0, 0.0, 0.0, 1_000.0, 0.0])
FREE_AFTER = np.array([0.0, 2_000.0, 6_000.0, 0.0, 4_000.0, 0.0])
TFC_NETTED = np.array([0.0, 100.0, 0.0, 0.0, 200.0, 500.0])
TFC_BEFORE_NETTING = np.array([0.0, 500.0, 1_000.0, 0.0, 800.0, 500.0])


def _hh(person_values):
    return np.bincount(P_HH, weights=person_values, minlength=2)


def _common(dfe_age):
    return dict(
        hh_weight=HH_W, bu_weight=HH_W, p_weight=P_W, p_id=np.arange(6), p_household=P_HH, p_benunit=P_HH,
        p_is_child=np.array([False, True, True, False, True, True]), p_dfe_age=np.asarray(dfe_age),
    )


def _pair(dfe_age=(35, 0, 2, 40, 4, 6), tfc_netted=TFC_NETTED, tfc_before=TFC_BEFORE_NETTING, free_after=FREE_AFTER):
    zero = np.zeros(6)
    split = {f"p_free_{k}": zero for k in ("universal", "targeted")}
    base = FakeRun(**_common(dfe_age), **split, p_free_value=FREE_BEFORE, p_free_extended=FREE_BEFORE,
                   p_tfc_value=zero, hh_free=_hh(FREE_BEFORE), hh_tfc=_hh(zero))
    reform = FakeRun(**_common(dfe_age), **split, p_free_value=free_after, p_free_extended=free_after,
                     p_tfc_value=tfc_netted, p_tfc_before_netting=tfc_before, hh_free=_hh(free_after),
                     hh_tfc=_hh(tfc_netted), hh_tfc_before_netting=_hh(tfc_before))
    return base, reform


def _runs(**pair_kwargs):
    base, reform = _pair(**pair_kwargs)
    expected = {"baseline_claim_all": base, "reform_claim_all": reform,
                "baseline_claim_use_all": base, "reform_claim_use_all": reform}
    return {"baseline": base, "reform": reform}, expected


def test_child_level_cost_is_each_childs_change_times_its_rate():
    runs, expected = _runs()
    h = A.household_changes(runs, expected, YEAR)
    # 30 hours: 0.42 x 2,000 + 0.84 x 6,000 in household 0; 0.91 x 3,000 in household 1 (its universal hours kept).
    assert h["dfe"]["thirty_hours"] == pytest.approx([(0.42 * 2_000 + 0.84 * 6_000) * 10_000, 0.91 * 3_000 * 20_000])
    assert h["centax"]["thirty_hours"] == pytest.approx([(0.73 * 8_000) * 10_000, 0.91 * 3_000 * 20_000])
    # Tax-Free Childcare: netted if the child takes up the hours, before netting if not, with the same chance. The
    # DfE-age-6 child's top-up does not depend on the hours, so it is counted in full whatever its (missing) rate.
    hh0 = (0.42 * 100 + 0.58 * 500) + (0.84 * 0 + 0.16 * 1_000)
    hh1 = (0.91 * 200 + 0.09 * 800) + 500
    assert h["dfe"]["tax_free_childcare"] == pytest.approx([hh0 * 10_000, hh1 * 20_000])


def test_contract_basis_is_the_expected_mode_of_issue_7():
    runs, expected = _runs()
    h = A.household_changes(runs, expected, YEAR)
    rate = EXTENDED_TAKE_UP_RATE
    claim_all = _hh(FREE_AFTER - FREE_BEFORE) * HH_W
    assert h["contract"]["thirty_hours"] == pytest.approx(rate * claim_all)
    tfc = rate * _hh(TFC_NETTED) + (1 - rate) * _hh(TFC_BEFORE_NETTING)
    assert h["contract"]["tax_free_childcare"] == pytest.approx(tfc * HH_W)
    out = A.basis_costs(runs, expected, years=[YEAR])
    assert out["contract"]["thirty_hours"][str(YEAR)] == round(float((rate * claim_all).sum()) / 1e9, 3)
    assert out["contract"]["thirty_hours_per_point_m"][str(YEAR)] == int(round(float(claim_all.sum()) / 100 / 1e6))
    assert "thirty_hours_per_point_m" not in out["dfe"]


def test_totals_add_up_on_every_basis():
    runs, expected = _runs()
    out = A.basis_costs(runs, expected, years=[YEAR])
    for basis in TAKE_UP_BASES:
        o = out[basis]
        assert o["total"][str(YEAR)] == round(o["thirty_hours"][str(YEAR)] + o["tax_free_childcare"][str(YEAR)], 3)


def test_components_add_up_to_the_child_level_30_hours():
    runs, expected = _runs()
    comp = A.basis_components(runs, expected, "dfe", years=[YEAR])
    h = A.household_changes(runs, expected, YEAR)
    assert comp["extended"][str(YEAR)] == round(float(h["dfe"]["thirty_hours"].sum()) / 1e9, 3)
    assert comp["universal"][str(YEAR)] == comp["targeted"][str(YEAR)] == 0


def test_a_changed_child_at_an_age_with_no_rate_stops_the_build():
    # The DfE-age-6 child's hours change: no rate covers it.
    runs, expected = _runs(free_after=FREE_AFTER + np.array([0, 0, 0, 0, 0, 500.0]))
    with pytest.raises(ValueError, match="DfE age"):
        A.household_changes(runs, expected, YEAR)
    # The contract basis has no rates by age, but household_changes covers every basis, so the build stops.
    with pytest.raises(ValueError, match="DfE age"):
        A.basis_costs(runs, expected, years=[YEAR])


def test_differing_person_order_between_the_pair_raises():
    runs, expected = _runs()
    expected["reform_claim_use_all"].arrays["p_id"] = np.arange(6)[::-1]
    with pytest.raises(ValueError, match="p_id"):
        A.person_changes(expected, YEAR, "dfe")


# ── Recipients ──────────────────────────────────────────────────────────────


def test_family_gains_if_any_child_takes_up_siblings_independent():
    """No Tax-Free Childcare: household 0 gains only if one of its two children takes up the hours."""
    runs, expected = _runs(tfc_netted=np.zeros(6), tfc_before=np.zeros(6),
                           free_after=np.array([0.0, 2_000.0, 6_000.0, 0.0, 1_000.0, 0.0]))
    out = A.basis_recipients(expected, "dfe", years=[YEAR])[str(YEAR)]
    p_family = 1 - (1 - 0.42) * (1 - 0.84)
    assert out["families_gaining"] == A._k(10_000 * p_family)
    assert out["children_gaining"] == A._k(10_000 * (0.42 + 0.84))
    assert out["by_scheme"]["thirty_hours"] == out["families_gaining"]
    assert out["by_scheme"]["tax_free_childcare"] == 0
    expected_gain = 10_000 * (0.42 * 2_000 + 0.84 * 6_000)
    assert out["mean_gain_gbp"] == round(expected_gain / (10_000 * p_family))


def test_contract_family_takes_up_as_a_whole():
    runs, expected = _runs(tfc_netted=np.zeros(6), tfc_before=np.zeros(6),
                           free_after=np.array([0.0, 2_000.0, 6_000.0, 0.0, 1_000.0, 0.0]))
    out = A.basis_recipients(expected, "contract", years=[YEAR])[str(YEAR)]
    rate = EXTENDED_TAKE_UP_RATE
    assert out["families_gaining"] == A._k(10_000 * rate)
    assert out["children_gaining"] == A._k(10_000 * 2 * rate)
    assert out["mean_gain_gbp"] == round(8_000.0)


def test_a_child_gains_from_tax_free_childcare_whether_or_not_it_takes_up_the_hours():
    runs, expected = _runs()
    out = A.basis_recipients(expected, "dfe", years=[YEAR])[str(YEAR)]
    # Every child gains: each has a top-up before netting, and the newly entitled ones also gain the hours.
    assert out["children_gaining"] == A._k(10_000 * 2 + 20_000 * 2)
    assert out["families_gaining"] == A._k(30_000)
    assert out["by_scheme"]["tax_free_childcare"] == A._k(30_000)
    # The DfE-age-2 child's netted top-up is zero: it gains Tax-Free Childcare only if it does not take up the hours.
    tfc_children = 10_000 * (1 + (1 - 0.84)) + 20_000 * 2
    assert out["children_by_scheme"]["tax_free_childcare"] == A._k(tfc_children)
    assert out["children_by_scheme"]["thirty_hours"] == A._k(10_000 * (0.42 + 0.84) + 20_000 * 0.91)
