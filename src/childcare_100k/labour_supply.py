"""Labour supply response to removing the £100,000 limit: who moves into work.

Ported from PolicyEngine/free-childcare-reform (``labour_supply.py``), adapted to
this reform and to policyengine-uk 2.102.3.

What is taken from policyengine-uk, and what is replaced
========================================================

free-childcare-reform replaced three parts of ``policyengine_uk.dynamics.participation``
because of upstream bugs. In policyengine-uk 2.102.3 (the version policyengine.py 6.2.1
certifies) two of them are fixed, so only the third is ported:

1. ``impute_wages_for_nonworkers`` divided annual ``hours_worked`` by 52 a second
   time (an hourly wage of about £0.43). **Fixed upstream**: ``hourly_wage`` now
   divides annual earnings by annual hours once (mean annual hours among workers on
   this release: 1,889). The upstream imputation is used as it is: the median
   hourly wage of workers of the same sex and ten-year age band, times 18.8 hours a
   week.
2. ``calculate_earnings_quintile`` ranked everyone, children included, so its
   bottom quintiles held no earners. **Fixed upstream**: thresholds are now the
   weighted quintiles of working adults' earnings. The upstream function is used as
   it is, which places a non-worker on the full-time equivalent of their imputed
   earnings (free-childcare-reform placed them on the 18.8-hour figure, which puts
   them lower in the table and roughly doubles their elasticity; that is inside
   this module's high bound, which doubles every elasticity).
3. No childcare cost is imputed for someone entering work, and the gain to work is
   measured on ``household_net_income``, which does not net off childcare. **Still
   missing upstream**, so ported: :func:`imputed_childcare_cost` and
   :func:`gain_to_work`.

Also kept from the port, because upstream still lacks them: responses are expected
values (each person's probability change times their weight) rather than a seeded
draw; ``calculate_participation_elasticities`` and
``calculate_excluded_from_labour_supply_responses`` read the simulation's default
period, so the elasticities are computed with the default period moved to the
costed year (:func:`elasticities`), and the exclusions are restated for an explicit
year (:func:`excluded`).

The responding population
=========================

Every adult (the first two in each benefit unit, not self-employed, students, disabled
(receiving DLA or PIP) or aged 60 and over: the OBR's exclusions, Table A4) in a
benefit unit whose youngest child is under 12 and in which at least one adult's income,
as the limits test it (adjusted net income less salary sacrifice returned to pay,
``corrections.py``), is over £100,000 in the baseline: the parent over the limit as
well as their partner. Under 12 because Tax-Free Childcare runs to 11 and contains the
30 hours' 9 months-4 years band: following Brewer et al., a parent whose *youngest*
child is in the band is the one the support frees to work. The over-£100,000 condition
is where the reform changes anything. Outside this population the reform leaves the
gain to work unchanged, which the job checks and records.

Who can respond on each margin follows from the population: moving into work (this
module) is open to its non-workers, in practice the partner of someone over the limit,
who today gains no childcare support by working and under the reform brings the family
the 30 hours and Tax-Free Childcare by doing so; the hours response
(``hours_response.py``) is open to its adults in work, at or below the limit and over it.

The gain to work
================

    gain to work = in-work net income - childcare paid while working
                 - (out-of-work net income - childcare support a non-worker keeps)

with every net income recomputed by the model with the adult's earnings switched off
and on. For someone not working today, the childcare they would buy is imputed
(:func:`imputed_childcare_cost`) and the Tax-Free Childcare the scenario would pay on
it is computed from the model's own in-work eligibility (:func:`gain_to_work`). The
30 funded hours reach them through the model itself: in-work income includes them
when the family qualifies.

The exchequer gains an entrant's earnings less the rise in their household's net
income on the reform's tax-benefit system (tax and National Insurance paid, plus
childcare support the family now receives), less the Tax-Free Childcare top-up on
the care they start buying. That can be negative: under this reform an entrant's
family typically becomes eligible for both schemes.

Not modelled: bunching, parents who today keep their income at or below £100,000 and
would earn more without the limit.
"""

