"""Hours response of parents in work: a price effect and an income effect.

policyengine-uk's intensive-margin machinery is driven by changes in marginal tax rates
and net income; it does not see a change in the price of childcare, an input to
working. The reform changes two things for an adult in work in the responding
population (``labour_supply.responding``, after the OBR exclusions), whatever their own
income, so the hours response has two parts, computed separately for the adults at or
below £100,000 and the adults over it (``GROUPS``):

    price effect:   earnings change = earnings x HOURS_PRICE_ELASTICITY x change in the
                    marginal price of paid childcare (%)
    income effect:  earnings change = earnings x OBR income elasticity
                    x change in household net income (%)

Hours and earnings move together at a constant hourly wage. Each part's exchequer effect
is the model's: the reform simulation is recomputed with that part's changed earnings,
and the offset is the extra earnings less the rise in household net income (positive is
money back). The net hours offset is the sum of the two parts.

The price effect: what counts as a price change
===============================================

An extra hour of work needs an extra hour of paid childcare. Only a change in what that
*marginal* hour costs the family is a price change; support that does not depend on how
many hours the family buys is a lump sum, which enters through the income effect.

* Tax-Free Childcare pays 20% of each £1 of routed spend until the child's cap is
  reached, so where the reform newly pays it and the cap does not bind, the marginal
  price falls. The marginal rate is the model's own: the change in the family's
  ``tax_free_childcare`` when its childcare spend rises by 1% (``tfc_marginal_rate``),
  which carries the routed share (59.3% of spend in this data, so about 11.9p per £1),
  each child's cap, the eligible part of the year and the take-up draw. A family at the
  cap gets no price change from Tax-Free Childcare.
* The 30 funded hours are a fixed number of hours, conditional only on both parents
  passing the minimum earnings test. For a family that still buys paid care on top of
  the newly funded hours, the funded hours do not change the price of the marginal hour
  (it is still bought at the full price, less any Tax-Free Childcare): they are
  inframarginal, a lump sum. Only where the newly funded hours cover all the paid care
  the family buys do they make the marginal hour free (a 100% fall, the setting in which
  Brewer et al. estimate the elasticity: a move from part-time to full-time free care).
  ``childcare_expenses`` is an annual spend, not hours, so the test is on value: the
  family is fully covered if newly funded hours, displacing paid care at
  ``FREE_HOURS_DISPLACEMENT`` (90.5%) of their value, are worth at least its spend.
  The 90.5% is an assumption (IFS BN189: 570 more funded hours raised subsidisable care
  by 163 hours and all non-family care by 54; 1 - 54/570 counts every displaced hour of
  non-family care as paid); 71.4% (1 - 163/570) and 100% are published as a sensitivity
  (``FREE_HOURS_DISPLACEMENT_RANGE``).

The rule is the same for every adult in the family: the family buys one set of
childcare. The earlier version of this module turned the fall in the family's whole
out-of-pocket spend into a percentage price fall, which counted the lump-sum value of the
funded hours as a price cut and gave the parent over £100,000 a large positive response;
that is the doubtful direction this version removes.

Responding to the price: adults in work whose family pays for childcare in the baseline.

The income effect
=================

The OBR's income elasticities (Table A2 of the note; policyengine-uk's
``calculate_labour_net_income_elasticities``: for example -0.185 for a woman in a couple
whose youngest child is 0-2, -0.05 for a man in a couple) applied as policyengine-uk's
``apply_progression_responses`` does: earnings change = earnings x elasticity x
(reform - baseline household net income) / baseline household net income, the relative
change clipped to +/-100%. Household net income is the model's ``household_net_income``,
static (before any response), which counts the funded hours at their funding value and
Tax-Free Childcare. Responding: every adult in work in the responding population.

The elasticity, -0.042, is an extrapolated scenario assumption, not an estimated price
elasticity. Brewer et al. (IFS WP20/09) estimate +0.600 weekly hours (on a mean of
14.319, zeros for non-workers included) for mothers whose youngest child becomes
eligible for full-time rather than part-time free care; dividing that by a 100% price
fall and applying it to every working adult with a child under 12 extends it to other
interventions, parents and child ages it was not estimated on. It is a total-hours
effect, so it also overlaps with the extensive margin. The low and high bounds scale
both elasticities (``ELASTICITY_SCALES``).

Dropped from the port: the Universal Credit childcare element. It is unchanged by the
reform and families with a parent over £100,000 receive essentially no Universal Credit.
"""

from __future__ import annotations

import numpy as np
from microdf import MicroSeries

from .config import FREE_HOURS_DISPLACEMENT, FULL_TIME_HOURS, HOURS_PRICE_ELASTICITY
from .labour_supply import values

# Who responds, split by their own income as the limits test it. Both groups use the same rules.
GROUPS = ("at_or_below_limit", "over_limit")
COMPONENTS = ("price", "income")
# The proportional rise in childcare spend used to read the model's marginal Tax-Free Childcare rate.
TFC_STEP = 0.01


