"""The model correction (corrections.py) on policyengine-uk 2.147.2: Tax-Free Childcare's claimant-and-partner income
gate (C6), and the corrections and toggles dropped because the engine now handles them, each kept as a regression test."""

import pytest

from childcare_100k import corrections


def test_correction_refuses_a_changed_model_formula(monkeypatch):
    monkeypatch.setitem(corrections.EXPECTED_FORMULA_SHA256, corrections.TFC_ELIGIBLE, "0" * 64)
    from policyengine_uk import CountryTaxBenefitSystem

    with pytest.raises(RuntimeError, match="changed upstream"):
        corrections.apply_to_system(CountryTaxBenefitSystem())


# ── Corrections dropped because policyengine-uk 2.147.2 handles them ──────────────────────────────────

Y = 2027


def _family(a_income, b_income, child_age, usage=30, b_extra=None, reform=False, extra=None, a_extra=None):
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    from childcare_100k import config

    people = {
        "a": {"age": {Y: 35}, "employment_income": {Y: a_income}, "is_parent": {Y: True}, **(a_extra or {})},
        "b": {"age": {Y: 34}, "employment_income": {Y: b_income}, "is_parent": {Y: True}, **(b_extra or {})},
        "c": {"age": {Y: child_age}, **(extra or {})},
    }
    situation = {
        "people": people,
        "benunits": {"bu": {"members": list(people), "maximum_extended_childcare_hours_usage": {Y: usage}}},
        "households": {"hh": {"members": list(people), "region": {Y: "SOUTH_EAST"}}},
    }
    scenario = Scenario(
        parameter_changes=config.parameter_changes(config.REFORM_PARAMETERS) if reform else None,
        simulation_modifier=corrections.apply_corrections,
        applied_before_data_load=True,
    )
    return Simulation(situation=situation, scenario=scenario)


def _funded(sim):
    return {
        v: float(sim.calculate(f"{v}_childcare_entitlement", Y).sum())
        for v in ("extended", "universal", "targeted")
    }


def test_upstream_exactly_100000_qualifies_for_the_30_hours():
    """C3, upstream: reg 14(3)(c)(i) excludes only income that exceeds £100,000."""
    assert _funded(_family(100_000, 40_000, 2))["extended"] > 0
    assert _funded(_family(100_001, 40_000, 2))["extended"] == 0


def test_upstream_partner_on_a_specified_benefit_does_not_need_the_minimum_earnings():
    """C1, upstream: reg 14(4)/15(4); a partner on contributory ESA earning £5,000 alongside a £120,000 earner."""
    esa = {"esa_contrib_reported": {Y: 5_000}}
    assert _funded(_family(120_000, 5_000, 2, b_extra=esa))["extended"] == 0
    assert _funded(_family(120_000, 5_000, 2, b_extra=esa, reform=True))["extended"] > 0
    assert _funded(_family(120_000, 5_000, 2, reform=True))["extended"] == 0


def test_upstream_universal_hours_are_kept_and_added_once():
    """C2, upstream: a three-year-old drawing 5 hours keeps the universal 15; drawing 30, gets 30 in total, not 45."""
    base, reform = _family(120_000, 40_000, 3, usage=5), _family(120_000, 40_000, 3, usage=5, reform=True)
    assert sum(_funded(reform).values()) == pytest.approx(sum(_funded(base).values()))
    full = _funded(_family(120_000, 40_000, 3, usage=30, reform=True))
    below = _funded(_family(40_000, 40_000, 3, usage=30))
    assert full["universal"] > 0
    assert sum(full.values()) == pytest.approx(sum(below.values()))


# ── Tax-Free Childcare ───────────────────────────────────────────────────────────


def _tfc_family(b_extra, a_income=120_000, b_income=0, reform=True, corrected=True, couple=True):
    """A 2027 England family: a £120,000 earner, a partner with ``b_extra``, a three-year-old in £10,000 of paid care."""
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    from childcare_100k import config

    people = {"a": {"age": {Y: 35}, "employment_income": {Y: a_income}, "is_parent": {Y: True}}}
    if couple:
        people["b"] = {"age": {Y: 34}, "employment_income": {Y: b_income}, "is_parent": {Y: True}, **b_extra}
    people["c"] = {"age": {Y: 3}, "childcare_expenses": {Y: 10_000}}
    situation = {
        "people": people,
        "benunits": {"bu": {"members": list(people), "would_claim_tfc": {Y: True},
                            "would_claim_extended_childcare": {Y: True},
                            "maximum_extended_childcare_hours_usage": {Y: 30}}},
        "households": {"hh": {"members": list(people), "region": {Y: "SOUTH_EAST"}}},
    }
    scenario = Scenario(
        parameter_changes=config.parameter_changes(config.REFORM_PARAMETERS) if reform else None,
        simulation_modifier=corrections.apply_corrections if corrected else None,
        applied_before_data_load=True,
    )
    return Simulation(situation=situation, scenario=scenario)


def _tfc(sim):
    return float(sim.calculate("tax_free_childcare", Y).sum())