from __future__ import annotations

import gc

import numpy as np
import pandas as pd
from microdf import MicroSeries
from policyengine_uk.dynamics.participation import (
    calculate_earnings_quintile,
    calculate_participation_elasticities,
    impute_wages_for_nonworkers,
)
from policyengine_uk.dynamics.progression import calculate_labour_net_income_elasticities

from .config import (
    BASELINE_LIMIT,
    ELASTICITY_SCALES,
    FREE_HOURS_DISPLACEMENT_RANGE,
    FULL_TIME_HOURS,
    HOURS_FOR_NEW_ENTRANTS,
    LSR_WEEKS_PER_YEAR,
    PARTICIPATION_CHANGE_BOUND,
    YEARS,
    YOUNGEST_CHILD_MAX_AGE,
)

COUNT_ADULTS = 2
# A gain to work that changes by less than this (£ a year) is treated as unchanged when
# checking that the reform moves nobody outside the responding population.
UNCHANGED = 1.0


def values(sim, variable, year, to=None):
    """A variable as a plain float or string array (MicroSeries on dataset runs, arrays on situations)."""
    result = sim.calculate(variable, year, map_to=to) if to else sim.calculate(variable, year)
    return np.asarray(getattr(result, "values", result))


def per_person(sim, year, benunit_values):
    """A benefit-unit value on each of its members, by benefit-unit id (an exact join)."""
    benunit_ids = values(sim, "benunit_id", year)
    person_ids = values(sim, "benunit_id", year, "person")
    if len(set(benunit_ids)) != len(benunit_ids):
        raise ValueError("benunit_id is not unique")
    lookup = pd.Series(np.asarray(benunit_values, float), index=benunit_ids)
    out = lookup.reindex(person_ids).to_numpy()
    if np.isnan(out).any():
        raise ValueError("a person's benefit unit is missing from the join")
    return out


def benunit_max(sim, year, person_values):
    """The largest member value in each benefit unit, on each member."""
    person_ids = values(sim, "benunit_id", year, "person")
    s = pd.Series(np.asarray(person_values, float))
    return s.groupby(person_ids).transform("max").to_numpy()


def excluded(sim, year):
    """Adults the OBR framework holds outside the response, for an explicit year."""
    status = values(sim, "employment_status", year).astype(str)
    age = values(sim, "age", year).astype(float)
    adult_index = values(sim, "adult_index", year).astype(float)
    # OBR Table A4 also holds disabled people outside the participation response; the
    # model's disability flag is receipt of DLA or PIP (``is_disabled_for_benefits``).
    disabled = values(sim, "is_disabled_for_benefits", year).astype(bool)
    return (
        np.isin(status, ["FT_SELF_EMPLOYED", "PT_SELF_EMPLOYED", "STUDENT"])
        | disabled
        | (age >= 60)
        | (adult_index == 0)
        | (adult_index > COUNT_ADULTS)
    )


def limit_income(sim, year):
    """Income as the childcare limits test it (corrections.py): ANI less salary sacrifice returned to pay."""
    return values(sim, "adjusted_net_income", year).astype(float) - values(
        sim, "salary_sacrifice_returned_to_income", year
    ).astype(float)


def responding(sim, year):
    """The responding population (module docstring), before the OBR exclusions."""
    youngest = values(sim, "youngest_child_age", year, "person").astype(float)
    adult = values(sim, "adult_index", year).astype(float) > 0
    over = adult & (limit_income(sim, year) > BASELINE_LIMIT)
    family_over = benunit_max(sim, year, over) > 0
    return np.isfinite(youngest) & (youngest <= YOUNGEST_CHILD_MAX_AGE) & family_over


def elasticities(sim, year):
    """OBR Table A1 participation elasticities (upstream), placed on upstream's earnings quintiles.

    ``calculate_participation_elasticities`` reads the simulation's default period, so
    it is moved to the costed year for the call and restored.
    """
    previous = sim.default_calculation_period
    sim.default_calculation_period = year
    try:
        quintile = calculate_earnings_quintile(sim, year, HOURS_FOR_NEW_ENTRANTS)
        return np.asarray(calculate_participation_elasticities(sim, quintile), float)
    finally:
        sim.default_calculation_period = previous


