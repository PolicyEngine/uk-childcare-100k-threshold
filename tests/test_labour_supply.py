"""The labour supply response (labour_supply.py, hours_response.py).

The arithmetic tests run on hand-built arrays. The gain-to-work tests run policyengine-uk on
hand-built households, so none of these needs the Microcosm release.
"""

import numpy as np
import pytest

from childcare_100k import config
from childcare_100k import labour_supply as ls
from childcare_100k import hours_response as hr


def _base(**overrides):
    """Four adults: in work at or below the limit, in work over it, in work without childcare spend, not in work."""
    n = 4
    base = {
        "actual_cost": np.array([10_000.0, 10_000.0, 0.0, 8_000.0]),
        "bu_tfc": np.zeros(n),
        "bu_free": np.zeros(n),
        "tfc_rate": np.zeros(n),
        "hh_net_income": np.full(n, 100_000.0),
        "hh_disposable_income": np.full(n, 100_000.0),
        "income_elasticity": np.array([-0.185, -0.05, -0.05, -0.185]),
        "employment_income": np.array([40_000.0, 120_000.0, 30_000.0, 0.0]),
        "weekly_hours": np.array([30.0, 40.0, 30.0, 0.0]),
        "eligible": np.ones(n, bool),
        "hours_eligible": np.ones(n, bool),
        "over_limit": np.array([False, True, False, False]),
        "weights": np.ones(n),
    }
    base.update(overrides)
    return base


def _ref(free=0.0, tfc_rate=0.0, gain=0.0, n=4):
    """The reform: newly funded hours worth ``free``, a Tax-Free Childcare rate, and a cash gain ``gain``."""
    return {"bu_free": np.full(n, free), "bu_tfc": np.zeros(n), "tfc_rate": np.full(n, tfc_rate),
            "bu_tfc_displaced": {hr.displacement_key(d): np.zeros(n) for d in hr.DISPLACEMENTS},
            "hh_net_income": np.full(n, 100_000.0 + gain + free),
            "hh_disposable_income": np.full(n, 100_000.0 + gain)}


def test_funded_hours_below_the_familys_paid_care_are_not_a_price_change():
    """Funded hours worth less than the paid care bought: the marginal hour is still bought at full price."""
    covered, change = hr.marginal_price_change(_base(), _ref(free=4_000.0))
    assert not covered.any()
    np.testing.assert_allclose(change, 0.0)


def test_funded_hours_covering_all_paid_care_make_the_marginal_hour_free():
    covered, change = hr.marginal_price_change(_base(), _ref(free=12_000.0))
    # 12,000 x 90.5% covers the 10,000 and 8,000 families; the family with no spend is not "covered".
    assert covered.tolist() == [True, True, False, True]
    np.testing.assert_allclose(change[covered], -1.0)
    # At the low displacement (71.4%) the 8,000 family is covered and the 10,000 families are not.
    covered_low, _ = hr.marginal_price_change(_base(), _ref(free=12_000.0),
                                              config.FREE_HOURS_DISPLACEMENT_RANGE["low"])
    assert covered_low.tolist() == [False, False, False, True]


def test_tax_free_childcare_is_a_price_change_only_where_the_cap_does_not_bind():
    # Newly received below the cap: 20% of routed spend (59.3%) off each marginal pound.
    _, change = hr.marginal_price_change(_base(), _ref(tfc_rate=0.2 * 0.593))
    np.testing.assert_allclose(change[[0, 1, 3]], -0.2 * 0.593)
    # At the cap the model's marginal rate is zero: no price change, whatever the top-up's size.
    capped = _ref(tfc_rate=0.0)
    capped["bu_tfc"] = np.full(4, 2_000.0)
    np.testing.assert_allclose(hr.marginal_price_change(_base(), capped)[1], 0.0)


def test_each_group_responds_to_price_and_income_separately():
    base, ref = _base(), _ref(tfc_rate=0.1, gain=5_000.0)
    s = hr.earnings_shares(base, ref, 1.0, "at_or_below_limit")
    # The price: only adults in work whose family pays for childcare; the income: every adult in work.
    assert s["respond_price"].tolist() == [True, False, False, False]
    assert s["respond_income"].tolist() == [True, False, True, False]
    assert s["price"][0] == pytest.approx(config.HOURS_PRICE_ELASTICITY * -0.1)
    assert s["income"][0] == pytest.approx(-0.185 * 0.05)
    over = hr.earnings_shares(base, ref, 2.0, "over_limit")
    assert over["respond_price"].tolist() == [False, True, False, False]
    # The bounds scale both elasticities.
    assert over["price"][1] == pytest.approx(2 * config.HOURS_PRICE_ELASTICITY * -0.1)
    assert over["income"][1] == pytest.approx(2 * -0.05 * 0.05)


