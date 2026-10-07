"""The labour supply response (labour_supply.py, hours_response.py).

The arithmetic tests run on hand-built arrays. The gain-to-work tests run policyengine-uk on
hand-built households, so none of these needs the Microcosm release.
"""

import numpy as np
import pytest

from childcare_100k import config
from childcare_100k import labour_supply as ls
from childcare_100k.hours_response import out_of_pocket_prices, price_change


def _base(**overrides):
    n = 4
    base = {
        "actual_cost": np.array([10_000.0, 10_000.0, 0.0, 8_000.0]),
        "bu_tfc": np.zeros(n),
        "bu_free": np.zeros(n),
        "employment_income": np.array([40_000.0, 120_000.0, 30_000.0, 0.0]),
        "weekly_hours": np.array([30.0, 40.0, 30.0, 0.0]),
        "eligible": np.ones(n, bool),
        "over_limit": np.array([False, True, False, False]),
        "weights": np.ones(n),
    }
    base.update(overrides)
    return base


def test_out_of_pocket_price_displaces_free_hours_and_applies_tfc_to_the_rest():
    base = _base()
    ref = {"bu_tfc": np.array([2_000.0, 2_000.0, 0.0, 0.0]), "bu_free": np.array([4_000.0, 4_000.0, 0.0, 0.0])}
    before, after = out_of_pocket_prices(base, ref)
    np.testing.assert_allclose(before, [10_000, 10_000, 0, 8_000])
    remaining = 10_000 - 4_000 * config.FREE_HOURS_DISPLACEMENT
    np.testing.assert_allclose(after[:2], remaining * (1 - 0.2))
    # Newly free hours never take the price below zero.
    big = {"bu_tfc": np.zeros(4), "bu_free": np.full(4, 50_000.0)}
    assert (out_of_pocket_prices(base, big)[1] >= 0).all()


def test_price_change_splits_the_parent_over_the_limit_from_everyone_else():
    base = _base()
    ref = {"bu_tfc": np.array([2_000.0, 2_000.0, 0.0, 1_000.0]), "bu_free": np.zeros(4)}
    respond, change = price_change(base, ref, "at_or_below_limit")
    # Only the worker at or below the limit who pays for childcare responds.
    assert respond.tolist() == [True, False, False, False]
    assert change[0] == pytest.approx(-0.2)
    respond, change = price_change(base, ref, "over_limit")
    assert respond.tolist() == [False, True, False, False]


def _prep(pct, elasticity, emp, eligible=None, over_limit=None):
    n = len(pct)
    return {
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
        "entrant_earnings": np.zeros(n),
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
