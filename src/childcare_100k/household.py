"""The £100,000 cliff for one illustrative family, through policyengine.py's household API."""

import hashlib
import importlib.metadata
import json
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from pathlib import Path

from .config import CLIFF, HOUSEHOLD_GRID, REFORM_PARAMETERS, REMOVED

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


def _people(earnings, partner_earnings=None, child_ages=None, spend_per_child=None):
    """Parents and children; ``partner_earnings=None`` with explicit ages gives a lone parent."""
    c = CLIFF
    if child_ages is None:  # the published cliff family
        partner_earnings, child_ages, spend_per_child = c["partner_earnings"], c["child_ages"], c["childcare_spend_per_child"]
    people = [{"age": 35, "employment_income": earnings, "is_parent": True}]
    if partner_earnings is not None:
        people.append({"age": 35, "employment_income": partner_earnings, "is_parent": True})
    people += [{"age": a, "childcare_expenses": spend_per_child} for a in child_ages]
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


def _run(earnings, year, reform, family=None):
    from policyengine.tax_benefit_models.uk import calculate_household

    result = calculate_household(
        people=_people(earnings, **(family or {})),
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


def _earnings(lo, hi, step):
    earnings = list(range(lo, hi + 1, step))
    if 100_000 in earnings:  # show both sides of the limit
        i = earnings.index(100_000)
        earnings = earnings[: i + 1] + [100_001] + earnings[i + 1:]
    return earnings


def _sweep(args):
    """Net income after childcare spending at every grid earnings level, in one axes call for one family."""
    from policyengine.tax_benefit_models.uk import calculate_household

    family, year, reform, lo, step, count = args
    result = calculate_household(
        people=_people(lo, **family),
        household={"region": CLIFF["region"]},
        year=year,
        reform=_reform(year) if reform else None,
        extra_variables=["household_net_income", "childcare_expenses"],
        axes=[[{"name": "employment_income", "min": lo, "max": lo + step * (count - 1), "count": count, "index": 0}]],
    )
    net = result.household["household_net_income"]
    spend = [sum(p["childcare_expenses"][i] for p in result.person) for i in range(count)]
    return [round(n - c) for n, c in zip(net, spend)]


def _grid_cache_key():
    """Everything the grid depends on: this module, the grid and cliff settings, and the model versions."""
    digest = hashlib.sha256(Path(__file__).read_bytes())
    digest.update(json.dumps({"grid": HOUSEHOLD_GRID, "cliff": CLIFF, "params": REFORM_PARAMETERS,
                              "removed": repr(REMOVED)}, sort_keys=True).encode())
    for pkg in ("policyengine", "policyengine-uk"):
        digest.update(importlib.metadata.version(pkg).encode())
    return digest.hexdigest()


def household_grid(workers=8):
    """The grid, reused from the run cache when nothing it depends on has changed."""
    from .config import RUNS

    path = RUNS / "household_grid.json"
    key = _grid_cache_key()
    if path.exists():
        cached = json.loads(path.read_text())
        if cached.get("key") == key:
            return cached["grid"]
    grid = _compute_household_grid(workers)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"key": key, "grid": grid}))
    return grid


def _compute_household_grid(workers=8):
    """One axes call per family and scenario: earnings sweep the grid in a single simulation."""
    g = HOUSEHOLD_GRID
    year = CLIFF["year"]
    lo, step, count = g["earnings_min"], g["earnings_step"], g["earnings_count"]
    earnings = [lo + step * i for i in range(count)]
    if 100_001 not in earnings or 99_001 not in earnings:
        raise ValueError("the grid must put £99,001 and £100,001 on its earnings points")
    combos = list(product(g["parents"], g["children"], g["spend_per_child"]))
    jobs = []
    for parent, children, spend in combos:
        family = {"partner_earnings": parent["partner_earnings"], "child_ages": children["ages"],
                  "spend_per_child": spend["amount"]}
        jobs += [(family, year, reform, lo, step, count) for reform in (False, True)]
    with ProcessPoolExecutor(workers) as pool:
        values = list(pool.map(_sweep, jobs))
    series = {
        f"{parent['id']}|{children['id']}|{spend['id']}": {"baseline": values[2 * k], "reform": values[2 * k + 1]}
        for k, (parent, children, spend) in enumerate(combos)
    }
    return {
        "year": year,
        "region": CLIFF["region"],
        "earnings": earnings,
        "options": {"parents": g["parents"], "children": g["children"], "spend_per_child": g["spend_per_child"]},
        "default": g["default"],
        "series": series,
    }
