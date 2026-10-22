"""Model corrections and toggles, written against policyengine-uk 2.134.4.

Two corrections apply to every run, baseline and reform alike. Three toggles are
off in the shipped line and on in the line on CenTax's basis (``CENTAX_BASIS``);
a fourth, the 9-11-month-olds, is added outside the model (aggregate.py).

Corrections
===========

C4. The childcare income tests exclude salary sacrifice returned to pay (from 6 April 2029)
-----------------------------------------------------------------------------------------
From 6 April 2029, pension contributions made through salary sacrifice above
£2,000 a year are subject to Class 1 National Insurance. HMRC's policy paper says
the measure changes National Insurance only and does not change salary
sacrifice's effect on adjusted net income, naming Tax-Free Childcare among the
schemes unaffected:
https://www.gov.uk/government/publications/salary-sacrifice-reform-for-pension-contributions-effective-from-6-april-2029/salary-sacrifice-reform-for-pension-contributions

policyengine-uk 2.134.4 still models the cap by adding the excess above £2,000
(``salary_sacrifice_returned_to_income``) to ``employment_income``, so it flows
into ``adjusted_net_income``. Both childcare income tests (the 30 funded hours for
working parents and Tax-Free Childcare) are replaced with copies that compare
adjusted net income less ``salary_sacrifice_returned_to_income`` with the limit.
``adjusted_net_income`` itself is left alone: the model derives taxable income
from it and also deducts the returned amount as pension relief. The minimum-income
tests are unchanged. It is a no-op before 2029-30, while the cap is unset.

C6 (Tax-Free Childcare half). The final income gate tests the claimant and partner
---------------------------------------------------------------------------------
Childcare Payments Act 2014 s.3(1) requires the claimant's partner, as well as the
claimant, to meet the income condition (SI 2015/448 reg 15). policyengine-uk
2.134.4's ``tax_free_childcare_eligible`` still applies the income test to members
flagged ``is_parent``, so an unflagged partner (a step-parent, say) over the limit
passes. The replacement tests upstream's ``is_claimant_or_partner`` instead.

Dropped (now upstream in policyengine-uk 2.134.4)
-------------------------------------------------
- C1: a partner with a specified benefit need not pass the work or income
  conditions (``extended_childcare_entitlement_limited_capability_or_specified_benefit``,
  used by ``extended_childcare_entitlement_work_condition``).
- C2: the universal and targeted 15 hours survive eligibility for the extended
  hours (``universal_childcare_entitlement_eligible`` and
  ``targeted_childcare_entitlement_eligible`` no longer switch off; the extended
  value is ``extended_childcare_entitlement_per_child``, the hours above them).
- C3: exactly £100,000 qualifies (``ani <= p.income.limit``).
- C5: Tax-Free Childcare reg 13 (``tax_free_childcare_regarded_as_in_paid_work``).
- C6 (30-hours half, and Tax-Free Childcare's work condition): both use
  ``is_claimant_or_partner``.

Toggles
=======

``reception``: no funded hours for a 4-year-old in reception
------------------------------------------------------------
A child in a reception class of a maintained school is in full-time education, so
the early-years funded hours stop. The model gives funded hours to every child
under compulsory school age (5). The toggle removes the universal and extended
entitlements for a child whose ``current_education`` is ``PRIMARY``, as the data
record reception (about 46% of weighted 4-year-olds on the 19 October 2026 release;
the model's own age-based default never sets ``PRIMARY`` before 7, so the flag
comes from the data). Not yet fixed in policyengine-uk.

``dfe_rates``: DfE's published funding rates
--------------------------------------------
The model values funded hours at 2024-25 rates uprated by CPI (£11.89, £8.78 and
£6.23 an hour for under-2s, 2-year-olds and 3- and 4-year-olds in 2026-27). DfE's
2026-27 national average rates are £12.04, £8.90 and £6.61 (validation.py). The
toggle sets each year from 2026-27 to DfE's 2026-27 rate times the model's own CPI
uprating from 2026-27 to that year. Not yet fixed in policyengine-uk.

``pension_in_ani``: adjusted net income after pension contributions
-------------------------------------------------------------------
Income Tax Act 2007 s.58 deducts grossed-up pension contributions in arriving at
adjusted net income. policyengine-uk 2.134.4 does not: ``adjusted_net_income`` is
``net_income`` less Gift Aid, ``net_income`` sums the taxable income components
(``adjusted_net_income_components``), and ``taxable_employment_income`` deducts
only ``employment_expenses``; ``pension_contributions_relief`` comes off later, in
``allowances``. The toggle tests income less the larger of the model's
``pension_contributions_relief`` and the salary sacrifice returned to pay (C4; the
relief includes the returned amount, so this is the relief whenever it is the
larger).

``under_ones``: 9- to 11-month-olds
-----------------------------------
The model holds age in whole years and gives age 0 no funded hours. Added outside the
model (aggregate.under_ones_cost), so it has no system change here.

Each replacement reproduces the model's formula with only the stated change. The
model's formulas are fingerprinted: if policyengine-uk changes any of them, the
correction refuses to apply, rather than silently replacing new logic with old.
"""