class _FakeSim:
    """Household net income = 60% of earnings, one person per household: enough to sign the offsets."""

    def __init__(self, base):
        self.emp = base["employment_income"].copy()
        self.w = base["weights"]

    def calculate(self, variable, year, map_to=None):
        return {"household_net_income": 0.6 * self.emp, "household_weight": self.w,
                "employment_income": self.emp}[variable]

    def reset_calculations(self):
        pass

    def set_input(self, variable, year, value):
        assert variable == "employment_income"
        self.emp = np.asarray(value, float)


@pytest.mark.parametrize("group", hr.GROUPS)
def test_price_effect_brings_money_back_and_the_income_effect_costs_money(group):
    """The signs, by hand: a cheaper marginal hour raises hours (offset > 0); a richer family works less (< 0)."""
    base, ref = _base(), _ref(tfc_rate=0.1, gain=5_000.0)
    r = hr.hours_response(_FakeSim(base), 2029, base, ref, 1.0)
    g = r[group]
    worker = 0 if group == "at_or_below_limit" else 1
    emp = base["employment_income"][worker]
    price_earn = emp * config.HOURS_PRICE_ELASTICITY * -0.1
    assert g["price_earnings"] == pytest.approx(price_earn)
    assert g["price_offset"] == pytest.approx(0.4 * price_earn) and g["price_offset"] > 0
    assert g["income_offset"] < 0
    assert g["offset"] == pytest.approx(g["price_offset"] + g["income_offset"])
    assert r["total"]["offset"] == pytest.approx(sum(r[k]["offset"] for k in hr.GROUPS))
    # Funded hours that leave paid care to buy are a lump sum: no price effect, only the income effect.
    lump = hr.hours_response(_FakeSim(base), 2029, base, _ref(free=4_000.0), 1.0)[group]
    assert lump["price_offset"] == 0 and lump["income_offset"] < 0


def _prep(pct, elasticity, emp, eligible=None, over_limit=None, cells=None):
    n = len(pct)
    return {
        "cells": np.zeros((n, len(ls.ENTRY_CELL_LEVELS)), int) if cells is None else np.asarray(cells, int),
        "pct": np.asarray(pct, float),
        "elasticity": np.asarray(elasticity, float),
        "reform_gain": np.full(n, 15_000.0),
        "entrant_subsidy": np.full(n, 200.0),
        "eligible": np.ones(n, bool) if eligible is None else np.asarray(eligible, bool),
        "over_limit": np.zeros(n, bool) if over_limit is None else np.asarray(over_limit, bool),
        "weights": np.full(n, 10.0),
        "employment_income": np.asarray(emp, float),
        "weekly_hours": np.full(n, 30.0),
        "entrant_earnings": np.full(n, 18_000.0),
    }


def test_participation_applies_the_elasticity_to_the_employed_share():
    """C4: 80 workers and 20 non-workers, e x dG/G = 0.02 each: P x e x dG/G = 1.6 entrants per 100."""
    n_work, n_not = 80, 20
    prep = _prep(pct=[0.2] * 100, elasticity=[0.1] * 100, emp=[30_000] * n_work + [0] * n_not)
    prep["weights"] = np.ones(100)
    r = ls.participation_response(prep, 1.0)
    assert r["entrants"] == pytest.approx(1.6)
    assert r["implied_entrants"] == pytest.approx(1.6)
    assert r["non_worker_rule_entrants"] == pytest.approx(0.4)  # the old rule: (1 - P) x e x dG/G
    assert r["leavers"] == 0


