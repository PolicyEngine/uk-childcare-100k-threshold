"""Model corrections applied to every run, baseline and reform alike.

Six corrections, each pending an upstream fix in policyengine-uk (2.102.3 is the
certified version; policyengine-uk#2079, merged after it, fixes the first two and the
fifth):

1. Exactly £100,000 qualifies for the 30 hours (C3).
2. A partner with a specified benefit need not pass the minimum earnings test (C1).
3. The universal and targeted 15 hours survive eligibility for the extended hours (C2).
4. Salary sacrifice returned to pay from April 2029 is not income for the limits.
5. Tax-Free Childcare regards a partner on a caring or incapacity benefit as in
   qualifying paid work (SI 2015/448 reg 13).
6. Both childcare schemes test the claimant and partner, not the ``is_parent`` flags.

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

5. Tax-Free Childcare: a partner on a caring or incapacity benefit (reg 13)
-------------------------------------------------------------------------
SI 2015/448 reg 13(1) regards a person whose partner is in qualifying paid work as in
qualifying paid work themselves while they are paid or entitled to a benefit, allowance
or credit in reg 13(1)(b): incapacity benefit, severe disablement allowance, carer's
allowance, contributory ESA, credits for incapacity or limited capability for work and
(from 1 December 2022) Scottish carer's assistance. Reg 13(2)(b) regards them as having
the minimum income; reg 15's £100,000 limit still applies to them. Reg 13(3) does not
count a partner as in qualifying paid work while that partner is *paid* a reg 13(1)(b)
benefit or allowance. policyengine-uk 2.102.3 tests the Pension Credit disability list
(DLA, PIP) and incapacity benefit in the work condition and never deems the minimum
income, so no such couple was ever eligible: a £120,000 earner whose partner receives
contributory ESA or Carer's Allowance got no Tax-Free Childcare even with the limit
removed. policyengine-uk#2079 rewrote both formulas; the replacements mirror it:

- ``tfc_regarded_as_in_paid_work`` is upstream's
  ``tax_free_childcare_regarded_as_in_paid_work``: a claimant or partner on a reg
  13(1)(b) benefit whose partner is ``tax_free_childcare_treated_as_in_work`` and not
  paid a reg 13(1)(b) benefit.
- The work condition is upstream's: every claimant and partner is 16 or over and in, or
  regarded as in, qualifying paid work. DLA and PIP are not on the list, so the
  Pension Credit route is gone, as upstream.
- The Tax-Free Childcare income test (section 4's replacement) also accepts reg
  13(2)(b)'s deemed minimum income.

Mapped to 2.102.3's variables (the costed years are all after December 2022):
entitlement is ``incapacity_benefit``, ``sda``, ``carers_allowance``,
``receives_carers_allowance``, ``carer_support_payment`` and ``esa_contrib``; payment
(reg 13(3)) is the same list. 2.102.3 has no overlapping-benefits rule for Carer's
Allowance, so its ``carers_allowance`` is both the entitlement and the payment
(upstream's ``carers_allowance_pre_overlap`` and ``is_entitled_to_carer_benefit`` do
not exist yet). Not mapped: NI credits for incapacity (upstream's
``receives_limited_capability_for_work_credits``, an input not in the data) and carer's
leave (reg 13(1)(c), upstream's ``tax_free_childcare_on_carers_leave``, likewise an
input). Upstream's ``is_claimant_or_partner`` does not exist in 2.102.3; section 6
ports it.

6. The claimant and partner, not the ``is_parent`` flags
--------------------------------------------------------
Childcare Payments Act 2014 s.3(1) requires the claimant's partner, as well as the
claimant, to meet the eligibility conditions (SI 2015/448 reg 9: in qualifying paid
work, or regarded as in it under reg 13; reg 15: the income limit). SI 2022/1134 reg 14
and 15 likewise test the parent and their partner. policyengine-uk 2.102.3 finds the
partner through ``is_parent``: the Tax-Free Childcare final income gate tests only
flagged parents, and the 30 hours' work condition counts them (a single flagged parent
in work passes as a lone parent). A couple whose partner is not flagged a parent (a
step-parent, say) was therefore paid Tax-Free Childcare when that partner neither
worked nor was regarded as working (the corrected reform paid the £2,000 cap to a
£120,000 earner with a nonworking unflagged partner), and a flagged parent on
Carer's Allowance whose unflagged partner works was refused the 30 hours.

``claimant_or_partner`` ports upstream's ``is_claimant_or_partner`` (merged after
2.102.3): the claimant is the adult benefit-unit head; the partner is the eldest other
flagged parent if there is one, else the eldest other adult; outside a couple, an adult
presumed to be the claimant's child (16 or more years younger and under 20, or at any age
when a flagged claimant has no such younger member to explain the flag) is passed over;
two flagged parents under an unflagged head are the couple. Within a benefit unit the
model makes a couple (``is_couple``, two or more members 18 or over) the presumption does
not apply: the other adult is the partner whatever their age or flag (a 19-year-old
nonworking partner of a £120,000 earner was presumed a child, and the corrected reform
paid that couple £2,000 of Tax-Free Childcare and £3,633.88 of extended hours). "Adult" is upstream's ``is_hbai_adult`` (not an HBAI
dependent child: under 16; 16-17 and neither head nor flagged; 18-19, neither, in
non-advanced education or approved training with a flagged parent), ported as
``hbai_adult``; the presumption's ages (20, 16) are upstream's parameters, which 2.102.3
lacks. The replacements use it in place of the flags:

- Tax-Free Childcare's work condition (section 5) and reg 13 test, and the final
  eligibility's income gate (``tax_free_childcare_eligible``), which upstream still
  writes with ``is_parent``.
- The 30 hours' work condition (``extended_childcare_entitlement_work_condition``,
  whose ``defined_for = "is_parent"`` is lifted) and income test (which tested every
  member 18 or over, so a lone parent living with a dependent 18- or 19-year-old failed
  it too).

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
TFC_WORK_CONDITION = "tax_free_childcare_work_condition"
THIRTY_HOURS_ELIGIBLE = "extended_childcare_entitlement_eligible"
THIRTY_HOURS_VALUE = "extended_childcare_entitlement"
UNIVERSAL_ELIGIBLE = "universal_childcare_entitlement_eligible"
TARGETED_ELIGIBLE = "targeted_childcare_entitlement_eligible"
TFC_ELIGIBLE = "tax_free_childcare_eligible"
THIRTY_HOURS_WORK_CONDITION = "extended_childcare_entitlement_work_condition"
# sha256 of inspect.getsource() of each model formula this module replaces (policyengine-uk 2.102.3).
EXPECTED_FORMULA_SHA256 = {
    THIRTY_HOURS_INCOME_TEST: "8ae8e181373d300974d7bdf434ea7e4ceeaf47a4c3a0e986a01a46d35e8ecfff",
    TFC_INCOME_TEST: "db72ceccc92a7f7c8bece286610df6fe63afe1b8f3d91353867650523310da6d",
    THIRTY_HOURS_ELIGIBLE: "1be9225945c80e49d79e277bb14c596ef37e0330a25a7345950731d10799113c",
    THIRTY_HOURS_VALUE: "4f7fa84421f58cd67d27c6610aee3d1c532c0d4b780a1cf76519f820f98666a8",
    UNIVERSAL_ELIGIBLE: "322527b7a86eea6e066574f2126f6ad7f47af6caeb7aab7ab64968ab4e6758c5",
    TARGETED_ELIGIBLE: "d4a98f6ca5d5a82eb92e2c3f9796f9a76b8952b1bb5834409a30b6a5f160a88a",
    TFC_WORK_CONDITION: "079ae1c2eafb745a7c97c3b08600049abad4a1d5728cf520cd49d49e4e049c7a",
    TFC_ELIGIBLE: "98ce3d2f004afee87e4beb588fe03649080e8fcfa777e310821ef38cff185948",
    THIRTY_HOURS_WORK_CONDITION: "4c147af4d5a1dc81a20dc7d24969519bd10d2a072736ad72038472c4f57d0484",
}
# Replacements that also lift the variable's ``defined_for`` (the model restricts it to
# ``is_parent``, which would hide an unflagged partner from the corrected formula).
CLEAR_DEFINED_FOR = {THIRTY_HOURS_WORK_CONDITION}
# SI 2015/448 reg 13(1)(b) as amended from 1 December 2022 (section 5), in 2.102.3's variables:
# "paid or entitled to" ...
TFC_CARING_OR_INCAPACITY_BENEFITS = [
    "incapacity_benefit",  # 13(1)(b)(i) and (iii)
    "sda",  # 13(1)(b)(ii)
    "carers_allowance",  # 13(1)(b)(iv); 2.102.3 has no overlapping-benefits rule, so paid = entitled
    "receives_carers_allowance",  # 13(1)(b)(iv), where supplied as received
    "esa_contrib",  # 13(1)(b)(v)
    "carer_support_payment",  # 13(1)(b)(vii): Scottish carer's assistance
]
# ... and reg 13(3)'s "paid" (the same variables in 2.102.3).
TFC_CARING_OR_INCAPACITY_BENEFITS_IN_PAYMENT = TFC_CARING_OR_INCAPACITY_BENEFITS
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


# Upstream's presumption parameters (household.demographic.benefit_unit.presumed_child and
# household.demographic.hbai.dependent_child), which 2.102.3 does not have.
PRESUMED_CHILD_AGE_LIMIT = 20
PRESUMED_CHILD_MINIMUM_AGE_GAP = 16
DEPENDENT_CHILD_AGE_LIMIT = 16
DEPENDENT_YOUNG_PERSON_AGE_LIMIT = 20


def hbai_adult(person, period):
    """Upstream's ``is_hbai_adult``: everyone who is not a dependent child (``is_hbai_dependent_child``'s fallback).

    Under 16; 16 or 17 and neither the benefit-unit head nor flagged a parent; or 18 or 19,
    neither head nor parent, in non-advanced education or approved training and living
    with a flagged parent aged 16 or over.
    """
    age = person("age", period)
    is_parent = person("is_parent", period)
    lives_as_dependant = ~person("is_benunit_head", period) & ~is_parent
    in_education_or_training = person("is_in_non_advanced_education", period) | person(
        "is_in_approved_training", period
    )
    under_child_age = age < DEPENDENT_CHILD_AGE_LIMIT
    lives_with_identified_parent = person.benunit.any(is_parent & ~under_child_age)
    under_18_dependant = lives_as_dependant & person("age_under_18", period)
    young_person = (
        lives_as_dependant
        & (age < DEPENDENT_YOUNG_PERSON_AGE_LIMIT)
        & in_education_or_training
        & lives_with_identified_parent
    )
    return ~(under_child_age | under_18_dependant | young_person)


def claimant_or_partner(person, period):
    """Upstream's ``is_claimant_or_partner`` (section 6): the claimant and, in a couple, the partner, flagged or not."""
    age = person("age", period)
    adult = hbai_adult(person, period)
    is_head = person("is_benunit_head", period)
    head_is_adult = person.benunit.any(is_head & adult)
    eldest_adult = adult & (person.get_rank(person.benunit, -age, condition=adult) == 0)
    adult_head = is_head & adult
    eldest_adult_head = adult_head & (
        person.get_rank(person.benunit, -age, condition=adult_head) == 0
    )
    claimant = np.where(head_is_adult, eldest_adult_head, eldest_adult)
    claimant_age = person.benunit.max(np.where(claimant, age, -np.inf))
    identified_parent = adult & person("is_parent", period)
    other_parent = identified_parent & ~claimant
    claimant_is_parent = person.benunit.any(claimant & identified_parent)
    # Two flagged parents other than a non-parent claimant are the couple.
    parents_are_couple = (person.benunit.sum(other_parent) >= 2) & ~claimant_is_parent
    parent_couple = other_parent & (
        person.get_rank(person.benunit, -age, condition=other_parent) < 2
    )
    large_gap = claimant_age - age >= PRESUMED_CHILD_MINIMUM_AGE_GAP
    young_child = (age < PRESUMED_CHILD_AGE_LIMIT) & large_gap
    # A flagged claimant with no young child to explain the flag is the parent of a
    # much younger member at any age.
    flag_unexplained = claimant_is_parent & ~person.benunit.any(young_child)
    presumed_child = ((age < PRESUMED_CHILD_AGE_LIMIT) | flag_unexplained) & large_gap
    # In a benefit unit the model itself makes a couple (``is_couple``: two or more members
    # 18 or over), the other adult is the claimant's partner at any age: the presumption
    # applies only outside a couple. An 18- or 19-year-old dependent young person (not an
    # ``hbai_adult``) is still not the partner.
    in_couple = person.benunit("is_couple", period)
    other_adult = adult & ~claimant & (in_couple | ~presumed_child)
    pool = np.where(person.benunit.any(other_parent), other_parent, other_adult)
    partner = pool & (person.get_rank(person.benunit, -age, condition=pool) == 0)
    return np.where(parents_are_couple, parent_couple, claimant | partner)