import hashlib
import inspect
from contextlib import contextmanager

import numpy as np
from policyengine_core.periods import instant
from policyengine_uk.model_api import add

RETURNED_SALARY_SACRIFICE = "salary_sacrifice_returned_to_income"
PENSION_RELIEF = "pension_contributions_relief"
THIRTY_HOURS_INCOME_TEST = "extended_childcare_entitlement_meets_income_requirements"
TFC_INCOME_TEST = "tax_free_childcare_meets_income_requirements"
TFC_ELIGIBLE = "tax_free_childcare_eligible"
QUALIFYING_CHILD = "extended_childcare_entitlement_qualifying_child"
UNIVERSAL_ELIGIBLE = "universal_childcare_entitlement_eligible"
FUNDING_RATE = "gov.dfe.childcare_funding_rate"

# sha256 of inspect.getsource() of each model formula replaced here (policyengine-uk 2.134.4).
EXPECTED_FORMULA_SHA256 = {
    THIRTY_HOURS_INCOME_TEST: "ac02912ececf8b7e8241ce9ca895751ae2fa89b19c50ea92cd1883e10b50581f",
    TFC_INCOME_TEST: "a49dcd64411652a026fdb2e69c5462584c9cc56351236a18d1ef19c3c04c36b4",
    TFC_ELIGIBLE: "98ce3d2f004afee87e4beb588fe03649080e8fcfa777e310821ef38cff185948",
    QUALIFYING_CHILD: "7a8d6455dda1443577963939e1257be3391f4c32c210a93cd19f3f7b9640e12c",
    UNIVERSAL_ELIGIBLE: "5491b26bedd4d4742ac2cad58e4d3a39ae0309f7f5b95971ad34c6e7048b23a1",
}

# Toggles (module docstring). ``under_ones`` is applied in aggregate.py, outside the model.
RECEPTION = "reception"
DFE_RATES = "dfe_rates"
PENSION_IN_ANI = "pension_in_ani"
UNDER_ONES = "under_ones"
MODEL_TOGGLES = (RECEPTION, DFE_RATES, PENSION_IN_ANI)
TOGGLES = MODEL_TOGGLES + (UNDER_ONES,)
CENTAX_BASIS = TOGGLES

# DfE, 2026 to 2027 early years national funding formulae: technical note (validation.py's
# OFFICIAL rates): national average hourly rates for under-2s, 2-year-olds, 3- and 4-year-olds,
# in the order of the model's funding-rate brackets (thresholds 0, 2 and 3).
DFE_RATES_2026 = (12.04, 8.90, 6.61)
DFE_RATES_YEAR = 2026
MARK = "_childcare_100k_corrected"