def test_participation_response_is_the_expected_value():
    # Worker 0's gain rises (it implies entrants), worker 3's falls (it leaves); the non-worker
    # (1) is who enters; record 2 is outside the population.
    prep = _prep(pct=[0.2, 0.2, 0.2, -0.1], elasticity=[0.1] * 4, emp=[40_000, 0, 0, 50_000],
                 eligible=[True, True, False, True])
    r = ls.participation_response(prep, 1.0)
    assert r["entrants"] == pytest.approx(10 * 0.02)
    assert r["leavers"] == pytest.approx(10 * 0.01)
    assert r["offset"] == pytest.approx(10 * 0.02 * (18_000 - 15_000 - 200) - 10 * 0.01 * (50_000 - 15_000))
    assert ls.participation_response(prep, 2.0)["entrants"] == pytest.approx(2 * r["entrants"])


def test_entrants_are_shared_among_non_workers_by_their_own_response():
    prep = _prep(pct=[0.3, 0.1, 0.3], elasticity=[0.1] * 3, emp=[40_000, 0, 0])
    prep["entrant_earnings"] = np.array([0.0, 10_000.0, 20_000.0])
    r = ls.participation_response(prep, 1.0)
    # 0.3 (scaled by weight 10) of new employment, split 1:3 between the two non-workers.
    assert r["entrants"] == pytest.approx(10 * 0.03)
    assert r["earnings"] == pytest.approx(10 * 0.03 * (0.25 * 10_000 + 0.75 * 20_000))


def test_participation_change_is_bounded():
    prep = _prep(pct=[10.0, 10.0], elasticity=[1.0, 1.0], emp=[40_000, 0])
    r = ls.participation_response(prep, 1.0)
    assert r["entrants"] == pytest.approx(10 * config.PARTICIPATION_CHANGE_BOUND)
    # No non-worker's probability of entering exceeds 1, however many workers imply entrants.
    many = _prep(pct=[1.0] * 5, elasticity=[0.4] * 5, emp=[40_000] * 4 + [0])
    assert ls.participation_response(many, 1.0)["entrants"] == pytest.approx(10 * 1.0)


def test_gain_to_work_elasticity_uses_the_gain_actually_used():
    """A3: e_G = e_I x G / I, with G the childcare-adjusted gain the response uses."""
    n = 1
    base = {
        "gtw_gain_to_work": np.array([10_000.0]),
        "gtw_in_work_income": np.array([150_000.0]),
        "gtw_out_of_work_income": np.array([130_000.0]),
        "elasticity_wrt_income": np.array([0.5]),
        "not_excluded": np.ones(n, bool), "eligible": np.ones(n, bool), "over_limit": np.zeros(n, bool),
        "weights": np.ones(n), "employment_income": np.array([40_000.0]), "weekly_hours": np.array([30.0]),
        "entrant_earnings": np.zeros(n), "cells": np.zeros((n, 4), int), "hourly_wage": np.zeros(n),
    }
    ref = {"gtw_gain_to_work": np.array([11_000.0]), "gtw_in_work_income": np.array([151_000.0]),
           "gtw_out_of_work_income": np.array([130_000.0]), "gtw_entrant_subsidy": np.zeros(n)}
    prep = ls.prepare(base, ref)
    assert prep["elasticity"][0] == pytest.approx(0.5 * 10_000 / 150_000)  # not 0.5 x (150k - 130k) / 150k
    assert prep["pct"][0] == pytest.approx(0.1)


def test_bounds_scale_with_the_price_elasticities():
    assert config.ELASTICITY_SCALES["low"] == pytest.approx(1 / 3)
    assert config.ELASTICITY_SCALES["high"] == pytest.approx(2)


# ── Gain to work on hand-built households (policyengine-uk, no dataset) ────────────


def _couple(partner_a_income, year=2027):
    return {
        "people": {
            "a": {"age": {year: 35}, "employment_income": {year: partner_a_income},
                  "hours_worked": {year: 1_950}, "is_parent": {year: True}},
            "b": {"age": {year: 34}, "employment_income": {year: 0}, "is_parent": {year: True}},
            "child": {"age": {year: 3}, "childcare_expenses": {year: 0}},
        },
        "benunits": {"bu": {"members": ["a", "b", "child"], "would_claim_tfc": {year: True},
                            "would_claim_extended_childcare": {year: True},
                            "maximum_extended_childcare_hours_usage": {year: 30}}},
        "households": {"hh": {"members": ["a", "b", "child"], "region": {year: "SOUTH_EAST"}}},
    }


