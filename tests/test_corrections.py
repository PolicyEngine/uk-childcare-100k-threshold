"""The model corrections (corrections.py): the 2029 salary-sacrifice fix and the three entitlement fixes."""

import pytest

from childcare_100k import corrections


def _situation(year):
    """One parent on £97,000 after £10,000 of pension salary sacrifice, with a two-year-old."""
    return {
        "people": {
            "parent": {
                "age": {year: 35},
                "employment_income_before_lsr": {year: 97_000},
                "pension_contributions_via_salary_sacrifice": {year: 10_000},
            },
            "child": {"age": {year: 2}},
        },
        "benunits": {"bu": {"members": ["parent", "child"]}},
        "households": {
            "hh": {"members": ["parent", "child"], "region": {year: "SOUTH_EAST"}}
        },
    }


def _sim(year, corrected):
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    kwargs = (
        {
            "scenario": Scenario(
                simulation_modifier=corrections.apply_corrections,
                applied_before_data_load=True,
            )
        }
        if corrected
        else {}
    )
    return Simulation(situation=_situation(year), **kwargs)


def _value(sim, variable, year):
    return sim.calculate(variable, year)[0]


def test_income_tests_ignore_salary_sacrifice_returned_to_pay_in_2029():
    uncorrected, corrected = _sim(2029, False), _sim(2029, True)
    assert _value(
        corrected, "salary_sacrifice_returned_to_income", 2029
    ) == pytest.approx(8_000)
    # The model's own adjusted net income crosses £100,000 and fails both tests...
    assert _value(uncorrected, "adjusted_net_income", 2029) > 100_000
    assert not _value(uncorrected, corrections.THIRTY_HOURS_INCOME_TEST, 2029)
    assert not _value(uncorrected, corrections.TFC_INCOME_TEST, 2029)
    # ...the corrected tests pass, and nothing else moves.
    assert _value(corrected, corrections.THIRTY_HOURS_INCOME_TEST, 2029)
    assert _value(corrected, corrections.TFC_INCOME_TEST, 2029)
    for variable in ("adjusted_net_income", "income_tax", "ni_employee"):
        assert _value(corrected, variable, 2029) == pytest.approx(
            _value(uncorrected, variable, 2029)
        )


def test_correction_is_a_no_op_before_the_cap():
    uncorrected, corrected = _sim(2028, False), _sim(2028, True)
    for variable in (
        corrections.THIRTY_HOURS_INCOME_TEST,
        corrections.TFC_INCOME_TEST,
        "income_tax",
    ):
        assert _value(corrected, variable, 2028) == _value(uncorrected, variable, 2028)


def test_correction_refuses_a_changed_model_formula(monkeypatch):
    monkeypatch.setitem(
        corrections.EXPECTED_FORMULA_SHA256, corrections.TFC_INCOME_TEST, "0" * 64
    )
    from policyengine_uk import CountryTaxBenefitSystem

    with pytest.raises(RuntimeError, match="changed upstream"):
        corrections.apply_to_system(CountryTaxBenefitSystem())


# ── Entitlement corrections (C1-C3 of the program review of #4) ─────────────────

Y = 2027


def _family(a_income, b_income, child_age, usage=30, b_extra=None, reform=False, corrected=True):
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    from childcare_100k import config

    people = {
        "a": {"age": {Y: 35}, "employment_income": {Y: a_income}, "is_parent": {Y: True}},
        "b": {"age": {Y: 34}, "employment_income": {Y: b_income}, "is_parent": {Y: True}, **(b_extra or {})},
        "c": {"age": {Y: child_age}},
    }
    situation = {
        "people": people,
        "benunits": {"bu": {"members": list(people), "maximum_extended_childcare_hours_usage": {Y: usage}}},
        "households": {"hh": {"members": list(people), "region": {Y: "SOUTH_EAST"}}},
    }
    scenario = Scenario(
        parameter_changes=config.parameter_changes(config.REFORM_PARAMETERS) if reform else None,
        simulation_modifier=corrections.apply_corrections if corrected else None,
        applied_before_data_load=True,
    )
    return Simulation(situation=situation, scenario=scenario)


def _funded(sim):
    return {
        v: float(sim.calculate(f"{v}_childcare_entitlement", Y).sum())
        for v in ("extended", "universal", "targeted")
    }


def test_exactly_100000_qualifies_for_the_30_hours():
    """C3: reg 14(3)(c)(i) excludes only income that exceeds £100,000."""
    assert _funded(_family(100_000, 40_000, 2))["extended"] > 0
    assert _funded(_family(100_000, 40_000, 2, corrected=False))["extended"] == 0
    assert _funded(_family(100_001, 40_000, 2))["extended"] == 0


def test_partner_on_a_specified_benefit_does_not_need_the_minimum_earnings():
    """C1: reg 14(4)/15(4); a partner on contributory ESA earning £5,000 alongside a £120,000 earner."""
    esa = {"esa_contrib_reported": {Y: 5_000}}
    assert _funded(_family(120_000, 5_000, 2, b_extra=esa))["extended"] == 0  # over the limit today
    assert _funded(_family(120_000, 5_000, 2, b_extra=esa, reform=True))["extended"] > 0
    assert _funded(_family(120_000, 5_000, 2, b_extra=esa, reform=True, corrected=False))["extended"] == 0
    # Without the benefit the low earner still fails the minimum earnings test.
    assert _funded(_family(120_000, 5_000, 2, reform=True))["extended"] == 0


def test_universal_hours_are_kept_when_the_family_becomes_eligible():
    """C2: a three-year-old whose drawn extended use is 5 hours keeps the universal 15."""
    base, reform = _family(120_000, 40_000, 3, usage=5), _family(120_000, 40_000, 3, usage=5, reform=True)
    assert sum(_funded(reform).values()) == pytest.approx(sum(_funded(base).values()))
    assert _funded(reform)["universal"] == pytest.approx(_funded(base)["universal"])
    raw = _family(120_000, 40_000, 3, usage=5, reform=True, corrected=False)
    assert sum(_funded(raw).values()) < sum(_funded(base).values())  # the model's own loss


def test_extended_hours_above_the_universal_are_added_once():
    """C2: with 30 hours used, a three-year-old gets 30 hours in total, not 45."""
    reform = _funded(_family(120_000, 40_000, 3, usage=30, reform=True))
    raw = _funded(_family(120_000, 40_000, 3, usage=30, reform=True, corrected=False))
    assert reform["universal"] > 0
    assert sum(reform.values()) == pytest.approx(sum(raw.values()))