def _limit_income(person, period, pension_in_ani):
    """Adjusted net income as the childcare limits test it: less salary sacrifice returned to pay (C4) and,
    with ``pension_in_ani``, less pension contributions (the larger of the relief and the returned amount)."""
    ani = person("adjusted_net_income", period)
    returned = person(RETURNED_SALARY_SACRIFICE, period)
    if pension_in_ani:
        return ani - np.maximum(person(PENSION_RELIEF, period), returned)
    return ani - returned


def income_for_limit(person, period):
    """C4 only: adjusted net income less salary sacrifice returned to pay."""
    return _limit_income(person, period, False)


def _thirty_hours_income_test(person, period, parameters, pension_in_ani=False):
    """policyengine-uk 2.134.4's formula with the limit income (C4, optionally pension_in_ani) in place of ANI."""
    p = parameters(period).gov.dfe.extended_childcare_entitlement
    yearly_eligible_income = add(person, period, p.income.countable_sources)
    quarterly_income = yearly_eligible_income / 4
    min_wage_rate = person("minimum_wage", period)
    required_threshold = min_wage_rate * p.minimum_weekly_hours * 13
    income = _limit_income(person, period, pension_in_ani)
    return (quarterly_income >= required_threshold) & (income <= p.income.limit)


def _tfc_income_test(person, period, parameters, pension_in_ani=False):
    """policyengine-uk 2.134.4's formula with the limit income (C4, optionally pension_in_ani) in place of ANI."""
    p = parameters(period).gov.hmrc.tax_free_childcare
    expected_income = person("tax_free_childcare_expected_declaration_period_income", period)
    min_wage_rate = person("minimum_wage", period)
    required_threshold = min_wage_rate * p.minimum_weekly_hours * p.income.declaration_period_weeks
    meets_minimum_income = expected_income >= required_threshold
    in_start_up_period = person("tax_free_childcare_self_employment_start_up_period", period)
    regarded_as_in_paid_work = person("tax_free_childcare_regarded_as_in_paid_work", period)
    income = _limit_income(person, period, pension_in_ani)
    return (meets_minimum_income | in_start_up_period | regarded_as_in_paid_work) & (
        income <= p.income.income_limit
    )


def tfc_eligible(benunit, period, parameters):
    """policyengine-uk 2.134.4's formula with the income test on the claimant and partner, not ``is_parent`` (C6)."""
    person = benunit.members
    has_qualifying_child = benunit.any(person("tax_free_childcare_qualifying_child", period))
    meets_income_condition = benunit.all(
        person("tax_free_childcare_meets_income_requirements", period)
        | ~person("is_claimant_or_partner", period)
    )
    childcare_eligible = benunit("tax_free_childcare_program_eligible", period)
    work_eligible = benunit("tax_free_childcare_work_condition", period)
    return np.logical_and.reduce(
        [has_qualifying_child, meets_income_condition, childcare_eligible, work_eligible]
    )


def in_reception(person, period):
    """A child the data record in primary school (reception) while under compulsory school age."""
    education = person("current_education", period)
    return education == education.possible_values.PRIMARY


def qualifying_child_not_in_reception(person, period, parameters):
    """policyengine-uk 2.134.4's formula, less children in reception (``reception`` toggle)."""
    p = parameters(period).gov.dfe
    age = person("age", period)
    compulsory_school_age = p.compulsory_school_age
    compulsory_school_age_start = min(
        threshold
        for threshold, is_compulsory in zip(
            compulsory_school_age.thresholds, compulsory_school_age.amounts
        )
        if is_compulsory
    )
    under_compulsory_school_age = age < compulsory_school_age_start
    country = person.household("country", period)
    in_england = country == country.possible_values.ENGLAND
    meets_minimum_age = age >= p.extended_childcare_entitlement.young_child_minimum_age
    not_looked_after = ~person("is_looked_after_by_local_authority", period)
    return (
        under_compulsory_school_age
        & in_england
        & meets_minimum_age
        & not_looked_after
        & ~in_reception(person, period)
    )