def income_elasticities(sim, year):
    """OBR Table A2 income elasticities of hours (upstream), for the costed year.

    ``calculate_labour_net_income_elasticities`` reads the simulation's default period,
    so it is moved to the costed year for the call and restored.
    """
    previous = sim.default_calculation_period
    sim.default_calculation_period = year
    try:
        return np.asarray(calculate_labour_net_income_elasticities(sim), float)
    finally:
        sim.default_calculation_period = previous


def imputed_childcare_cost(sim, year, respond, actual_cost):
    """Gross childcare a non-worker would buy on entering work (free-childcare-reform's port).

    ``childcare_expenses`` records what a family spends today, which for most
    non-working parents is little or nothing. A potential entrant is given the mean
    spend of working adults whose youngest child is the same age, pro-rated from their
    mean weekly hours to the entrant's 18.8. The same gross cost is used in the
    baseline and the reform; the subsidy on it is scenario-specific (:func:`gain_to_work`).
    """
    employment = values(sim, "employment_income", year).astype(float)
    hours = values(sim, "hours_worked", year).astype(float)
    youngest = values(sim, "youngest_child_age", year, "person").astype(float)
    weights = values(sim, "household_weight", year, "person").astype(float)
    working = employment > 0
    imputed = np.zeros_like(actual_cost, dtype=float)
    for age in np.unique(youngest[respond & ~working & np.isfinite(youngest)]):
        band = youngest == age
        donors = band & working & (hours > 0)
        if not donors.any():
            continue
        mean_cost = float(MicroSeries(actual_cost[donors], weights=weights[donors]).mean())
        mean_weekly_hours = float(MicroSeries(hours[donors], weights=weights[donors]).mean()) / LSR_WEEKS_PER_YEAR
        if mean_weekly_hours > 0:
            imputed[band & ~working] = mean_cost * HOURS_FOR_NEW_ENTRANTS / mean_weekly_hours
    return imputed


def _entrant_subsidy(sim, year, imputed_cost):
    """Tax-Free Childcare the scenario pays on an entrant's imputed childcare, in its in-work state.

    The model's own eligibility (``tax_free_childcare_eligible``, which carries the
    take-up draw and every condition including the income limit), the dataset's routed
    share, the 20% rate and the family's cap, applied to the imputed spend. The cap is
    the model's: for each qualifying child (``tax_free_childcare_qualifying_child``,
    which runs to 16 for a disabled child), the disabled-child amount (£4,000) for a
    disabled or blind child and the standard amount (£2,000) otherwise, both read from
    the model's parameters.
    """
    p = sim.tax_benefit_system.parameters(f"{year}-06-01").gov.hmrc.tax_free_childcare
    eligible = per_person(sim, year, values(sim, "tax_free_childcare_eligible", year).astype(float))
    routed = np.clip(benunit_max(sim, year, values(sim, "tax_free_childcare_spend_routed_share", year)), 0, 1)
    qualifying = values(sim, "tax_free_childcare_qualifying_child", year).astype(bool)
    higher = values(sim, "is_disabled_for_benefits", year).astype(bool) | values(sim, "is_blind", year).astype(bool)
    child_cap = pd.Series(qualifying * np.where(higher, p.contribution.disabled_child, p.contribution.standard_child))
    family_cap = child_cap.groupby(values(sim, "benunit_id", year, "person")).transform("sum").to_numpy()
    top_up = np.minimum(imputed_cost * routed * p.contribution.rate, family_cap)
    return eligible * top_up


