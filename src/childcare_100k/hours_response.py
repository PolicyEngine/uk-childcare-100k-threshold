"""Hours response of parents in work: a price effect and an income effect.

policyengine-uk's intensive-margin machinery is driven by changes in marginal tax rates
and net income; it does not see a change in the price of childcare, an input to
working. The reform changes two things for an adult in work in the responding
population (``labour_supply.responding``, after the OBR progression model's exclusions,
Table A3, which unlike the participation model's do not include disabled people),
whatever their own income, so the hours response has two parts, reported for the adults
at or below £100,000 and the adults over it (``GROUPS``):

    price effect:   earnings change = earnings x HOURS_PRICE_ELASTICITY x change in the
                    marginal price of paid childcare (%)
    income effect:  earnings change = earnings x OBR income elasticity
                    x the household's gain (% of disposable income)

Hours and earnings move together at a constant hourly wage. The exchequer effect is the
model's: the reform simulation is recomputed once with every responding adult's combined
change in earnings (both parts, both groups), and the net offset is the extra earnings
less the rise in household net income (positive is money back). Taxes and benefits are
not additive (a parent near £100,000 crosses the personal-allowance taper), so the parts
are an attribution that adds up to the net exactly: the first group's combined change
recomputed on its own, the second group the remainder; within a group, the price change
recomputed on its own, the income effect the remainder (:func:`hours_response`).

The price effect: what counts as a price change
===============================================

An extra hour of work needs an extra hour of paid childcare. Only a change in what that
*marginal* hour costs the family is a price change; support that does not depend on how
many hours the family buys is a lump sum, which enters through the income effect.

* The marginal net price of paid care is £1 less the cash support the family gets on its
  next £1 of spend, from every payment the model ties to ``childcare_expenses``
  (``CHILDCARE_SUPPORT``). The rate is the model's own: the change in that support when
  the family's childcare spend rises by £1 (:func:`marginal_support_rates`), which
  carries each payment's rules, caps, the eligible part of the year and the take-up draw.
  Tax-Free Childcare pays 20% of each £1 of routed spend (59.3% of spend in this data, so
  about 11.9p per £1) until the child's cap; the Universal Credit childcare element pays
  85% of charges (SI 2013/376 reg 34) up to its cap (reg 36), withdrawn only through the
  taper, so a claimant below the cap gets 85p on its next £1 and one at the cap none.
  The baseline rate is read at today's spend; the reform's at the spend the family still
  makes once the newly funded hours displace paid care (below), the spending the income
  effect assumes (:func:`at_displaced_spend`). So a family whose £11,000 of care puts it at
  the £2,000 Tax-Free Childcare cap today, but which buys £7,710.38 once the funded hours
  displace £3,289.62, faces a 20% marginal rate, not zero; and a London Universal Credit
  family with £27,000 of care, its childcare element capped at £22,033.92 today, is
  £20,153.82 on the £23,710.38 left, below the cap, so its next £1 costs 15p rather than
  £1. Published as sensitivities (``PRICE_BASIS_SENSITIVITIES``): ``original_spend``, the
  reform's rate at today's spend, and ``tfc_only``, Tax-Free Childcare alone (the rule
  before A8).
* The 30 funded hours are a fixed number of hours, conditional only on both parents
  passing the minimum earnings test. For a family that still buys paid care on top of
  the newly funded hours, the funded hours do not change the price of the marginal hour
  (it is still bought at the full price, less any Tax-Free Childcare): they are
  inframarginal, a lump sum. Only where the newly funded hours cover all the paid care
  the family buys do they make the marginal hour free (a 100% fall, the setting in which
  Brewer et al. estimate the elasticity: a move from part-time to full-time free care).
  ``childcare_expenses`` is an annual spend, not hours, so the test is on value: the
  family is fully covered if newly funded hours, displacing paid care at
  ``FREE_HOURS_DISPLACEMENT`` (90.5%) of their value, are worth more than its spend
  (exactly its spend covers the hours bought, not the next one).
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
whose youngest child is 0-2, -0.05 for a man in a couple; a couple is married or
cohabiting, ``labour_supply.CoupleView``) applied as policyengine-uk's
``apply_progression_responses`` does: earnings change = earnings x elasticity x
(the household's gain) / its baseline income, the relative change clipped to +/-100%.
Responding: every adult in work in the responding population.

The OBR applies the elasticities to a change in cash income. The funded hours are not
cash: what they put in a family's pocket is the paid childcare they replace. So the gain
(:func:`income_gain`) is, on one resource definition throughout, the change in
disposable income (``hbai_household_net_income``, static, before any response: cash
benefits and taxes, Tax-Free Childcare included, funded hours not) plus the paid care
the newly funded hours displace (:func:`paid_care_saving`: their funding value x
``FREE_HOURS_DISPLACEMENT``, the price rule's assumption, capped at what the family
spends today), as a percentage of baseline disposable income. The reform's disposable
income is the model's, recomputed with each child's ``childcare_expenses`` lowered in
proportion to the family's displaced spend (:func:`at_displaced_spend`): the family no
longer pays for that care, so every cash payment tied to childcare spending falls with
it together, Tax-Free Childcare (the top-up on the displaced spend) and the Universal
Credit childcare element (85% of charges paid, SI 2013/376 reg 34(1)) among them. Published
as sensitivities (``INCOME_BASIS_SENSITIVITIES``): ``paid_care_fixed_spend``, the same
gain with spending held fixed, so that support on the displaced spend is kept; and
``government_cost``, the change in ``household_net_income``, which values the funded
hours at what the government pays for them, over the same base. The base is disposable income rather than
``household_net_income``, which also deducts policyengine-uk's expected stamp duty
(``income_change``).

The elasticity, -0.042, is an extrapolated scenario assumption, not an estimated price
elasticity. Brewer et al. (IFS WP20/09) estimate +0.600 weekly hours (on a mean of
14.319, zeros for non-workers included) for mothers whose youngest child becomes
eligible for full-time rather than part-time free care; dividing that by a 100% price
fall and applying it to every working adult with a child under 12 extends it to other
interventions, parents and child ages it was not estimated on. It is a total-hours
effect, so it also overlaps with the extensive margin. The low and high bounds scale
both elasticities (``ELASTICITY_SCALES``).

The Universal Credit childcare element, like the Tax-Free Childcare top-up, enters both
parts: the income effect through the recomputed disposable income at displaced spend, and
the price effect where the reform's lower spend changes its rate on the next £1 (below its
cap rather than at it).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from microdf import MicroSeries

from .config import (
    FREE_HOURS_DISPLACEMENT,
    FREE_HOURS_DISPLACEMENT_RANGE,
    FULL_TIME_HOURS,
    HOURS_PRICE_ELASTICITY,
    INCOME_BASIS,
    PRICE_BASIS,
)
from .labour_supply import values

# Who responds, split by their own income as the limits test it. Both groups use the same rules.
GROUPS = ("at_or_below_limit", "over_limit")
COMPONENTS = ("price", "income")
# The family's extra childcare spend (£, split across its children in proportion to their spend) used to read
# the model's marginal childcare support rates: the next £1, the claimed marginal unit (C3).
PRICE_STEP = 1.0
# The cash payments policyengine-uk ties to ``childcare_expenses`` (each summed to the family): Tax-Free
# Childcare, Universal Credit (its childcare element, 85% of charges up to the reg 36 cap), the legacy
# Working Tax Credit childcare element (and Child Tax Credit, tapered jointly with it), Housing Benefit's
# childcare disregard and the student Childcare Grant. Their change when spend rises is the support on the
# family's next £1 of paid care.
CHILDCARE_SUPPORT = ("tax_free_childcare", "universal_credit", "working_tax_credit", "child_tax_credit",
                     "housing_benefit", "childcare_grant")


def _family(sim, year, variable):
    from .labour_supply import per_person

    return per_person(sim, year, values(sim, variable, year, "benunit").astype(float))


def _support(sim, year):
    """(the family's Tax-Free Childcare, its childcare-linked cash support in all), on each member."""
    tfc = _family(sim, year, "tax_free_childcare")
    return tfc, tfc + sum(_family(sim, year, v) for v in CHILDCARE_SUPPORT if v != "tax_free_childcare")


def _rates(before, after, bu_spend):
    """Marginal support per £1: the support after spend rises by ``PRICE_STEP`` less before, clipped to [0, 1]."""
    rate = np.divide(after - before, PRICE_STEP, out=np.zeros_like(bu_spend), where=bu_spend > 0)
    return np.clip(rate, 0.0, 1.0)


def marginal_support_rates(sim, year, kept=None):
    """The family's marginal Tax-Free Childcare rate and its marginal childcare support rate (on each member).

    The support paid on the family's next £1 of childcare spend, the model's own: every
    person's ``childcare_expenses`` (scaled by ``kept``, the share of spend the family still
    makes, if given) is raised by that person's share of the family's spend times
    ``PRICE_STEP`` (£1), so the family buys £1 more care, split across its children in
    proportion to what each already costs, and the family's cash support recomputed; each
    rate is the change in support per £1 (0 where the family spends nothing). An absolute
    £1 step, not a proportional one, so near a cap (the Universal Credit childcare
    element's, reg 36, or a child's Tax-Free Childcare cap) the rate is the one on the
    marginal pound, not an average over spending mostly beyond the cap. ``tfc_rate``
    counts Tax-Free Childcare alone; ``support_rate`` every payment in
    ``CHILDCARE_SUPPORT``, so a Universal Credit family below its childcare-element cap
    gets 85p per £1, one at the cap none. policyengine-uk computes in float32, so a £1
    step reads each rate to within about 1.2e-7 x the support level (under 0.3p per £1 for a
    £22,000 Universal Credit childcare element, under 0.03p for Tax-Free Childcare), against
    rates of 12p to 85p; zero support is exact. Returns ``(rates, support at the spend)``;
    the simulation is restored afterwards.
    """
    spend = values(sim, "childcare_expenses", year).astype(np.float64)
    kept = np.ones_like(spend) if kept is None else np.asarray(kept, np.float64)
    at = spend * kept
    try:
        sim.reset_calculations()
        sim.set_input("childcare_expenses", year, at)
        bu_spend = _family(sim, year, "childcare_expenses")
        tfc, support = _support(sim, year)
        at_spend = {"bu_tfc": tfc, "hh_disposable_income": values(
            sim, "hbai_household_net_income", year, "person").astype(float)}
        share = np.divide(at, bu_spend, out=np.zeros_like(at), where=bu_spend > 0)
        sim.reset_calculations()
        sim.set_input("childcare_expenses", year, at + share * PRICE_STEP)
        tfc_up, support_up = _support(sim, year)
    finally:
        sim.reset_calculations()
        sim.set_input("childcare_expenses", year, spend.astype(np.float32))
    rates = {"tfc_rate": _rates(tfc, tfc_up, bu_spend), "support_rate": _rates(support, support_up, bu_spend)}
    return rates, at_spend


def tfc_marginal_rate(sim, year):
    """Tax-Free Childcare paid on the family's next £1 of childcare spend (on each member), the model's own."""
    return marginal_support_rates(sim, year)[0]["tfc_rate"]


def marginal_price_change(base, ref, displacement=FREE_HOURS_DISPLACEMENT, price_basis=PRICE_BASIS):
    """Proportional change in the net price of the family's marginal £1 of paid care, and who is fully covered.

    The net price of the next £1 is 1 less the childcare-linked cash support it attracts
    (``support_rate``: Tax-Free Childcare, the Universal Credit childcare element and the
    rest of ``CHILDCARE_SUPPORT``). Baseline: at the family's spend today. Reform: zero if
    newly funded hours (at ``displacement`` of their value) more than cover all the
    family's paid care, otherwise 1 less the reform's support rate:
    ``remaining_spend`` (central), at the paid care the family still buys once the funded
    hours displace some of it, the spending the central income gain assumes (so a
    Universal Credit family that the displacement moves below its childcare-element cap
    gets 85p off its next £1); ``original_spend`` (a sensitivity), at the family's spend
    today; ``tfc_only`` (a sensitivity), Tax-Free Childcare alone at both states, the
    reform's at the remaining spend (the rule before A8). Funded value exactly equal to the
    spend covers the hours the family buys and no more: the next hour lies beyond the fixed
    entitlement and is bought at the full price, so the test is strict.
    """
    expenses = base["actual_cost"]
    covered = (expenses > 0) & (newly_funded_value(base, ref) * displacement > expenses)
    if price_basis == "remaining_spend":
        key, reform_rate = "support_rate", displaced(ref, displacement)["support_rate"]
    elif price_basis == "original_spend":
        key, reform_rate = "support_rate", ref["support_rate"]
    elif price_basis == "tfc_only":
        key, reform_rate = "tfc_rate", displaced(ref, displacement)["tfc_rate"]
    else:
        raise ValueError(price_basis)
    before = 1.0 - base[key]
    after = np.where(covered, 0.0, 1.0 - reform_rate)
    change = np.divide(after - before, before, out=np.zeros_like(before), where=before > 0)
    return covered, np.clip(change, -1.0, 1.0)


def newly_funded_value(base, ref):
    """The family's newly funded hours at their funding value (on each member)."""
    return np.maximum(ref["bu_free"] - base["bu_free"], 0.0)


def _household_total(base, benunit_values):
    """A benefit-unit value summed over the benefit units of each person's household, on each person."""
    n = len(benunit_values)
    benunit_id = base.get("benunit_id", np.arange(n))
    household_id = base.get("household_id", np.arange(n))
    frame = pd.DataFrame({"hh": household_id, "bu": benunit_id, "v": np.asarray(benunit_values, float)})
    per_household = frame.drop_duplicates("bu").groupby("hh")["v"].sum()
    return per_household.reindex(household_id).to_numpy()


def paid_care_saving(base, ref, displacement=FREE_HOURS_DISPLACEMENT):
    """Paid childcare the newly funded hours displace, capped at the family's spend, summed over the household.

    The same displacement as the price rule: newly funded value x ``displacement``, but
    no more than what the family pays for care today.
    """
    saving = np.minimum(newly_funded_value(base, ref) * displacement, base["actual_cost"])
    return _household_total(base, saving)


def displacement_key(displacement):
    """The key a displacement rate's recomputed reform is stored under (``ref["displaced"]``)."""
    return round(float(displacement), 6)


# The displacement rates the hours margin is computed at: central and the sensitivity's ends.
DISPLACEMENTS = (FREE_HOURS_DISPLACEMENT, *FREE_HOURS_DISPLACEMENT_RANGE.values())


def at_displaced_spend(sim, year, base, ref, displacement=FREE_HOURS_DISPLACEMENT):
    """The reform once the paid care the newly funded hours displace is no longer bought (on each member).

    Each person's ``childcare_expenses`` is scaled by 1 - (the family's displaced spend,
    :func:`paid_care_saving` before the household sum) / (the family's spend) and the model
    recomputes, with the routed share, caps, eligibility and every other rule, on the care
    the family still pays for:

    * ``hh_disposable_income``: the household's ``hbai_household_net_income`` (Tax-Free
      Childcare, the Universal Credit childcare element and any other cash support tied
      to childcare spending respond together): the central income gain's
      (:func:`income_gain`);
    * ``bu_tfc``: the family's ``tax_free_childcare``;
    * ``support_rate`` and ``tfc_rate``: the family's marginal childcare support and
      Tax-Free Childcare rates at that remaining spend (:func:`marginal_support_rates`):
      the central price rule's and the ``tfc_only`` sensitivity's
      (:func:`marginal_price_change`).

    The simulation is restored afterwards.
    """
    bu_spend = base["actual_cost"]
    remaining = bu_spend - np.minimum(newly_funded_value(base, ref) * displacement, bu_spend)
    # The baseline's person arrays and the reform's share one person order: a benefit-unit
    # share on each member.
    kept = np.divide(remaining, bu_spend, out=np.ones_like(bu_spend), where=bu_spend > 0)
    rates, out = marginal_support_rates(sim, year, kept)
    return {**out, **rates}


def displaced(ref, displacement=FREE_HOURS_DISPLACEMENT):
    """The reform at displaced spend (:func:`at_displaced_spend`), as stored in ``ref["displaced"]``."""
    return ref["displaced"][displacement_key(displacement)]


def _members(base, group):
    """Adults in work in the group who respond on the hours margin (OBR Table A3 screen)."""
    in_group = base["over_limit"] if group == "over_limit" else ~base["over_limit"]
    return base["hours_eligible"] & in_group & (base["employment_income"] > 0) & (base["weekly_hours"] > 0)


def price_change(base, ref, group="at_or_below_limit", displacement=FREE_HOURS_DISPLACEMENT, price_basis=PRICE_BASIS):
    """Who responds to the price (in work, family pays for childcare) and their marginal price change."""
    covered, change = marginal_price_change(base, ref, displacement, price_basis)
    respond = _members(base, group) & (base["actual_cost"] > 0)
    return respond, np.where(respond, change, 0.0), respond & covered


def income_gain(base, ref, displacement=FREE_HOURS_DISPLACEMENT, basis=INCOME_BASIS):
    """The household's gain from the reform that the income effect responds to (module docstring).

    ``paid_care`` (the central basis): the change in disposable income
    (``hbai_household_net_income``: cash, Tax-Free Childcare and the Universal Credit
    childcare element included, funded hours not), the reform's recomputed at the spend
    left once the newly funded hours displace paid care (:func:`at_displaced_spend`), plus
    the paid childcare they displace (:func:`paid_care_saving`).
    ``paid_care_fixed_spend`` (a sensitivity): the same with spending held fixed, so the
    reform's disposable income keeps the support tied to the displaced spend.
    ``government_cost`` (a sensitivity): the change in ``household_net_income``, which
    counts the funded hours at what the government pays for them.
    """
    if basis in ("paid_care", "paid_care_fixed_spend"):
        reform = displaced(ref, displacement) if basis == "paid_care" else ref
        return reform["hh_disposable_income"] - base["hh_disposable_income"] + paid_care_saving(base, ref, displacement)
    if basis == "government_cost":
        return ref["hh_net_income"] - base["hh_net_income"]
    raise ValueError(basis)


def income_change(base, ref, group="at_or_below_limit", displacement=FREE_HOURS_DISPLACEMENT, basis=INCOME_BASIS):
    """Who responds to income (in work) and the relative change in their household's income.

    The gain is :func:`income_gain`; the base it is a percentage of is the household's
    disposable income, ``hbai_household_net_income``. (``household_net_income`` also
    nets off taxes that are not paid out of the year's income, chiefly policyengine-uk's
    expected stamp duty: for a few high-income households that leaves it near zero or
    negative, which made their percentage change jump from year to year.)
    """
    respond = _members(base, group)
    gain = income_gain(base, ref, displacement, basis)
    income = base["hh_disposable_income"]
    rel = np.divide(gain, income, out=np.zeros_like(income), where=income > 0)
    return respond, np.where(respond, np.clip(rel, -1.0, 1.0), 0.0)


def earnings_shares(base, ref, scale, group="at_or_below_limit", displacement=FREE_HOURS_DISPLACEMENT,
                    basis=INCOME_BASIS, price_basis=PRICE_BASIS):
    """Each part's proportional change in earnings (and hours) for every person, at one elasticity scale."""
    respond_p, d_price, covered = price_change(base, ref, group, displacement, price_basis)
    respond_i, d_income = income_change(base, ref, group, displacement, basis)
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


def _offset(sim, year, extra, weights):
    """Exchequer offset of a change in earnings: the extra earnings less the rise in household net income."""
    if not np.any(extra):
        return 0.0
    return float(MicroSeries(extra, weights=weights).sum()) - _net_income_rise(sim, year, extra)


def hours_response(sim, year, base, ref, scale, displacement=FREE_HOURS_DISPLACEMENT, basis=INCOME_BASIS,
                   price_basis=PRICE_BASIS):
    """The hours response of every responding adult in work at one elasticity scale, by group and in total.

    Returns ``{group: {...} for group in GROUPS}`` and ``"total"``. Each holds
    ``{price,income}_{earnings,ftes,offset}``, the net ``earnings``, ``ftes`` and
    ``offset``, and diagnostics. Offsets are positive when money comes back to the
    Exchequer.

    The net offset is the model's on the combined change in earnings: the reform
    simulation is recomputed once with every responding adult's price and income
    changes together, so the taxes and benefits are those of the hours actually worked
    (computing the parts separately and adding them overstated it where a parent
    crosses a taper, such as the personal allowance's at £100,000). The parts are an
    attribution that adds up to the net exactly: the first group's combined change is
    recomputed on its own, the second group is the remainder, and within each group the
    price effect is its price change recomputed on its own and the income effect is the
    remainder.
    """
    emp, w = base["employment_income"], base["weights"]

    def total(x):
        return float(MicroSeries(x, weights=w).sum())

    shares = {g: earnings_shares(base, ref, scale, g, displacement, basis, price_basis) for g in GROUPS}
    extra = {g: {part: emp * shares[g][part] for part in COMPONENTS} for g in GROUPS}
    combined = {g: extra[g]["price"] + extra[g]["income"] for g in GROUPS}
    net = _offset(sim, year, sum(combined.values()), w)
    group_net = {GROUPS[0]: _offset(sim, year, combined[GROUPS[0]], w)}
    group_net[GROUPS[1]] = net - group_net[GROUPS[0]]

    out = {}
    for g in GROUPS:
        s, o = shares[g], {}
        for part in COMPONENTS:
            o[f"{part}_earnings"] = total(extra[g][part])
            o[f"{part}_ftes"] = total(base["weekly_hours"] * s[part]) / FULL_TIME_HOURS
        o["price_offset"] = _offset(sim, year, extra[g]["price"], w)
        o["income_offset"] = group_net[g] - o["price_offset"]
        o["offset"] = group_net[g]
        o["earnings"] = o["price_earnings"] + o["income_earnings"]
        o["ftes"] = o["price_ftes"] + o["income_ftes"]
        rp, ri = s["respond_price"], s["respond_income"]
        o.update({
            "workers": total(ri.astype(float)),
            "workers_paying": total(rp.astype(float)),
            "workers_price_falls": total((rp & (s["d_price"] < 0)).astype(float)),
            "workers_fully_covered": total(s["covered"].astype(float)),
            "mean_price_change": float(MicroSeries(s["d_price"][rp], weights=w[rp]).mean()) if rp.any() else 0.0,
            "mean_income_change": float(MicroSeries(s["d_income"][ri], weights=w[ri]).mean()) if ri.any() else 0.0,
        })
        out[g] = o
    out["total"] = {k: sum(out[g][k] for g in GROUPS) for k in out[GROUPS[0]] if not k.startswith("mean_")}
    return out
