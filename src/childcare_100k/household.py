"""The £100,000 cliff for one illustrative family, through policyengine.py's household API."""

from .config import CLIFF, REFORM_PARAMETERS, REMOVED

FREE_HOURS_VARIABLES = (
    "extended_childcare_entitlement",
    "universal_childcare_entitlement",
    "targeted_childcare_entitlement",
)
OUTPUT_VARIABLES = (
    "household_net_income",
    *FREE_HOURS_VARIABLES,
    "tax_free_childcare",
    "income_tax",
    "childcare_expenses",
)


def _people(earnings):
    c = CLIFF
    people = [
        {"age": 35, "employment_income": earnings, "is_parent": True},
        {"age": 35, "employment_income": c["partner_earnings"], "is_parent": True},
    ]
    people += [{"age": a, "childcare_expenses": c["childcare_spend_per_child"]} for a in c["child_ages"]]
    return people


def _reform(year):
    """Each limit removed from 1 January of the example year, as policyengine.py dates scalar reforms."""
    return {p: {f"{year}-01-01": REMOVED} for p in REFORM_PARAMETERS}


def _household_total(result, variable):
    """The household total of a variable, from whichever entity policyengine.py returns it on."""
    if variable in result.household:
        return float(result.household[variable])
    if variable in result.benunit:
        return float(result.benunit[variable])
    if all(variable in person for person in result.person):
        return float(sum(person[variable] for person in result.person))
    raise KeyError(f"{variable} is not in the household result")


def _run(earnings, year, reform):
    from policyengine.tax_benefit_models.uk import calculate_household

    result = calculate_household(
        people=_people(earnings),
        household={"region": CLIFF["region"]},
        year=year,
        reform=_reform(year) if reform else None,
        extra_variables=list(OUTPUT_VARIABLES),
    )

    def hh(v):
        return _household_total(result, v)

    return {
        "net_income": hh("household_net_income"),
        "free_hours_value": sum(hh(v) for v in FREE_HOURS_VARIABLES),
        "tfc": hh("tax_free_childcare"),
        "income_tax": hh("income_tax"),
        "childcare_spend": hh("childcare_expenses"),
    }


def cliff_example():
    c = CLIFF
    year = c["year"]
    earnings = list(range(c["earnings_min"], c["earnings_max"] + 1, c["earnings_step"]))
    if 100_000 in earnings:  # show both sides of the limit
        i = earnings.index(100_000)
        earnings = earnings[: i + 1] + [100_001] + earnings[i + 1:]
    base = [_run(e, year, False) for e in earnings]
    ref = [_run(e, year, True) for e in earnings]

    def after_childcare(r):
        return round(r["net_income"] - r["childcare_spend"])

    spend = c["childcare_spend_per_child"] * len(c["child_ages"])
    return {
        "description": (
            f"A couple in England ({c['region'].replace('_', ' ').title()}) with children aged "
            f"{' and '.join(map(str, c['child_ages']))}; one parent earns £{c['partner_earnings']:,}, the other's "
            f"employment income varies from £{c['earnings_min']:,} to £{c['earnings_max']:,} "
            f"({year}-{(year + 1) % 100:02d} tax year)."
        ),
        "year": year,
        "earnings": earnings,
        "net_income_baseline": [after_childcare(r) for r in base],
        "net_income_reform": [after_childcare(r) for r in ref],
        "components": {
            "free_hours_value_baseline": [round(r["free_hours_value"]) for r in base],
            "free_hours_value_reform": [round(r["free_hours_value"]) for r in ref],
            "tax_free_childcare_baseline": [round(r["tfc"]) for r in base],
            "tax_free_childcare_reform": [round(r["tfc"]) for r in ref],
            "income_tax_baseline": [round(r["income_tax"]) for r in base],
            "income_tax_reform": [round(r["income_tax"]) for r in ref],
        },
        "notes": (
            "Computed with policyengine.py's household calculator (calculate_household), the same model "
            "release as the population runs. Net income is household net income (after tax and benefits, "
            "including the value of funded hours at the local-authority funding rate and the Tax-Free "
            f"Childcare top-up) minus the family's own childcare spending of £{spend:,} a year "
            f"(£{c['childcare_spend_per_child']:,} per child), held fixed in both scenarios as in the population "
            "run. Both parents are under 40, work, pass the minimum income test and make no pension "
            "contributions, so adjusted net income equals employment income. Funded hours are valued at 30 "
            "hours x 38 weeks for each child (the model's default usage for a single household). The personal "
            "allowance taper between £100,000 and £125,140 applies in both scenarios. At exactly £100,000 the "
            "model already withdraws the 30 hours (it tests income < £100,000, where the law allows up to and "
            "including £100,000) but keeps Tax-Free Childcare."
        ),
    }