def gain_to_work(sim, year, entrant_earnings, actual_cost, imputed_cost):
    """In-work and out-of-work household net income for each of the first two adults, and the gain to work.

    Each adult's employment is switched off, then on (at imputed earnings for a
    non-worker), and the whole system recomputed, as upstream ``calculate_gain_to_work``
    does. Kept local because the childcare terms need values from the same recomputes:
    the Tax-Free Childcare a worker would keep out of work (zero in both scenarios
    here, since it is work-tested, but measured rather than assumed) and the top-up
    on an entrant's imputed childcare.
    """
    original = values(sim, "employment_income", year).astype(float)
    adult_index = values(sim, "adult_index", year).astype(float)
    working = original > 0
    base_income = values(sim, "household_net_income", year, "person").astype(float)
    in_work, out_of_work = base_income.copy(), base_income.copy()
    out_support, entrant_subsidy = np.zeros_like(base_income), np.zeros_like(base_income)

    def recompute(employment):
        sim.reset_calculations()
        sim.set_input("employment_income", year, employment.astype(np.float32))
        return values(sim, "household_net_income", year, "person").astype(float)

    try:
        for index in range(1, COUNT_ADULTS + 1):
            adult = adult_index == index
            if not adult.any():
                continue
            without = original.copy()
            without[adult] = 0
            out_of_work[adult] = recompute(without)[adult]
            tfc = per_person(sim, year, values(sim, "tax_free_childcare", year, "benunit").astype(float))
            out_support[adult] = tfc[adult]

            with_work = original.copy()
            with_work[adult] = np.where(working[adult], original[adult], entrant_earnings[adult])
            in_work[adult] = recompute(with_work)[adult]
            entrant_subsidy[adult] = _entrant_subsidy(sim, year, imputed_cost)[adult]
    finally:
        sim.reset_calculations()
        sim.set_input("employment_income", year, original.astype(np.float32))

    # A worker's recorded cost is gross (its subsidy is already in net income); an
    # entrant's imputed cost is net of the top-up the scenario would pay on it.
    entrant_subsidy = np.where(working, 0.0, entrant_subsidy)
    cost_when_working = np.where(working, actual_cost, imputed_cost - entrant_subsidy)
    gtw = (in_work - cost_when_working) - (out_of_work - np.where(working, out_support, 0.0))
    return {
        "in_work_income": in_work,
        "out_of_work_income": out_of_work,
        "entrant_subsidy": entrant_subsidy,
        "gain_to_work": gtw,
    }


def hours_inputs(sim, year):
    """What the hours margin reads from one scenario (hours_response.py), on each person."""
    from .hours_response import tfc_marginal_rate

    return {
        "bu_tfc": per_person(sim, year, values(sim, "tax_free_childcare", year, "benunit").astype(float)),
        "bu_free": per_person(sim, year, sum(
            values(sim, v, year, "benunit").astype(float)
            for v in ("extended_childcare_entitlement", "universal_childcare_entitlement",
                      "targeted_childcare_entitlement"))),
        "tfc_rate": tfc_marginal_rate(sim, year),
        "hh_net_income": values(sim, "household_net_income", year, "person").astype(float),
    }


def baseline_side(sim, year):
    """Everything the response needs from the baseline simulation, for one year."""
    respond = responding(sim, year)
    eligible = respond & ~excluded(sim, year)
    actual_cost = per_person(sim, year, values(sim, "childcare_expenses", year, "benunit").astype(float))
    entrant_earnings = np.asarray(impute_wages_for_nonworkers(sim, year, HOURS_FOR_NEW_ENTRANTS), float)
    imputed_cost = imputed_childcare_cost(sim, year, eligible, actual_cost)
    elasticity = elasticities(sim, year)
    out = {
        "eligible": eligible,
        "over_limit": limit_income(sim, year) > BASELINE_LIMIT,
        "not_excluded": ~excluded(sim, year),
        "weights": values(sim, "household_weight", year, "person").astype(float),
        "employment_income": values(sim, "employment_income", year).astype(float),
        "weekly_hours": values(sim, "hours_worked", year).astype(float) / LSR_WEEKS_PER_YEAR,
        "entrant_earnings": entrant_earnings,
        "actual_cost": actual_cost,
        "imputed_cost": imputed_cost,
        "elasticity_wrt_income": elasticity,
        # The hours margin (hours_response.py).
        "income_elasticity": income_elasticities(sim, year),
        **hours_inputs(sim, year),
    }
    out.update({f"gtw_{k}": v for k, v in gain_to_work(sim, year, entrant_earnings, actual_cost, imputed_cost).items()})
    return out


