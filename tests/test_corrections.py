"""The model corrections and toggles (corrections.py) on policyengine-uk 2.134.4: the 2029 salary-sacrifice fix (C4),
Tax-Free Childcare's claimant-and-partner income gate (C6), the dropped corrections now upstream, and the toggles."""

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


# ── Corrections dropped because policyengine-uk 2.134.4 handles them (C1-C3, C5, C6 30-hours half) ──────

Y = 2027


def _family(a_income, b_income, child_age, usage=30, b_extra=None, reform=False, toggles=(), extra=None):
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    from childcare_100k import config

    people = {
        "a": {"age": {Y: 35}, "employment_income": {Y: a_income}, "is_parent": {Y: True}},
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
        simulation_modifier=corrections.modifier(toggles, years=config.YEARS),
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
    """C6, kept: tax_free_childcare_eligible tests is_parent in 2.134.4, so an unflagged partner over £100,000 passed."""
    rich = {**UNFLAGGED, "savings_interest_income": {Y: 110_000}}
    assert _tfc(_tfc_family(rich, a_income=40_000, b_income=20_000, reform=False, corrected=False)) == pytest.approx(2_000)
    assert _tfc(_tfc_family(rich, a_income=40_000, b_income=20_000, reform=False)) == 0
    assert _tfc(_tfc_family(rich, a_income=40_000, b_income=20_000)) == pytest.approx(2_000)


# ── Toggles ──────────────────────────────────────────────────────────────────────


def test_reception_toggle_removes_a_reception_childs_funded_hours():
    reception = {"current_education": {Y: "PRIMARY"}}
    shipped = _funded(_family(40_000, 40_000, 4, extra=reception))
    toggled = _funded(_family(40_000, 40_000, 4, extra=reception, toggles=["reception"]))
    assert shipped["universal"] > 0 and shipped["extended"] > 0
    assert sum(toggled.values()) == 0
    # A 4-year-old not in reception keeps them.
    assert _funded(_family(40_000, 40_000, 4, toggles=["reception"])) == pytest.approx(
        _funded(_family(40_000, 40_000, 4)))


def test_dfe_rates_toggle_sets_dfe_2026_rates_uprated_by_the_model():
    from policyengine_uk import CountryTaxBenefitSystem

    system = CountryTaxBenefitSystem()
    rate = system.parameters.gov.dfe.childcare_funding_rate
    model = [[b.amount(f"{y}-01-01") for b in rate.brackets] for y in (2026, 2029)]
    corrections.apply_to_system(system, ["dfe_rates"], years=[2025, 2026, 2029])
    assert [b.amount("2026-01-01") for b in rate.brackets] == pytest.approx(list(corrections.DFE_RATES_2026))
    assert [b.amount("2029-06-01") for b in rate.brackets] == pytest.approx(
        [d * m29 / m26 for d, m26, m29 in zip(corrections.DFE_RATES_2026, model[0], model[1])])
    # 2025-26 is left at the model's rate.
    assert rate.brackets[0].amount("2025-01-01") < corrections.DFE_RATES_2026[0]


def test_pension_toggle_tests_ani_after_pension_contributions():
    """£105,000 earner paying £10,000 into a personal pension: over the limit on the model's ANI, under it in law."""
    pension = {"personal_pension_contributions": {Y: 10_000}}

    def eligible(toggles):
        from policyengine_uk import Simulation
        from policyengine_uk.utils.scenario import Scenario

        people = {"a": {"age": {Y: 35}, "employment_income": {Y: 105_000}, **pension}, "c": {"age": {Y: 2}}}
        situation = {"people": people, "benunits": {"bu": {"members": list(people)}},
                     "households": {"hh": {"members": list(people), "region": {Y: "SOUTH_EAST"}}}}
        sim = Simulation(situation=situation, scenario=Scenario(
            simulation_modifier=corrections.modifier(toggles), applied_before_data_load=True))
        return bool(sim.calculate(corrections.THIRTY_HOURS_INCOME_TEST, Y)[0])

    assert not eligible([])
    assert eligible(["pension_in_ani"])
