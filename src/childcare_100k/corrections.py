"""Model corrections applied to every run, baseline and reform alike.

Four corrections, each pending an upstream fix in policyengine-uk (2.102.3 is the
certified version; policyengine-uk#2079, merged after it, fixes the first two):

1. Exactly £100,000 qualifies for the 30 hours (C3).
2. A partner with a specified benefit need not pass the minimum earnings test (C1).
3. The universal and targeted 15 hours survive eligibility for the extended hours (C2).
4. Salary sacrifice returned to pay from April 2029 is not income for the limits.

1. Exactly £100,000 qualifies for the 30 hours
-----------------------------------------------
SI 2022/1134 reg 14(3)(c)(i) and 15(3)(b)(i) exclude a parent or partner who
expects adjusted net income to *exceed* £100,000. policyengine-uk tests
``adjusted_net_income < limit``, so exactly £100,000 loses the 30 hours. The
replacement tests ``<=``, as Tax-Free Childcare already does.

2. A partner on a specified benefit (reg 14(4) and 15(4))
--------------------------------------------------------
SI 2022/1134 reg 14(4) and 15(4) let a parent or partner who has limited
capability for work or is entitled to a specified benefit (reg 11A: carer's
allowance, the Universal Credit carer element, employment and support allowance,
incapacity benefit, severe disablement allowance, and NI credits for incapacity)
meet the parent conditions without the work or income conditions, when the other
member of the couple meets reg 14(3)/15(3). policyengine-uk's work condition
already accepts such a couple, but ``extended_childcare_entitlement_eligible``
also requires every adult to pass the minimum earnings test, so the route never
applies. The replacement exempts from the income test an adult who is:

- paid any of the model's own person-level ``disability_criteria`` (carer's
  allowance, contributory ESA, incapacity benefit, severe disablement allowance);
- the carer (``is_carer_for_benefits``) in a family whose Universal Credit award
  includes the carer element;
- not in work, in a family receiving income-related ESA.

Not mapped: limited capability for work itself (policyengine-uk's
``uc_limited_capability_for_WRA`` is a proxy equal to receiving PIP or DLA,
which is not the reg 39/40 Universal Credit determination, and the model's own
work condition does not accept it either) and NI credits (not in the data). The
working parent still faces the full test, and the work condition still needs one
parent in work, so a lone parent cannot qualify this way.

3. The universal and targeted 15 hours are a floor
--------------------------------------------------
policyengine-uk switches a child's universal (3-4) and targeted (2) entitlements
off whenever the family is eligible for the extended entitlement, and values the
extended entitlement at the family's drawn weekly usage
(``maximum_extended_childcare_hours_usage``, 0-30), which can be under 15. A
family that becomes eligible can then lose funded hours (policyengine-uk#1930).
In law the working-parent hours for a 3- or 4-year-old come on top of the
universal 15 hours, and qualifying never removes them. For 3- and 4-year-olds
policyengine-uk's extended hours (30) are the whole entitlement, universal
included, so the replacements keep the universal and targeted entitlements in
every family and count as extended only each child's funded hours *above* them:

    extended (each child) = max(0, extended hours x rate x weeks - universal - targeted)

so a child's total funded hours are max(universal or targeted, extended), never
both added in full (no double counting) and never less than the floor.

4. The childcare income tests exclude salary sacrifice returned to pay (from 6 April 2029)
------------------------------------------------------------------------------------------ exclude salary sacrifice returned to pay (from 6 April 2029)
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

It is a no-op before 2029-30, while the cap is unset.

Each replacement reproduces the model's formula with only the stated change. The
model's formulas are fingerprinted: if policyengine-uk changes any of them, the
correction refuses to apply, rather than silently replacing new logic with old.
"""

import hashlib
import inspect
from contextlib import contextmanager

import numpy as np
from policyengine_uk.model_api import add

RETURNED_SALARY_SACRIFICE = "salary_sacrifice_returned_to_income"
THIRTY_HOURS_INCOME_TEST = "extended_childcare_entitlement_meets_income_requirements"
TFC_INCOME_TEST = "tax_free_childcare_meets_income_requirements"
THIRTY_HOURS_ELIGIBLE = "extended_childcare_entitlement_eligible"
THIRTY_HOURS_VALUE = "extended_childcare_entitlement"
UNIVERSAL_ELIGIBLE = "universal_childcare_entitlement_eligible"
TARGETED_ELIGIBLE = "targeted_childcare_entitlement_eligible"
# sha256 of inspect.getsource() of each model formula this module replaces (policyengine-uk 2.102.3).
EXPECTED_FORMULA_SHA256 = {
    THIRTY_HOURS_INCOME_TEST: "8ae8e181373d300974d7bdf434ea7e4ceeaf47a4c3a0e986a01a46d35e8ecfff",
    TFC_INCOME_TEST: "db72ceccc92a7f7c8bece286610df6fe63afe1b8f3d91353867650523310da6d",
    THIRTY_HOURS_ELIGIBLE: "1be9225945c80e49d79e277bb14c596ef37e0330a25a7345950731d10799113c",
    THIRTY_HOURS_VALUE: "4f7fa84421f58cd67d27c6610aee3d1c532c0d4b780a1cf76519f820f98666a8",
    UNIVERSAL_ELIGIBLE: "322527b7a86eea6e066574f2126f6ad7f47af6caeb7aab7ab64968ab4e6758c5",
    TARGETED_ELIGIBLE: "d4a98f6ca5d5a82eb92e2c3f9796f9a76b8952b1bb5834409a30b6a5f160a88a",
}
MARK = "_childcare_100k_corrected"


def income_for_limit(person, period):
    """Adjusted net income as the childcare limits test it: less salary sacrifice returned to pay."""
    return person("adjusted_net_income", period) - person(
        RETURNED_SALARY_SACRIFICE, period
    )