def tfc_regarded_as_in_paid_work(person, period):
    """Upstream's ``tax_free_childcare_regarded_as_in_paid_work`` (reg 13(1)(a)-(b), (3)), without carer's leave."""
    member = claimant_or_partner(person, period)
    caring_or_incapacity_benefit = (
        add(person, period, TFC_CARING_OR_INCAPACITY_BENEFITS) > 0
    )
    paid_caring_or_incapacity_benefit = (
        add(person, period, TFC_CARING_OR_INCAPACITY_BENEFITS_IN_PAYMENT) > 0
    )
    in_work_without_caring_or_incapacity_benefit = (
        member
        & person("tax_free_childcare_treated_as_in_work", period)
        & ~paid_caring_or_incapacity_benefit
    )
    partner_in_qualifying_paid_work = (
        person.benunit.sum(in_work_without_caring_or_incapacity_benefit)
        - in_work_without_caring_or_incapacity_benefit
    ) > 0
    return member & caring_or_incapacity_benefit & partner_in_qualifying_paid_work


def tfc_work_condition(person, period, parameters):
    """Upstream's (policyengine-uk#2079) formula: every claimant and partner is 16+ and in, or regarded as in, paid work."""
    benunit = person.benunit
    member = claimant_or_partner(person, period)
    in_qualifying_paid_work = person(
        "tax_free_childcare_treated_as_in_work", period
    ) | tfc_regarded_as_in_paid_work(person, period)
    meets_condition = person("over_16", period) & in_qualifying_paid_work
    # Reported on the applicant and partner; their children play no part.
    return member & benunit.all(meets_condition | ~member)