def _gtw(partner_a_income, reform, year=2027):
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    scenario = Scenario(parameter_changes=config.parameter_changes(config.REFORM_PARAMETERS)) if reform else None
    sim = Simulation(situation=_couple(partner_a_income, year), scenario=scenario)
    entrant = np.array([0.0, 18_000.0, 0.0])
    cost = np.array([0.0, 3_000.0, 0.0])
    return ls.gain_to_work(sim, year, entrant, np.zeros(3), cost)


def test_removing_the_limit_raises_the_partners_gain_to_work_when_the_other_parent_is_over_it():
    before, after = _gtw(120_000, False), _gtw(120_000, True)
    # The partner (b) entering work brings the family the 30 hours and Tax-Free Childcare only under the reform.
    assert after["gain_to_work"][1] > before["gain_to_work"][1] + 1_000
    assert after["entrant_subsidy"][1] > 0 and before["entrant_subsidy"][1] == 0


def test_removing_the_limit_leaves_a_family_under_it_unchanged():
    before, after = _gtw(60_000, False), _gtw(60_000, True)
    assert after["gain_to_work"][1] == pytest.approx(before["gain_to_work"][1], abs=1)


def _disabled_child_family(child_age, year=2027):
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    situation = _couple(120_000, year)
    situation["people"]["b"]["employment_income"] = {year: 18_000}
    situation["people"]["child"] = {"age": {year: child_age}, "is_disabled_for_benefits": {year: True},
                                    "childcare_expenses": {year: 15_000}}
    scenario = Scenario(parameter_changes=config.parameter_changes(config.REFORM_PARAMETERS))
    return Simulation(situation=situation, scenario=scenario)


@pytest.mark.parametrize("child_age", [8, 14])
def test_entrant_subsidy_uses_the_models_disabled_child_cap_and_age(child_age):
    """A8: 20% of £15,000 is £3,000, under the £4,000 disabled-child cap; a disabled child qualifies to 16."""
    sim = _disabled_child_family(child_age)
    subsidy = ls._entrant_subsidy(sim, 2027, np.array([15_000.0, 15_000.0, 15_000.0]))
    model = float(sim.calculate("tax_free_childcare", 2027).sum())
    assert subsidy[1] == pytest.approx(3_000)
    assert model == pytest.approx(3_000)


def _paying_couple(spend, year=2027):
    situation = _couple(120_000, year)
    situation["people"]["b"]["employment_income"] = {year: 30_000}
    situation["people"]["b"]["hours_worked"] = {year: 1_560}
    situation["people"]["child"]["childcare_expenses"] = {year: spend}
    return situation


@pytest.mark.parametrize("spend, reform, expected", [
    (5_000, True, 0.2),   # newly eligible, below the £2,000 cap: 20p off each marginal pound
    (15_000, True, 0.0),  # at the cap: the top-up is a lump sum
    (5_000, False, 0.0),  # baseline: a parent over £100,000, no Tax-Free Childcare
])
def test_marginal_tax_free_childcare_rate_is_the_models(spend, reform, expected):
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    scenario = Scenario(parameter_changes=config.parameter_changes(config.REFORM_PARAMETERS)) if reform else None
    sim = Simulation(situation=_paying_couple(spend), scenario=scenario)
    rate = hr.tfc_marginal_rate(sim, 2027)
    np.testing.assert_allclose(rate, expected, atol=1e-3)
    # The simulation is restored.
    assert float(sim.calculate("childcare_expenses", 2027).sum()) == pytest.approx(spend)


def test_income_elasticities_are_the_obrs_for_the_costed_year():
    from policyengine_uk import Simulation

    situation = _paying_couple(5_000)
    situation["people"]["a"]["gender"] = {2027: "MALE"}
    situation["people"]["b"]["gender"] = {2027: "FEMALE"}
    situation["benunits"]["bu"]["is_married"] = {2027: True}
    e = ls.income_elasticities(Simulation(situation=situation), 2027)
    # A man in a couple, and a woman in a couple whose youngest child is 3-4 (OBR Table A2).
    assert e[0] == pytest.approx(-0.05)
    assert e[1] == pytest.approx(-0.173)


