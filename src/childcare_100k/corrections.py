"""Model corrections applied to every run, baseline and reform alike.

The childcare income tests exclude salary sacrifice returned to pay (from 6 April 2029)
-----------------------------------------------------------------------------------------
From 6 April 2029, pension contributions made through salary sacrifice above
£2,000 a year are subject to Class 1 National Insurance. HMRC's policy paper says
the measure changes National Insurance only and does not change salary
sacrifice's effect on adjusted net income, naming Tax-Free Childcare among the
schemes unaffected:
https://www.gov.uk/government/publications/salary-sacrifice-reform-for-pension-contributions-effective-from-6-april-2029/salary-sacrifice-reform-for-pension-contributions

policyengine-uk 2.102.3 models the cap by adding the excess above £2,000
(``salary_sacrifice_returned_to_income``) to ``employment_income``, so it flows
into ``adjusted_net_income``. That pushes some parents below £100,000 over the
limit in 2029-30.

The correction is deliberately narrow. Both childcare income tests (the 30 funded
hours for working parents and Tax-Free Childcare) compare adjusted net income
less ``salary_sacrifice_returned_to_income`` with the limit. ``adjusted_net_income``
itself is left alone. The model derives taxable income from it and also deducts
the returned amount as pension relief, so correcting it there would deduct the
amount twice and understate income tax. The minimum-income tests are unchanged.

Each replacement reproduces the model's formula with only the income measure
changed. The model's formulas are fingerprinted: if policyengine-uk changes
either one, the correction refuses to apply, rather than silently replacing new
logic with old. The correction is a no-op before 2029-30, while the cap is unset.
It is pending an upstream fix in policyengine-uk.
"""

import hashlib
import inspect

from policyengine_uk.model_api import add

RETURNED_SALARY_SACRIFICE = "salary_sacrifice_returned_to_income"
THIRTY_HOURS_INCOME_TEST = "extended_childcare_entitlement_meets_income_requirements"
TFC_INCOME_TEST = "tax_free_childcare_meets_income_requirements"
# sha256 of inspect.getsource() of each model formula this module replaces (policyengine-uk 2.102.3).
EXPECTED_FORMULA_SHA256 = {
    THIRTY_HOURS_INCOME_TEST: "8ae8e181373d300974d7bdf434ea7e4ceeaf47a4c3a0e986a01a46d35e8ecfff",
    TFC_INCOME_TEST: "db72ceccc92a7f7c8bece286610df6fe63afe1b8f3d91353867650523310da6d",
}
MARK = "_childcare_100k_income_test_excludes_returned_salary_sacrifice"


def income_for_limit(person, period):
    """Adjusted net income as the childcare limits test it: less salary sacrifice returned to pay."""
    return person("adjusted_net_income", period) - person(
        RETURNED_SALARY_SACRIFICE, period
    )


def thirty_hours_income_test(person, period, parameters):
    """policyengine-uk's formula with ``income_for_limit`` in place of adjusted net income."""
    p = parameters(period).gov.dfe.extended_childcare_entitlement
    yearly_eligible_income = add(person, period, p.income.countable_sources)
    quarterly_income = yearly_eligible_income / 4
    min_wage_rate = person("minimum_wage", period)
    required_threshold = min_wage_rate * p.minimum_weekly_hours * 13
    return (quarterly_income > required_threshold) & (
        income_for_limit(person, period) < p.income.limit
    )


def tfc_income_test(person, period, parameters):
    """policyengine-uk's formula with ``income_for_limit`` in place of adjusted net income."""
    p = parameters(period).gov.hmrc.tax_free_childcare
    expected_income = person(
        "tax_free_childcare_expected_declaration_period_income", period
    )
    min_wage_rate = person("minimum_wage", period)
    required_threshold = (
        min_wage_rate * p.minimum_weekly_hours * p.income.declaration_period_weeks
    )
    meets_minimum_income = expected_income >= required_threshold
    in_start_up_period = person(
        "tax_free_childcare_self_employment_start_up_period", period
    )
    return (meets_minimum_income | in_start_up_period) & (
        income_for_limit(person, period) <= p.income.income_limit
    )


REPLACEMENTS = {
    THIRTY_HOURS_INCOME_TEST: thirty_hours_income_test,
    TFC_INCOME_TEST: tfc_income_test,
}


def apply_to_system(tax_benefit_system):
    for name, replacement in REPLACEMENTS.items():
        variable = tax_benefit_system.variables[name]
        if getattr(variable, MARK, False):
            raise RuntimeError(
                f"{name} has already been corrected in this tax-benefit system"
            )
        if list(variable.formulas) != ["0001-01-01"]:
            raise RuntimeError(
                f"{name}: formula dates changed upstream ({list(variable.formulas)}); review the correction"
            )
        source = inspect.getsource(variable.formulas["0001-01-01"])
        digest = hashlib.sha256(source.encode()).hexdigest()
        if digest != EXPECTED_FORMULA_SHA256[name]:
            raise RuntimeError(
                f"{name}: the model's formula changed upstream (sha256 {digest}); review the correction"
            )
        variable.formulas["0001-01-01"] = replacement
        setattr(variable, MARK, True)


def is_applied(tax_benefit_system):
    return all(
        getattr(tax_benefit_system.variables[n], MARK, False) for n in REPLACEMENTS
    )


def apply_corrections(simulation):
    """Scenario modifier: apply every correction to a simulation's tax-benefit system."""
    apply_to_system(simulation.tax_benefit_system)