def tfc_income_test(person, period, parameters):
    """policyengine-uk's formula with ``income_for_limit`` in place of adjusted net income, and reg 13(2)(b)'s deemed minimum income."""
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
    # Reg 13(2)(b): a person regarded as in paid work through caring or incapacity
    # has expected income equal to the minimum (section 5).
    regarded_as_in_paid_work = tfc_regarded_as_in_paid_work(person, period)
    return (meets_minimum_income | in_start_up_period | regarded_as_in_paid_work) & (
        income_for_limit(person, period) <= p.income.income_limit
    )


def tfc_eligible(benunit, period, parameters):
    """policyengine-uk's formula with the income test on the claimant and partner, not the ``is_parent`` flags (section 6)."""
    person = benunit.members
    has_qualifying_child = benunit.any(person("tax_free_childcare_qualifying_child", period))
    meets_income_condition = benunit.all(
        person("tax_free_childcare_meets_income_requirements", period)
        | ~claimant_or_partner(person, period)
    )
    childcare_eligible = benunit("tax_free_childcare_program_eligible", period)
    work_eligible = benunit("tax_free_childcare_work_condition", period)
    return np.logical_and.reduce(
        [has_qualifying_child, meets_income_condition, childcare_eligible, work_eligible]
    )


def thirty_hours_work_condition(person, period, parameters):
    """policyengine-uk's formula on the claimant and partner (section 6) instead of the ``is_parent`` flags.

    A single claimant must be in work; in a couple both must be, or one in work and the
    other (or the family) on one of the model's ``disability_criteria`` (reg 14(4), 15(4)).
    Reported on the claimant and partner only.
    """
    benunit = person.benunit
    in_work = person("in_work", period)
    p = parameters(period).gov.dfe.extended_childcare_entitlement
    variables = person.entity.get_variable
    person_criteria = [v for v in p.disability_criteria if variables(v).entity.is_person]
    group_criteria = [v for v in p.disability_criteria if not variables(v).entity.is_person]
    on_person_criteria = (
        add(person, period, person_criteria) > 0
        if person_criteria
        else np.zeros(person.count, dtype=bool)
    )
    on_group_criteria = (
        add(benunit, period, group_criteria) > 0 if group_criteria else False
    )
    disability_eligible = on_person_criteria | on_group_criteria
    member = claimant_or_partner(person, period)
    members = benunit.sum(member)
    single_eligible = (members == 1) & in_work
    all_working = benunit.all(in_work | ~member)
    some_working = benunit.any(in_work & member)
    any_disability_eligible = benunit.any(disability_eligible & member)
    couple_eligible = (members == 2) & (all_working | (some_working & any_disability_eligible))
    return member & (single_eligible | couple_eligible)


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
    """policyengine-uk's formula on the claimant and partner (section 6), one on a specified benefit exempt from the income test (reg 14(4), 15(4))."""
    country = benunit.household("country", period)
    countries = country.possible_values
    in_england = country == countries.ENGLAND
    person = benunit.members
    person_meets_income_condition = (
        person("extended_childcare_entitlement_meets_income_requirements", period)
        | ~claimant_or_partner(person, period)
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
    TFC_WORK_CONDITION: tfc_work_condition,
    TFC_ELIGIBLE: tfc_eligible,
    THIRTY_HOURS_WORK_CONDITION: thirty_hours_work_condition,
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
        if name in CLEAR_DEFINED_FOR:
            variable.defined_for = None
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