def reform_side(sim, year, base):
    """The reform's gain to work, on the baseline's imputed earnings and childcare."""
    out = {f"gtw_{k}": v for k, v in gain_to_work(
        sim, year, base["entrant_earnings"], base["actual_cost"], base["imputed_cost"]).items()}
    out.update(hours_inputs(sim, year))
    return out


def prepare(base, ref):
    """Per-person quantities that do not depend on the elasticity scale."""
    gtw_b, gtw_r = base["gtw_gain_to_work"], ref["gtw_gain_to_work"]
    pct = np.zeros_like(gtw_b)
    positive = gtw_b > 0
    pct[positive] = (gtw_r[positive] - gtw_b[positive]) / gtw_b[positive]
    # Adam and Phillips, Appendix E: an elasticity with respect to in-work income I
    # converts to one with respect to the gain to work G as e_G = e_I x G / I (their
    # G = I - O gives the familiar (I - O) / I = 1 - replacement rate). Our gain to work
    # nets off childcare, G = I - C - (O - S_out), and with C and S_out held fixed a
    # change in I moves G one for one, so the consistent factor is G / I for the gain
    # actually used (the baseline's).
    in_work = base["gtw_in_work_income"]
    factor = np.zeros_like(in_work)
    factor[in_work > 0] = gtw_b[in_work > 0] / in_work[in_work > 0]
    elasticity = base["elasticity_wrt_income"] * np.clip(factor, 0, 1)
    reform_gain = ref["gtw_in_work_income"] - ref["gtw_out_of_work_income"]
    # Outside the responding population the reform must leave the gain to work alone.
    outside = base["not_excluded"] & ~base["eligible"]
    moved_outside = outside & (np.abs(gtw_r - gtw_b) > UNCHANGED)
    return {
        "pct": pct,
        "elasticity": elasticity,
        "reform_gain": reform_gain,
        "entrant_subsidy": ref["gtw_entrant_subsidy"],
        "eligible": base["eligible"],
        "over_limit": base["over_limit"],
        "weights": base["weights"],
        "employment_income": base["employment_income"],
        "weekly_hours": base["weekly_hours"],
        "entrant_earnings": base["entrant_earnings"],
        "moved_outside_weighted": float(MicroSeries(moved_outside.astype(float), weights=base["weights"]).sum()),
        "moved_outside_records": int(moved_outside.sum()),
    }