class _FamiliesSim:
    """Two couples with a child of 3, both parents in work: one married, one cohabiting (no engine)."""

    default_calculation_period = 2027

    def __init__(self):
        n = lambda *v: np.array(v)  # noqa: E731
        self.person = {
            "gender": n("MALE", "FEMALE", "MALE", "MALE", "FEMALE", "MALE"),
            "is_married": n(True, True, True, False, False, False),
            "is_couple": n(True, True, True, True, True, True),
            "benunit_count_children": n(1, 1, 1, 1, 1, 1),
            "youngest_child_age": n(3, 3, 3, 3, 3, 3),
            "is_household_head": n(True, False, False, True, False, False),
            "benunit_count_adults": n(2, 2, 2, 2, 2, 2),
            "employment_income": n(60_000.0, 40_000.0, 0.0, 60_000.0, 40_000.0, 0.0),
            "benunit_id": n(1, 1, 1, 2, 2, 2),
            "adult_index": n(1, 2, 0, 1, 2, 0),
            "age": n(40, 38, 3, 40, 38, 3),
        }

    def calculate(self, variable, period=None, map_to=None, **kwargs):
        return self.person[variable]


def test_cohabiting_parents_get_the_couple_income_elasticities():
    """OBR Table A2: a man in a couple -0.05, a woman in a couple whose youngest child is 3-4 -0.173."""
    e = ls.income_elasticities(_FamiliesSim(), 2027)
    np.testing.assert_allclose(e[[0, 1]], [-0.05, -0.173])
    np.testing.assert_allclose(e[[3, 4]], e[[0, 1]])
    # Why the view is needed: upstream reads legal marriage, so the cohabiting father gets nothing
    # (a "lone father") and the cohabiting mother the lone-parent rate. Drop the view when this fails.
    from policyengine_uk.dynamics.progression import calculate_labour_net_income_elasticities
    upstream = calculate_labour_net_income_elasticities(_FamiliesSim())
    np.testing.assert_allclose(upstream[[3, 4]], [0.0, -0.037])


def test_cohabiting_parents_get_the_couple_participation_elasticities():
    """OBR Table A1: the same row for a cohabiting as for a married parent (men; women with a working partner, 3-5)."""
    from policyengine_uk.dynamics.participation import calculate_participation_elasticities

    quintile = np.array([3, 3, 1, 3, 3, 1])
    e = calculate_participation_elasticities(ls.CoupleView(_FamiliesSim()), quintile)
    np.testing.assert_allclose(e[[0, 1]], [0.136, 0.589])
    np.testing.assert_allclose(e[[3, 4]], e[[0, 1]])
    upstream = calculate_participation_elasticities(_FamiliesSim(), quintile)
    np.testing.assert_allclose(upstream[[3, 4]], [0.0, 0.932])


def test_couple_elasticities_leave_marriage_in_the_simulation_alone():
    """A cohabiting couple in policyengine-uk: couple elasticities, while is_married (and so tax) is unchanged."""
    from policyengine_uk import Simulation

    situation = _paying_couple(5_000)
    situation["people"]["a"]["gender"] = {2027: "MALE"}
    situation["people"]["b"]["gender"] = {2027: "FEMALE"}
    situation["benunits"]["bu"]["is_married"] = {2027: False}
    sim = Simulation(situation=situation)
    tax = sim.calculate("income_tax", 2027).sum()
    e = ls.income_elasticities(sim, 2027)
    assert e[0] == pytest.approx(-0.05) and e[1] == pytest.approx(-0.173)
    assert not sim.calculate("is_married", 2027).any()
    assert sim.calculate("income_tax", 2027).sum() == pytest.approx(tax)


def test_income_effect_is_a_share_of_disposable_income():
    """A household whose net income is near zero after expected stamp duty still has a bounded percentage change."""
    base = _base(hh_net_income=np.full(4, 1_000.0))
    ref = _ref(gain=5_000.0)
    ref["hh_net_income"] = base["hh_net_income"] + 5_000.0
    ref["hh_disposable_income"] = base["hh_disposable_income"] + 5_000.0
    respond, change = hr.income_change(base, ref, "at_or_below_limit")
    np.testing.assert_allclose(change[respond], 0.05)
    # No disposable income: no percentage change, rather than a clipped 100%.
    base["hh_disposable_income"] = np.zeros(4)
    np.testing.assert_allclose(hr.income_change(base, ref, "at_or_below_limit")[1], 0.0)


# ── The rereview of #6: A1-A4, S1 ─────────────────────────────────────────────────


