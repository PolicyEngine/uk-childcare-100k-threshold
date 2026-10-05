"""The £100,000 cliff for one illustrative family (policyengine-uk household simulation)."""

import numpy as np

from .config import CLIFF, REFORM_PARAMETERS, parameter_changes


def _situation(earnings, year):
    c = CLIFF
    people = {
        "parent_1": {"age": {year: 35}, "employment_income": {year: earnings}, "is_parent": {year: True}},
        "parent_2": {"age": {year: 35}, "employment_income": {year: c["partner_earnings"]}, "is_parent": {year: True}},
    }
    children = []
    for i, a in enumerate(c["child_ages"]):
        name = f"child_{i + 1}"
        people[name] = {"age": {year: a}, "childcare_expenses": {year: c["childcare_spend_per_child"]}}
        children.append(name)
    members = list(people)
    return {
        "people": people,
        "benunits": {"family": {"members": members}},
        "households": {"household": {"members": members, "region": {year: c["region"]}}},
    }


def _run(earnings, year, reform):
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    kwargs = {}
    if reform:
        kwargs["scenario"] = Scenario(parameter_changes=parameter_changes(REFORM_PARAMETERS))
    sim = Simulation(situation=_situation(earnings, year), **kwargs)

    def hh(v):
        return float(np.asarray(sim.calculate(v, year, map_to="household"))[0])

    free = sum(hh(v) for v in ("extended_childcare_entitlement", "universal_childcare_entitlement",
                               "targeted_childcare_entitlement"))
    return {
        "net_income": hh("household_net_income"),
        "free_hours_value": free,
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
            "Net income is policyengine-uk household net income (after tax and benefits, including the value of "
            "funded hours at the local-authority funding rate and the Tax-Free Childcare top-up) minus the family's "
            f"own childcare spending of £{spend:,} a year (£{c['childcare_spend_per_child']:,} per child), held fixed "
            "in both scenarios as in the population run. Both parents are under 40, work, pass the minimum income "
            "test and make no pension contributions, so adjusted net income equals employment income. Funded hours "
            "are valued at 30 hours x 38 weeks for each child (the model's default usage for a single household). "
            "The personal allowance taper between £100,000 and £125,140 applies in both scenarios. At exactly "
            "£100,000 the model already withdraws the 30 hours (it tests income < £100,000, where the law allows "
            "up to and including £100,000) but keeps Tax-Free Childcare."
        ),
    }