def participation_response(prep, scale):
    """Expected entrants, leavers, full-time equivalents, earnings and exchequer offset at one scale.

    The OBR elasticity (Adam and Phillips, Appendix E) is the percentage change in the
    probability of working for a percentage change in the gain to work, so for a group
    with employment rate P the employed share rises by P x e x dG/G. Adam and Phillips
    apply it by reweighting the *working* records: new employment is the weighted sum,
    over workers, of their own e x dG/G. Applying e x dG/G to each non-worker instead
    gives (1 - P) x e x dG/G, too few for any group with more workers than non-workers.

    So the number of entrants is the sum over eligible workers of their positive
    e x dG/G (a worker whose gain falls leaves with probability e x |dG/G|, as before).
    Who enters is a non-worker, so those entrants are given the earnings, gain and
    subsidy of the eligible non-workers, shared in proportion to each non-worker's own
    weighted e x dG/G; no non-worker's probability may exceed 1.
    """
    w = prep["weights"]
    emp = prep["employment_income"]
    change = np.where(prep["eligible"], prep["elasticity"] * scale * prep["pct"], 0.0)
    change = np.clip(change, -PARTICIPATION_CHANGE_BOUND, PARTICIPATION_CHANGE_BOUND)
    working = emp > 0

    def total(x):
        return float(MicroSeries(x, weights=w).sum())

    implied = total(np.where(prep["eligible"] & working, np.maximum(change, 0), 0.0))
    pull = np.where(prep["eligible"] & ~working, np.maximum(change, 0), 0.0)
    pull_total = total(pull)
    enter = pull * (implied / pull_total) if pull_total > 0 else np.zeros_like(pull)
    capped = enter > 1
    enter = np.minimum(enter, 1.0)
    leave = np.where(prep["eligible"] & working, np.maximum(-change, 0), 0.0)

    earnings = prep["entrant_earnings"]
    gain = prep["reform_gain"]
    return {
        "entrants": total(enter),
        "leavers": total(leave),
        "ftes": total(enter) * HOURS_FOR_NEW_ENTRANTS / FULL_TIME_HOURS
        - total(leave * prep["weekly_hours"] / FULL_TIME_HOURS),
        "earnings": total(enter * earnings) - total(leave * emp),
        # Tax and NI paid and support withdrawn, less the support the family now gets.
        "offset": total(enter * (earnings - gain - prep["entrant_subsidy"])) - total(leave * (emp - gain)),
        "tax_and_ni": total(enter * (earnings - gain)) - total(leave * (emp - gain)),
        "bound_binding": total((np.abs(change) >= PARTICIPATION_CHANGE_BOUND) & prep["eligible"]),
        # Diagnostics: the new employment implied by the workers' records, the part implied by
        # workers over £100,000, and what the old non-worker-only rule would have given.
        "implied_entrants": implied,
        "implied_by_over_limit": total(np.where(prep["eligible"] & working & prep["over_limit"], np.maximum(change, 0), 0.0)),
        "non_worker_rule_entrants": pull_total,
        "entry_capped": total(capped.astype(float)),
    }


def run(build_simulation, log=print):
    """The labour supply job: baseline then reform simulation (one in memory at a time), every year.

    ``build_simulation(scenario)`` returns a corrected policyengine.py simulation
    (engine._simulation). Returns flat arrays for the run cache: ``{year}/{margin}/{bound}/{metric}``.
    """
    from .hours_response import GROUPS, hours_response

    sim = build_simulation("baseline")
    base = {}
    for y in YEARS:
        log(f"    labour supply {y}: baseline gain to work")
        base[y] = baseline_side(sim, y)
    del sim
    gc.collect()

    sim = build_simulation("reform")
    arrays = {}
    for y in YEARS:
        log(f"    labour supply {y}: reform gain to work and hours")
        ref = reform_side(sim, y, base[y])
        prep = prepare(base[y], ref)
        arrays[f"{y}/responding_adults"] = float(MicroSeries(prep["eligible"].astype(float), weights=prep["weights"]).sum())
        arrays[f"{y}/responding_records"] = int(prep["eligible"].sum())
        arrays[f"{y}/moved_outside_weighted"] = prep["moved_outside_weighted"]
        arrays[f"{y}/moved_outside_records"] = prep["moved_outside_records"]
        for bound, scale in ELASTICITY_SCALES.items():
            for k, v in participation_response(prep, scale).items():
                arrays[f"{y}/extensive/{bound}/{k}"] = v
            for k, v in hours_response(sim, y, base[y], ref, scale, "at_or_below_limit").items():
                arrays[f"{y}/intensive/{bound}/{k}"] = v
            for k, v in hours_response(sim, y, base[y], ref, scale, "over_limit").items():
                arrays[f"{y}/intensive_over_limit/{bound}/{k}"] = v
        # The displacement assumption varied on its own, at central elasticities, both groups summed
        # (hours_response.py): it sets which families' paid care the newly funded hours fully cover.
        for side, displacement in FREE_HOURS_DISPLACEMENT_RANGE.items():
            parts = [hours_response(sim, y, base[y], ref, 1.0, g, displacement) for g in GROUPS]
            for k in parts[0]:
                arrays[f"{y}/intensive_displacement/{side}/{k}"] = sum(p[k] for p in parts)
    del sim
    gc.collect()
    return arrays