def test_funded_value_exactly_equal_to_the_spend_does_not_make_the_next_hour_free():
    """S1: funded hours worth exactly the paid care cover the hours bought, not the next one."""
    base = _base(actual_cost=np.full(4, 100.0))
    exact = hr.marginal_price_change(base, _ref(free=100.0), displacement=1.0)
    assert not exact[0].any()
    np.testing.assert_allclose(exact[1], 0.0)
    above = hr.marginal_price_change(base, _ref(free=100.01), displacement=1.0)
    assert above[0].all()
    np.testing.assert_allclose(above[1], -1.0)


def test_income_gain_counts_paid_care_saved_and_cash_not_the_funding_value():
    """A4: £4,000 of newly funded hours displace £3,620 (90.5%) of paid care, capped at what the family spends."""
    base = _base(actual_cost=np.array([10_000.0, 2_000.0, 0.0, 8_000.0]))
    ref = _ref(free=4_000.0, gain=500.0)
    displaced = 4_000.0 * config.FREE_HOURS_DISPLACEMENT
    np.testing.assert_allclose(hr.income_gain(base, ref), [500 + displaced, 500 + 2_000, 500, 500 + displaced])
    # The sensitivity counts the funded hours at what the government pays for them.
    np.testing.assert_allclose(hr.income_gain(base, ref, basis="government_cost"), 4_500.0)
    # Two benefit units in one household: the household's saving is both units' savings.
    two = _base(actual_cost=np.array([10_000.0, 10_000.0, 1_000.0, 1_000.0]),
                benunit_id=np.array([1, 1, 2, 2]), household_id=np.array([7, 7, 7, 7]))
    np.testing.assert_allclose(hr.paid_care_saving(two, _ref(free=4_000.0)), displaced + 1_000.0)


def test_income_gain_withdraws_the_top_up_on_the_displaced_spend():
    """A5: the top-up the family no longer gets on care it no longer buys comes off the central gain only."""
    base = _base()
    ref = _ref(free=4_000.0, gain=500.0)
    ref["bu_tfc"] = np.full(4, 1_000.0)
    ref["bu_tfc_displaced"][hr.displacement_key(config.FREE_HOURS_DISPLACEMENT)] = np.full(4, 300.0)
    fixed = hr.income_gain(base, ref, basis="paid_care_fixed_spend")
    np.testing.assert_allclose(hr.income_gain(base, ref), fixed - 700.0)


def _paying_two_earner_couple(year=2027):
    """María's A5 household: £120,000 and £40,000 earners, a three-year-old, £5,000 of paid care."""
    situation = _couple(120_000, year)
    situation["people"]["b"]["employment_income"] = {year: 40_000}
    situation["people"]["b"]["hours_worked"] = {year: 1_950}
    situation["people"]["child"]["childcare_expenses"] = {year: 5_000}
    return situation


def test_income_gain_on_her_household_is_consistent_with_the_displaced_spend():
    """A5: newly funded hours displace £3,289.62 of the £5,000; the reform's top-up on what is left is £342.08, not
    the £1,000 on the full £5,000, so the gain is £3,631.70, not £4,289.62 (now the fixed-spend sensitivity)."""
    base = ls.baseline_side(_corrected(_paying_two_earner_couple(), False), 2027)
    sim = _corrected(_paying_two_earner_couple(), True)
    ref = ls.reform_side(sim, 2027, base)
    assert hr.paid_care_saving(base, ref)[0] == pytest.approx(3_289.62, abs=0.01)
    assert ref["bu_tfc"][0] == pytest.approx(1_000.0)
    assert ref["bu_tfc_displaced"][hr.displacement_key(config.FREE_HOURS_DISPLACEMENT)][0] == pytest.approx(342.08, abs=0.01)
    assert hr.income_gain(base, ref)[0] == pytest.approx(3_631.70, abs=0.01)
    assert hr.income_gain(base, ref, basis="paid_care_fixed_spend")[0] == pytest.approx(4_289.62, abs=0.01)
    # The recompute leaves the simulation's spend as it was.
    assert float(sim.calculate("childcare_expenses", 2027).sum()) == pytest.approx(5_000.0)


