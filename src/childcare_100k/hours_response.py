"""Hours response of parents in work whose childcare gets cheaper.

Ported from PolicyEngine/free-childcare-reform (``hours_response.py``). policyengine-uk's
intensive-margin machinery is driven by earnings elasticities and does not see a change
in the price of childcare, an input to working, so the response is

    hours change (%) = HOURS_PRICE_ELASTICITY x change in out-of-pocket childcare price (%)

for each adult in the responding population (``labour_supply.responding``, after the
OBR exclusions) who is in work, pays for childcare in the baseline and is not
themselves over £100,000 (the parent over the limit is a separate sensitivity; see
``GROUPS``). Hours and
earnings move together at a constant hourly wage. The exchequer effect is the model's:
the reform simulation is recomputed with the changed earnings, and the offset is the
extra earnings less the rise in household net income.

Out-of-pocket price. ``childcare_expenses`` is a fixed input, so the 30 hours do not
lower it in the simulation. As in free-childcare-reform, newly funded hours are
*assumed* to displace paid care at ``FREE_HOURS_DISPLACEMENT`` (90.5%) of their value,
capped at what the family spends, and Tax-Free Childcare (proportional to routed
spend) applies to what remains. The 90.5% is not a measured displacement of paid
care: IFS BN189 finds 570 more funded hours raised subsidisable care by 163 hours and
all care outside the immediate family by 54, so 1 - 54/570 counts every hour of
displaced non-family care, paid or unpaid, as paid. It is the upper end of what
BN189 supports for paid care at providers; 1 - 163/570 (71.4%), where only
subsidisable care already being bought is displaced, is the lower end. 71.4% and
100% are published as a sensitivity (``FREE_HOURS_DISPLACEMENT_RANGE``). The prices:

    baseline price = expenses - baseline Tax-Free Childcare
    reform price   = (expenses - displaced) x (1 - reform Tax-Free Childcare / expenses)

Dropped from the port: the Universal Credit childcare element. It is unchanged by the
reform and families with a parent over £100,000 receive essentially no Universal
Credit, so it would only enter the baseline price.

The elasticity, -0.042, is an extrapolated scenario assumption, not an estimated price
elasticity. Brewer et al. (IFS WP20/09) estimate +0.600 weekly hours (on a mean of
14.319, zeros for non-workers included) for mothers whose youngest child becomes
eligible for full-time rather than part-time free care; dividing that by a 100% price
fall and applying it to every working adult with a child under 12 extends it to other
interventions, parents and child ages it was not estimated on. It is a total-hours
effect, so it also overlaps with the extensive margin. The headline
applies it to responding adults at or below the limit only. Applied with the same
elasticity to the parent over £100,000 it would add much more (their earnings are
large and taxed at up to 62% in the personal-allowance taper), but the elasticity
is not measured on that group and their response to the limit itself (bunching) is
not modelled, so that figure is published separately as a sensitivity.
"""

from __future__ import annotations

import numpy as np
from microdf import MicroSeries

from .config import FREE_HOURS_DISPLACEMENT, FULL_TIME_HOURS, HOURS_PRICE_ELASTICITY
from .labour_supply import values


def out_of_pocket_prices(base, ref, displacement=FREE_HOURS_DISPLACEMENT):
    """Baseline and reform out-of-pocket childcare cost for each person's benefit unit."""
    expenses = base["actual_cost"]
    baseline_price = np.maximum(expenses - base["bu_tfc"], 0.0)
    new_free = np.maximum(ref["bu_free"] - base["bu_free"], 0.0)
    remaining = expenses - np.minimum(new_free * displacement, expenses)
    tfc_share = np.divide(ref["bu_tfc"], expenses, out=np.zeros_like(expenses), where=expenses > 0)
    reform_price = np.maximum(remaining * (1 - np.clip(tfc_share, 0, 1)), 0.0)
    return baseline_price, reform_price


# Who responds. The headline hours margin is adults at or below the limit (the partner of
# the parent over £100,000, and parents in families where only the other adult is over
# it); the parent over £100,000 is a separate, published sensitivity. The -0.042 is
# measured on mothers' hours, and that parent's response to the limit itself (bunching)
# is not modelled, so their hours are kept out of the headline.
GROUPS = ("at_or_below_limit", "over_limit")


def price_change(base, ref, group="at_or_below_limit", displacement=FREE_HOURS_DISPLACEMENT):
    """Proportional change in out-of-pocket price, for responding adults in work who pay for childcare."""
    baseline_price, reform_price = out_of_pocket_prices(base, ref, displacement)
    emp = base["employment_income"]
    in_group = base["over_limit"] if group == "over_limit" else ~base["over_limit"]
    respond = base["eligible"] & in_group & (emp > 0) & (base["weekly_hours"] > 0) & (baseline_price > 0)
    change = np.zeros_like(baseline_price)
    change[respond] = (reform_price[respond] - baseline_price[respond]) / baseline_price[respond]
    return respond, np.clip(change, -1.0, 1.0)


def hours_response(sim, year, base, ref, scale, group="at_or_below_limit", displacement=FREE_HOURS_DISPLACEMENT):
    """Extra hours, earnings and exchequer offset at one elasticity scale, on the reform simulation ``sim``."""
    if group not in GROUPS:
        raise ValueError(group)
    respond, change = price_change(base, ref, group, displacement)
    emp = base["employment_income"]
    w = base["weights"]
    share = np.where(respond, HOURS_PRICE_ELASTICITY * scale * change, 0.0)
    extra = emp * share

    before = values(sim, "household_net_income", year).astype(float)
    hh_weights = values(sim, "household_weight", year).astype(float)
    original = values(sim, "employment_income", year).astype(float)
    try:
        sim.reset_calculations()
        sim.set_input("employment_income", year, (original + extra).astype(np.float32))
        after = values(sim, "household_net_income", year).astype(float)
    finally:
        sim.reset_calculations()
        sim.set_input("employment_income", year, original.astype(np.float32))

    earnings = float(MicroSeries(extra, weights=w).sum())
    net_income = float(MicroSeries(after - before, weights=hh_weights).sum())
    extra_hours = float(MicroSeries(base["weekly_hours"] * share, weights=w).sum())
    return {
        "workers": float(MicroSeries(respond.astype(float), weights=w).sum()),
        "workers_price_falls": float(MicroSeries((respond & (change < 0)).astype(float), weights=w).sum()),
        "ftes": extra_hours / FULL_TIME_HOURS,
        "earnings": earnings,
        "offset": earnings - net_income,
        "mean_price_change": float(MicroSeries(change[respond], weights=w[respond]).mean()) if respond.any() else 0.0,
    }