def tfc_marginal_rate(sim, year):
    """Tax-Free Childcare paid on the family's next £1 of childcare spend (on each member), the model's own.

    Every person's ``childcare_expenses`` is raised by ``TFC_STEP`` and the family's
    ``tax_free_childcare`` recomputed; the rate is the change over the change in spend
    (0 where the family spends nothing). The simulation is restored afterwards.
    """
    from .labour_supply import per_person

    spend = values(sim, "childcare_expenses", year).astype(float)
    bu_spend = per_person(sim, year, values(sim, "childcare_expenses", year, "benunit").astype(float))
    before = per_person(sim, year, values(sim, "tax_free_childcare", year, "benunit").astype(float))
    try:
        sim.reset_calculations()
        sim.set_input("childcare_expenses", year, (spend * (1 + TFC_STEP)).astype(np.float32))
        after = per_person(sim, year, values(sim, "tax_free_childcare", year, "benunit").astype(float))
    finally:
        sim.reset_calculations()
        sim.set_input("childcare_expenses", year, spend.astype(np.float32))
    rate = np.divide(after - before, bu_spend * TFC_STEP, out=np.zeros_like(bu_spend), where=bu_spend > 0)
    return np.clip(rate, 0.0, 1.0)


def marginal_price_change(base, ref, displacement=FREE_HOURS_DISPLACEMENT):
    """Proportional change in the price of the family's marginal hour of paid care, and who is fully covered.

    Baseline marginal price: 1 less the baseline Tax-Free Childcare rate. Reform: zero if
    newly funded hours (at ``displacement`` of their value) cover all the family's paid
    care, otherwise 1 less the reform's Tax-Free Childcare rate.
    """
    expenses = base["actual_cost"]
    new_free = np.maximum(ref["bu_free"] - base["bu_free"], 0.0)
    covered = (expenses > 0) & (new_free * displacement >= expenses)
    before = 1.0 - base["tfc_rate"]
    after = np.where(covered, 0.0, 1.0 - ref["tfc_rate"])
    change = np.divide(after - before, before, out=np.zeros_like(before), where=before > 0)
    return covered, np.clip(change, -1.0, 1.0)


def _members(base, group):
    """Responding adults in work in the group."""
    in_group = base["over_limit"] if group == "over_limit" else ~base["over_limit"]
    return base["eligible"] & in_group & (base["employment_income"] > 0) & (base["weekly_hours"] > 0)


def price_change(base, ref, group="at_or_below_limit", displacement=FREE_HOURS_DISPLACEMENT):
    """Who responds to the price (in work, family pays for childcare) and their marginal price change."""
    covered, change = marginal_price_change(base, ref, displacement)
    respond = _members(base, group) & (base["actual_cost"] > 0)
    return respond, np.where(respond, change, 0.0), respond & covered


def income_change(base, ref, group="at_or_below_limit"):
    """Who responds to income (in work) and the relative change in their household's net income."""
    respond = _members(base, group)
    before, after = base["hh_net_income"], ref["hh_net_income"]
    rel = np.divide(after - before, before, out=np.zeros_like(before), where=before > 0)
    return respond, np.where(respond, np.clip(rel, -1.0, 1.0), 0.0)


def earnings_shares(base, ref, scale, group="at_or_below_limit", displacement=FREE_HOURS_DISPLACEMENT):
    """Each part's proportional change in earnings (and hours) for every person, at one elasticity scale."""
    respond_p, d_price, covered = price_change(base, ref, group, displacement)
    respond_i, d_income = income_change(base, ref, group)
    return {
        "price": np.where(respond_p, HOURS_PRICE_ELASTICITY * scale * d_price, 0.0),
        "income": np.where(respond_i, base["income_elasticity"] * scale * d_income, 0.0),
        "respond_price": respond_p,
        "respond_income": respond_i,
        "covered": covered,
        "d_price": d_price,
        "d_income": d_income,
    }


def _net_income_rise(sim, year, extra):
    """The rise in household net income on the reform simulation when earnings rise by ``extra``."""
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
    return float(MicroSeries(after - before, weights=hh_weights).sum())


def hours_response(sim, year, base, ref, scale, group="at_or_below_limit", displacement=FREE_HOURS_DISPLACEMENT):
    """Each part's extra hours, earnings and exchequer offset at one elasticity scale, and the net.

    Keys: ``{price,income}_{earnings,ftes,offset}``, the net ``earnings``, ``ftes`` and
    ``offset`` (price + income), and diagnostics. Offsets are positive when money comes
    back to the Exchequer: the price effect's is positive or zero, the income effect's
    negative or zero.
    """
    if group not in GROUPS:
        raise ValueError(group)
    s = earnings_shares(base, ref, scale, group, displacement)
    emp, w = base["employment_income"], base["weights"]

    def total(x):
        return float(MicroSeries(x, weights=w).sum())

    out = {}
    for part in COMPONENTS:
        extra = emp * s[part]
        earnings = total(extra)
        out[f"{part}_earnings"] = earnings
        out[f"{part}_ftes"] = total(base["weekly_hours"] * s[part]) / FULL_TIME_HOURS
        out[f"{part}_offset"] = earnings - _net_income_rise(sim, year, extra) if np.any(extra) else 0.0
    for k in ("earnings", "ftes", "offset"):
        out[k] = out[f"price_{k}"] + out[f"income_{k}"]
    rp, ri = s["respond_price"], s["respond_income"]
    out.update({
        "workers": total(ri.astype(float)),
        "workers_paying": total(rp.astype(float)),
        "workers_price_falls": total((rp & (s["d_price"] < 0)).astype(float)),
        "workers_fully_covered": total(s["covered"].astype(float)),
        "mean_price_change": float(MicroSeries(s["d_price"][rp], weights=w[rp]).mean()) if rp.any() else 0.0,
        "mean_income_change": float(MicroSeries(s["d_income"][ri], weights=w[ri]).mean()) if ri.any() else 0.0,
    })
    return out
