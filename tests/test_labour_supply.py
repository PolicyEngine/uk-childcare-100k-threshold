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


def _prep(pct, elasticity, emp, eligible=None):
    n = len(pct)
    return {
        "pct": np.asarray(pct, float),
        "elasticity": np.asarray(elasticity, float),
        "reform_gain": np.full(n, 15_000.0),
        "entrant_subsidy": np.full(n, 200.0),
        "eligible": np.ones(n, bool) if eligible is None else np.asarray(eligible, bool),
        "weights": np.full(n, 10.0),
        "employment_income": np.asarray(emp, float),
        "weekly_hours": np.full(n, 30.0),
        "entrant_earnings": np.full(n, 18_000.0),
    }


def test_participation_response_is_the_expected_value():
    prep = _prep(pct=[0.2, 0.2, -0.1], elasticity=[0.1, 0.1, 0.1], emp=[0, 0, 50_000], eligible=[True, False, True])
    r = ls.participation_response(prep, 1.0)
    assert r["entrants"] == pytest.approx(10 * 0.02)
    assert r["leavers"] == pytest.approx(10 * 0.01)
    assert r["offset"] == pytest.approx(10 * 0.02 * (18_000 - 15_000 - 200) - 10 * 0.01 * (50_000 - 15_000))
    assert ls.participation_response(prep, 2.0)["entrants"] == pytest.approx(2 * r["entrants"])


def test_participation_change_is_bounded():
    prep = _prep(pct=[10.0], elasticity=[1.0], emp=[0])
    assert ls.participation_response(prep, 1.0)["entrants"] == pytest.approx(10 * config.PARTICIPATION_CHANGE_BOUND)


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