ESA = {"esa_contrib_reported": {Y: 5_000}}
CARERS_ALLOWANCE = {"carers_allowance": {Y: 4_000}}
UNFLAGGED = {"is_parent": {Y: False}}


@pytest.mark.parametrize("benefit", [ESA, CARERS_ALLOWANCE], ids=["contributory ESA", "carer's allowance"])
def test_upstream_reg_13_partner_is_regarded_as_in_paid_work(benefit):
    """C5, upstream: SI 2015/448 reg 13(1)-(2); the reform pays the £2,000 cap on £10,000 of care."""
    assert _tfc(_tfc_family(benefit, reform=False)) == 0
    assert _tfc(_tfc_family(benefit)) == pytest.approx(2_000)
    assert _tfc(_tfc_family(benefit, corrected=False)) == pytest.approx(2_000)


def test_upstream_unflagged_nonworking_partner_fails_the_work_condition():
    """C6 work condition, upstream: Tax-Free Childcare and the 30 hours test the claimant and partner."""
    assert _tfc(_tfc_family(UNFLAGGED, corrected=False)) == 0
    assert _funded(_tfc_family(UNFLAGGED))["extended"] == 0
    assert _tfc(_tfc_family(UNFLAGGED, b_income=20_000)) == pytest.approx(2_000)


def test_unflagged_partner_faces_the_tfc_income_limit():
    """C6, kept: tax_free_childcare_eligible tests is_parent in 2.147.2, so an unflagged partner over £100,000 passed."""
    rich = {**UNFLAGGED, "savings_interest_income": {Y: 110_000}}
    assert _tfc(_tfc_family(rich, a_income=40_000, b_income=20_000, reform=False, corrected=False)) == pytest.approx(2_000)
    assert _tfc(_tfc_family(rich, a_income=40_000, b_income=20_000, reform=False)) == 0
    assert _tfc(_tfc_family(rich, a_income=40_000, b_income=20_000)) == pytest.approx(2_000)


# ── Toggles dropped because policyengine-uk 2.147.2 handles them ─────────────────────────────────────────────


def test_upstream_salary_sacrifice_over_the_2029_cap_leaves_income_tests_alone():
    """C4, upstream (policyengine-uk#2462): £97,000 after £10,000 of salary sacrifice stays under £100,000 in 2029."""
    from policyengine_uk import Simulation

    year = 2029
    situation = {
        "people": {
            "parent": {"age": {year: 35}, "employment_income_before_lsr": {year: 97_000},
                       "pension_contributions_via_salary_sacrifice": {year: 10_000}},
            "child": {"age": {year: 2}},
        },
        "benunits": {"bu": {"members": ["parent", "child"]}},
        "households": {"hh": {"members": ["parent", "child"], "region": {year: "SOUTH_EAST"}}},
    }
    sim = Simulation(situation=situation)
    assert sim.calculate("salary_sacrifice_returned_to_income", year)[0] == 0
    assert sim.calculate("adjusted_net_income", year)[0] <= 100_000
    assert sim.calculate("extended_childcare_entitlement_meets_income_requirements", year)[0]
    assert sim.calculate("tax_free_childcare_meets_income_requirements", year)[0]


def test_upstream_ani_is_after_pension_contributions():
    """Pension toggle, upstream (policyengine-uk#2440): £105,000 less £10,000 into a personal pension qualifies."""
    pension = {"personal_pension_contributions": {Y: 10_000}}
    assert _funded(_family(105_000, 40_000, 2, a_extra=pension))["extended"] > 0
    assert _funded(_family(105_000, 40_000, 2))["extended"] == 0


def test_upstream_funding_rates_are_dfe_2026_27_rates():
    """DfE-rate toggle, upstream (policyengine-uk#2465): DfE's 2026-27 national average rates."""
    from policyengine_uk import CountryTaxBenefitSystem

    rate = CountryTaxBenefitSystem().parameters("2026-06-01").gov.dfe.childcare_funding_rate
    assert [round(float(rate.calc(a)), 2) for a in (0, 2, 3)] == [12.04, 8.90, 6.61]


def _young(age, months, reform=False):
    """A £120,000 earner's child (the reform makes the family eligible) aged ``age`` and ``months`` on 6 October."""
    return _family(120_000, 40_000, age, reform=reform, extra={"months_since_last_birthday": {Y: months}})


def test_upstream_reception_children_keep_only_the_summer_term():
    """Reception toggle, upstream (policyengine-uk#2570): a 4-year-old who started school in September keeps one term."""
    started = _funded(_young(4, 6))  # born April: reception from September
    assert started["universal"] == pytest.approx(15 * 38 * 6.762 / 3, rel=0.01)


def test_upstream_children_under_one_are_funded_from_the_term_after_nine_months():
    """Under-1s adjustment, upstream (policyengine-uk#2570): a child aged 0 who is 9 months by 1 January is funded
    for the spring term under the reform; a newborn is not."""
    assert _funded(_young(0, 8))["extended"] == 0
    funded = _funded(_young(0, 8, reform=True))["extended"]
    assert funded == pytest.approx(30 * 38 * 12.317 / 3, rel=0.01)
    assert _funded(_young(0, 0, reform=True))["extended"] == 0