def test_disabled_workers_keep_the_hours_response():
    """A2: OBR Table A4 excludes disabled people from participation; Table A3 does not exclude them from hours."""
    from policyengine_uk import Simulation

    situation = _paying_couple(5_000)
    situation["people"]["b"]["dla_sc_category"] = {2027: "MIDDLE"}
    situation["people"]["b"]["is_disabled_for_benefits"] = {2027: True}
    sim = Simulation(situation=situation)
    assert ls.excluded(sim, 2027).tolist() == [False, True, True]
    assert ls.excluded_from_hours(sim, 2027).tolist() == [False, False, True]
    base = {**_base(), "hours_eligible": np.array([True, True, False, False]),
            "eligible": np.array([True, False, False, False])}
    # Adult 1 (over the limit) is outside the participation screen but responds on hours.
    respond, _ = hr.income_change(base, _ref(gain=1_000.0), "over_limit")
    assert respond.tolist() == [False, True, False, False]


def test_implied_entrants_go_to_non_workers_like_the_workers_who_imply_them():
    """A3: workers in cell 1 imply entry for cell 1's non-worker, not cell 2's, whatever the pull."""
    # Records: a cell-1 worker, a cell-1 non-worker, a cell-2 non-worker with a large pull.
    cells = [[1, 1, 1, 0], [1, 1, 1, 0], [2, 2, 2, 0]]
    prep = _prep(pct=[0.2, 0.1, 0.5], elasticity=[0.1] * 3, emp=[40_000, 0, 0], cells=cells)
    prep["entrant_earnings"] = np.array([0.0, 10_000.0, 30_000.0])
    r = ls.participation_response(prep, 1.0)
    assert r["entrants"] == pytest.approx(10 * 0.02)
    assert r["earnings"] == pytest.approx(10 * 0.02 * 10_000)  # all to the cell-1 non-worker
    assert r["allocated_sex_couple_child_quintile"] == pytest.approx(10 * 0.02)
    assert r["allocated_everyone"] == 0 and r["allocated_unallocated"] == 0


def test_a_cell_with_no_responding_non_worker_falls_back_to_a_coarser_cell():
    # A quintile-5 worker whose cell has no non-worker; the same sex, couple and child band has one in quintile 2.
    cells = [[15, 10, 1, 0], [12, 10, 1, 0], [22, 20, 2, 0]]
    prep = _prep(pct=[0.2, 0.1, 0.5], elasticity=[0.1] * 3, emp=[40_000, 0, 0], cells=cells)
    prep["entrant_earnings"] = np.array([0.0, 10_000.0, 30_000.0])
    r = ls.participation_response(prep, 1.0)
    assert r["allocated_sex_couple_child_quintile"] == 0
    assert r["allocated_sex_couple_child"] == pytest.approx(10 * 0.02)
    assert r["earnings"] == pytest.approx(10 * 0.02 * 10_000)
    # No like non-worker at any level but the last: everyone shares it, in proportion to their pull.
    alone = _prep(pct=[0.2, 0.5], elasticity=[0.1] * 2, emp=[40_000, 0], cells=[[1, 1, 1, 0], [2, 2, 2, 0]])
    assert ls.participation_response(alone, 1.0)["allocated_everyone"] == pytest.approx(10 * 0.02)


def test_entry_sensitivities_change_only_the_entry_placed_in_a_coarser_cell():
    """A3: a quintile-5 worker's entry falls back to a quintile-2 non-worker; a quintile-2 worker's stays in its cell.

    ``same_cell_only`` drops the fallen-back entry; ``worker_profile`` gives it the implying worker's hourly wage
    (the profile arrays stand in for the recompute) and leaves the same-cell entry on the non-worker's own profile.
    """
    # Records: q5 worker, q2 worker, q2 non-worker (all one sex/couple/child cell).
    cells = [[15, 10, 1, 0], [12, 10, 1, 0], [12, 10, 1, 0]]
    prep = _prep(pct=[0.2, 0.1, 0.1], elasticity=[0.1] * 3, emp=[90_000, 20_000, 0], cells=cells)
    prep["wage"] = np.array([45.0, 10.0, 0.0])
    central = ls.participation_response(prep, 1.0)
    assert central["allocated_sex_couple_child_quintile"] == pytest.approx(10 * 0.01)
    assert central["allocated_sex_couple_child"] == pytest.approx(10 * 0.02)
    same = ls.participation_response(prep, 1.0, "same_cell_only")
    assert same["entrants"] == pytest.approx(10 * 0.01)
    assert same["allocated_unallocated"] == pytest.approx(10 * 0.02)
    assert same["offset"] == pytest.approx(central["offset"] / 3)
    _, _, fallback = ls.allocate_entrants(np.array([0.02, 0.01, 0.0]), np.array([0.0, 0.0, 0.01]),
                                          np.asarray(cells), np.full(3, 10.0), wage=prep["wage"])
    assert fallback["fallback_enter"][2] == pytest.approx(0.02)
    assert fallback["fallback_wage"][2] == pytest.approx(45.0)  # the quintile-5 worker's wage
    prep.update(profile_earnings=np.full(3, 45.0 * 18.8 * 52), profile_gain=np.full(3, 30_000.0),
                profile_subsidy=np.full(3, 200.0))
    worker = ls.participation_response(prep, 1.0, "worker_profile")
    assert worker["entrants"] == pytest.approx(central["entrants"])
    own = 10 * 0.01 * (18_000 - 15_000 - 200)
    assert worker["offset"] == pytest.approx(own + 10 * 0.02 * (45.0 * 18.8 * 52 - 30_000 - 200))


