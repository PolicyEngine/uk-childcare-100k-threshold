"""The 2029 salary-sacrifice correction to the childcare income tests (corrections.py)."""

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