def thirty_hours_income_test(person, period, parameters):
    """policyengine-uk's formula with ``income_for_limit`` in place of ANI, and ``<=`` the limit (reg 14(3)(c)(i))."""
    p = parameters(period).gov.dfe.extended_childcare_entitlement
    yearly_eligible_income = add(person, period, p.income.countable_sources)
    quarterly_income = yearly_eligible_income / 4
    min_wage_rate = person("minimum_wage", period)
    required_threshold = min_wage_rate * p.minimum_weekly_hours * 13
    return (quarterly_income > required_threshold) & (
        income_for_limit(person, period) <= p.income.limit
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


def specified_benefit_exempt(person, period, parameters):
    """An adult who meets reg 14(4)/15(4) through a specified benefit (module docstring, section 2)."""
    p = parameters(period).gov.dfe.extended_childcare_entitlement
    person_criteria = [
        v for v in p.disability_criteria if person.entity.get_variable(v).entity.is_person
    ]
    on_person_benefit = (
        add(person, period, person_criteria) > 0
        if person_criteria
        else np.zeros(person.count, dtype=bool)
    )
    benunit = person.benunit
    uc_carer = (
        person("is_carer_for_benefits", period)
        & (benunit("universal_credit", period) > 0)
        & (benunit("uc_carer_element", period) > 0)
    )
    income_esa = (benunit("esa_income", period) > 0) & ~person("in_work", period)
    return on_person_benefit | uc_carer | income_esa


def thirty_hours_eligible(benunit, period, parameters):
    """policyengine-uk's formula, with an adult on a specified benefit exempt from the income test (reg 14(4), 15(4))."""
    country = benunit.household("country", period)
    countries = country.possible_values
    in_england = country == countries.ENGLAND
    person = benunit.members
    person_meets_income_condition = (
        person("extended_childcare_entitlement_meets_income_requirements", period)
        | person("is_child", period)
        | specified_benefit_exempt(person, period, parameters)
    )
    meets_income_condition = benunit.all(person_meets_income_condition)
    work_eligible = (
        benunit("extended_childcare_entitlement_work_condition", period) > 0
    )
    return in_england & meets_income_condition & work_eligible


def thirty_hours_value(benunit, period, parameters):
    """policyengine-uk's formula, counting only each child's funded hours above the universal and targeted hours."""
    p = parameters(period).gov.dfe
    person = benunit.members
    age = person("age", period)
    weekly_hours_per_child = p.extended_childcare_entitlement.hours.calc(age)
    max_hours_used = person("max_free_entitlement_hours_used", period)
    weekly_hours_to_use = np.minimum(max_hours_used, weekly_hours_per_child)
    maximum_hours_usage = benunit("maximum_extended_childcare_hours_usage", period)
    weekly_hours_to_use = np.minimum(
        weekly_hours_to_use, benunit.project(maximum_hours_usage)
    )
    full_value = weekly_hours_to_use * p.childcare_funding_rate.calc(age) * p.weeks_per_year
    floor = person("universal_childcare_entitlement", period) + person(
        "targeted_childcare_entitlement", period
    )
    return benunit.sum(np.maximum(full_value - floor, 0))


def universal_eligible(person, period, parameters):
    """policyengine-uk's formula without the switch-off for families eligible for the extended hours."""
    country = person.household("country", period)
    countries = country.possible_values
    in_england = country == countries.ENGLAND
    age = person("age", period)
    p = parameters(period).gov.dfe.universal_childcare_entitlement
    meets_age_condition = (age >= p.age.min) & (age < p.age.max)
    not_compulsory_age = ~person("is_of_compulsory_school_age", period)
    return in_england & meets_age_condition & not_compulsory_age


def targeted_eligible(benunit, period, parameters):
    """policyengine-uk's formula without the switch-off for families eligible for the extended hours."""
    country = benunit.household("country", period)
    in_england = country == country.possible_values.ENGLAND
    p = parameters(period).gov.dfe.targeted_childcare_entitlement
    has_qualifying_benefits = add(benunit, period, p.qualifying_benefits) > 0
    meets_any_criteria = add(benunit, period, p.qualifying_criteria) > 0
    return in_england & (has_qualifying_benefits | meets_any_criteria)


REPLACEMENTS = {
    THIRTY_HOURS_INCOME_TEST: thirty_hours_income_test,
    TFC_INCOME_TEST: tfc_income_test,
    THIRTY_HOURS_ELIGIBLE: thirty_hours_eligible,
    THIRTY_HOURS_VALUE: thirty_hours_value,
    UNIVERSAL_ELIGIBLE: universal_eligible,
    TARGETED_ELIGIBLE: targeted_eligible,
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


@contextmanager
def corrected_household_simulations():
    """Apply the corrections to every policyengine-uk simulation built inside the block.

    policyengine.py's ``calculate_household`` builds a policyengine-uk ``Simulation``
    from a situation and takes no simulation modifier, so the household calculator
    would otherwise run the uncorrected model. Each ``Simulation`` builds its own
    ``CountryTaxBenefitSystem``; inside the block every system it builds is corrected
    as it is created. Yields a list that records each corrected system, so a caller
    can check the correction reached its run.
    """
    import policyengine_uk.simulation as simulation_module

    original = simulation_module.CountryTaxBenefitSystem
    corrected = []

    def build(*args, **kwargs):
        system = original(*args, **kwargs)
        if not getattr(system.variables[THIRTY_HOURS_INCOME_TEST], MARK, False):
            apply_to_system(system)
        corrected.append(system)
        return system

    simulation_module.CountryTaxBenefitSystem = build
    try:
        yield corrected
    finally:
        simulation_module.CountryTaxBenefitSystem = original
