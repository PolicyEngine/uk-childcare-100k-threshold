"""Model correction, written against policyengine-uk 2.147.2.

One correction applies to every run, baseline and reform alike.

Correction
==========

C6 (Tax-Free Childcare half). The final income gate tests the claimant and partner
---------------------------------------------------------------------------------
Childcare Payments Act 2014 s.3(1) requires the claimant's partner, as well as the
claimant, to meet the income condition (SI 2015/448 reg 15). policyengine-uk
2.147.2's ``tax_free_childcare_eligible`` still applies the income test to members
flagged ``is_parent``, so an unflagged partner (a step-parent, say) over the limit
passes. The replacement tests upstream's ``is_claimant_or_partner`` instead.

Dropped, now upstream (each checked in the policyengine-uk 2.147.2 source)
-------------------------------------------------------------------------
- C1: a partner with a specified benefit need not pass the work or income
  conditions (``extended_childcare_entitlement_limited_capability_or_specified_benefit``).
- C2: the universal and targeted 15 hours survive eligibility for the extended
  hours; the extended value is ``extended_childcare_entitlement_per_child``, the
  hours above them.
- C3: exactly £100,000 qualifies (``ani <= p.income.limit``).
- C4: salary sacrifice above the April 2029 National Insurance cap no longer
  raises adjusted net income (policyengine-uk#2462). The cap now changes only NIC
  earnings; ``salary_sacrifice_returned_to_income`` has no formula and defaults to
  zero, and the release stores no value for it.
- C5: Tax-Free Childcare reg 13 (``tax_free_childcare_regarded_as_in_paid_work``).
- C6 (30-hours half, and Tax-Free Childcare's work condition): both use
  ``is_claimant_or_partner``.
- Pension contributions in adjusted net income (policyengine-uk#2440):
  ``adjusted_net_income`` now deducts ``pension_contributions_relief`` (Income Tax
  Act 2007 s.58).
- DfE's funding rates (policyengine-uk#2465): ``gov.dfe.childcare_funding_rate``
  holds DfE's 2025-26 and 2026-27 national averages (£12.04, £8.90 and £6.61 an
  hour in 2026-27), uprated by CPI after that.
- Reception (policyengine-uk#2570): ``early_years_term_share_before_school`` ends
  the universal and working-parent hours when a child starts school, from the date
  of birth, so a 4-year-old keeps only the terms before its reception September.
- 9-11-month-olds (policyengine-uk#2570): ``extended_childcare_entitlement_term_share``
  starts the working-parent hours from the first term after a child turns 9
  months, from ``age`` and ``months_since_last_birthday``, which the release
  stores for every child. Children aged 0 now qualify in the model, so nothing is
  added outside it.

The replacement reproduces the model's formula with only the stated change. The
model's formula is fingerprinted: if policyengine-uk changes it, the correction
refuses to apply, rather than silently replacing new logic with old.
"""

import hashlib
import inspect
from contextlib import contextmanager

import numpy as np

TFC_ELIGIBLE = "tax_free_childcare_eligible"

# sha256 of inspect.getsource() of each model formula replaced here (policyengine-uk 2.147.2).
EXPECTED_FORMULA_SHA256 = {
    TFC_ELIGIBLE: "98ce3d2f004afee87e4beb588fe03649080e8fcfa777e310821ef38cff185948",
}
MARK = "_childcare_100k_corrected"


def tfc_eligible(benunit, period, parameters):
    """policyengine-uk 2.147.2's formula with the income test on the claimant and partner, not ``is_parent`` (C6)."""
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


REPLACEMENTS = {TFC_ELIGIBLE: tfc_eligible}


def apply_to_system(tax_benefit_system):
    for name, replacement in REPLACEMENTS.items():
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


def is_applied(tax_benefit_system):
    return all(getattr(tax_benefit_system.variables[n], MARK, False) for n in REPLACEMENTS)


def apply_corrections(simulation):
    """Scenario modifier: the correction, on every run."""
    apply_to_system(simulation.tax_benefit_system)


@contextmanager
def corrected_household_simulations():
    """Apply the correction to every policyengine-uk simulation built inside the block.

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
        if not getattr(system.variables[TFC_ELIGIBLE], MARK, False):
            apply_to_system(system)
        corrected.append(system)
        return system

    simulation_module.CountryTaxBenefitSystem = build
    try:
        yield corrected
    finally:
        simulation_module.CountryTaxBenefitSystem = original