def universal_eligible_not_in_reception(person, period, parameters):
    """policyengine-uk 2.134.4's formula, less children in reception (``reception`` toggle)."""
    country = person.household("country", period)
    in_england = country == country.possible_values.ENGLAND
    age = person("age", period)
    p = parameters(period).gov.dfe.universal_childcare_entitlement
    meets_age_condition = (age >= p.age.min) & (age < p.age.max)
    not_compulsory_age = ~person("is_of_compulsory_school_age", period)
    return in_england & meets_age_condition & not_compulsory_age & ~in_reception(person, period)


def replacements(toggles=()):
    """The formula replacements for a run: the corrections, and the model toggles that replace formulas."""
    unknown = set(toggles) - set(TOGGLES)
    if unknown:
        raise ValueError(f"unknown toggles {sorted(unknown)}")
    pension = PENSION_IN_ANI in toggles

    def thirty_hours_income_test(person, period, parameters):
        return _thirty_hours_income_test(person, period, parameters, pension_in_ani=pension)

    def tfc_income_test(person, period, parameters):
        return _tfc_income_test(person, period, parameters, pension_in_ani=pension)

    out = {
        THIRTY_HOURS_INCOME_TEST: thirty_hours_income_test,
        TFC_INCOME_TEST: tfc_income_test,
        TFC_ELIGIBLE: tfc_eligible,
    }
    if RECEPTION in toggles:
        out[QUALIFYING_CHILD] = qualifying_child_not_in_reception
        out[UNIVERSAL_ELIGIBLE] = universal_eligible_not_in_reception
    return out


def set_dfe_rates(tax_benefit_system, years):
    """``dfe_rates``: each year from 2026-27 at DfE's 2026-27 rate times the model's CPI uprating since then.

    A year's formulas read parameters at 1 January of that year's key, so each value is set
    for the whole calendar year of the key.
    """
    brackets = tax_benefit_system.parameters.get_child(FUNDING_RATE).brackets
    if len(brackets) != len(DFE_RATES_2026):
        raise RuntimeError(f"{FUNDING_RATE} has {len(brackets)} brackets, expected {len(DFE_RATES_2026)}")
    for bracket, dfe in zip(brackets, DFE_RATES_2026):
        base = bracket.amount(f"{DFE_RATES_YEAR}-01-01")
        values = {y: dfe * bracket.amount(f"{y}-01-01") / base for y in years if y >= DFE_RATES_YEAR}
        for y, value in values.items():
            bracket.amount.update(start=instant(f"{y}-01-01"), stop=instant(f"{y}-12-31"), value=float(value))


def apply_to_system(tax_benefit_system, toggles=(), years=()):
    for name, replacement in replacements(toggles).items():
        variable = tax_benefit_system.variables[name]
        if getattr(variable, MARK, False):
            raise RuntimeError(f"{name} has already been corrected in this tax-benefit system")
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
    if DFE_RATES in toggles:
        set_dfe_rates(tax_benefit_system, years)
    tax_benefit_system._childcare_100k_toggles = tuple(sorted(set(toggles)))


def is_applied(tax_benefit_system, toggles=()):
    return all(
        getattr(tax_benefit_system.variables[n], MARK, False) for n in replacements(toggles)
    ) and getattr(tax_benefit_system, "_childcare_100k_toggles", None) == tuple(sorted(set(toggles)))


def apply_corrections(simulation):
    """Scenario modifier: the corrections only (the shipped line)."""
    apply_to_system(simulation.tax_benefit_system)


def modifier(toggles=(), years=()):
    """Scenario modifier: the corrections and the given toggles (``years`` sets the ``dfe_rates`` years)."""
    toggles = tuple(toggles)
    if DFE_RATES in toggles and not years:
        raise ValueError("dfe_rates needs the years to set")

    def apply(simulation):
        apply_to_system(simulation.tax_benefit_system, toggles, years)

    return apply


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