def _two_earner_couple(year=2027):
    """María's A1 household: a £120,000 and a £99,900 earner, a three-year-old, £5,000 of paid care."""
    situation = _couple(120_000, year)
    situation["people"]["b"]["employment_income"] = {year: 99_900}
    situation["people"]["b"]["hours_worked"] = {year: 1_950}
    situation["people"]["child"]["childcare_expenses"] = {year: 5_000}
    return situation


def _corrected(situation, reform, year=2027):
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    from childcare_100k import corrections

    scenario = Scenario(parameter_changes=config.parameter_changes(config.REFORM_PARAMETERS) if reform else None,
                        simulation_modifier=corrections.apply_corrections, applied_before_data_load=True)
    sim = Simulation(situation=situation, scenario=scenario)
    sim.default_calculation_period = year
    return sim


@pytest.fixture(scope="module")
def two_earner_runs():
    base_sim = _corrected(_two_earner_couple(), False)
    base = ls.baseline_side(base_sim, 2027)
    sim = _corrected(_two_earner_couple(), True)
    return sim, base, ls.reform_side(sim, 2027, base)


def test_hours_offset_is_recomputed_once_on_the_combined_earnings_change(two_earner_runs):
    """A1: the £99,900 parent crosses the personal-allowance taper. Recomputing the price (+£839.16) and income
    changes separately and adding them gave £432.87 for that parent; once, on the combined change, £400.84.
    (Her case uses the funded hours at government cost, the A4 sensitivity.)"""
    sim, base, ref = two_earner_runs
    r = hr.hours_response(sim, 2027, base, ref, 1.0, basis="government_cost")
    below, total = r["at_or_below_limit"], r["total"]
    assert below["price_earnings"] == pytest.approx(839.16, abs=0.01)
    assert below["offset"] == pytest.approx(400.84, abs=0.01)
    assert total["offset"] == pytest.approx(906.29, abs=0.01)
    # The parts are an attribution that adds up to the net exactly.
    for g in (*hr.GROUPS, "total"):
        assert r[g]["price_offset"] + r[g]["income_offset"] == pytest.approx(r[g]["offset"], abs=1e-6)
    # The net is one recompute on everyone's combined change.
    shares = [hr.earnings_shares(base, ref, 1.0, g, basis="government_cost") for g in hr.GROUPS]
    extra = base["employment_income"] * sum(s["price"] + s["income"] for s in shares)
    assert total["offset"] == pytest.approx(extra.sum() - hr._net_income_rise(sim, 2027, extra), abs=1e-6)


def test_hours_response_on_the_paid_care_basis(two_earner_runs):
    """A4 on her household: the gain counts the paid care the funded hours displace (capped at £5,000), not their cost."""
    sim, base, ref = two_earner_runs
    saving = hr.paid_care_saving(base, ref)
    newly_funded = hr.newly_funded_value(base, ref)
    assert saving[0] == pytest.approx(min(newly_funded[0] * config.FREE_HOURS_DISPLACEMENT, 5_000.0))
    paid = hr.income_gain(base, ref, basis="paid_care_fixed_spend")
    cost = hr.income_gain(base, ref, basis="government_cost")
    assert paid[0] == pytest.approx(cost[0] - newly_funded[0] + saving[0], abs=0.1)  # float32 sums
    r = hr.hours_response(sim, 2027, base, ref, 1.0)
    assert r["total"]["price_offset"] + r["total"]["income_offset"] == pytest.approx(r["total"]["offset"], abs=1e-6)
