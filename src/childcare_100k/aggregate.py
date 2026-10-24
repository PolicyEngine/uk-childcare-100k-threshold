"""Turn the record-level run arrays into the published aggregates.

Every weighted figure is a microdf ``MicroSeries`` sum, mean or share, built from
an entity's values and that entity's weights as ``engine.extract`` stored them.
Cross-entity values (a family's flag on its members, a person flag rolled up to
the family) were mapped by the simulation, so nothing here maps records by hand.

Nothing record-level leaves this module. A breakdown cell resting on fewer than
``MIN_CELL_RECORDS`` gaining or changed records is suppressed (published as
null), and a second cell is suppressed with it whenever a lone suppressed cell
could be recovered from a published total. Those record counts are deliberately
unweighted: they measure how many survey records a cell rests on.
"""

import numpy as np
from microdf import MicroSeries

from .config import (
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    EXPECTED_SCENARIOS,
    FAMILY_TYPES,
    FREE_HOURS_DISPLACEMENT_RANGE,
    FREE_HOURS_VARIABLES,
    GAIN_THRESHOLD,
    INCOME_BASIS_SENSITIVITIES,
    LEAD_YEAR,
    MIN_CELL_RECORDS,
    PRICE_BASIS_SENSITIVITIES,
    REGIONS,
    TAKE_UP_BASES,
    TFC_TAKE_UP_NEWLY_ELIGIBLE_LOW,
    VALIDATION_YEAR,
    YEARS,
)
from .engine import load_meta, run_path

BN = 1e9
# Share of the responding adults the reform may move outside the labour supply population (labour_supply).
MOVED_OUTSIDE_TOLERANCE = 0.002
AGE_BANDS = [("0-1", 0, 2), ("2", 2, 3), ("3-4", 3, 5), ("5-11", 5, 12), ("12+", 12, 200)]

# The low end's adjustment (see ``sensitivities``).
ROUTED_LOW = "tfc_routed_share"


class Run:
    """One scenario's arrays, refused unless its provenance matches the current data, code and versions."""

    def __init__(self, scenario):
        load_meta(scenario)  # raises on a provenance mismatch
        self.z = np.load(run_path(scenario))

    def __call__(self, year, name):
        return self.z[f"{year}/{name}"]


def load(scenarios):
    return {s: Run(s) for s in scenarios}


def _bn(x):
    return round(float(x) / BN, 3)


def _k(x):
    """Counts rounded to the nearest thousand."""
    return int(round(float(x) / 1000.0) * 1000)


def _records(mask):
    """Unweighted count of records (for disclosure control only)."""
    return int(np.count_nonzero(mask))


def _weights(base, ref, year, entity):
    """The entity's weights, which must be the same in both runs (same dataset, same records)."""
    w = base(year, f"{entity}_weight")
    if not np.array_equal(w, ref(year, f"{entity}_weight")):
        raise ValueError(f"{year}: {entity} weights differ between the two runs")
    return w


def _hh(values, w):
    return MicroSeries(np.asarray(values, dtype=float), weights=w)


def gross(base, ref, year):
    """Extra spending (£, unrounded) on free hours and TFC top-ups, and the net change in the government balance."""
    w = _weights(base, ref, year, "hh")
    free = _hh(ref(year, "hh_free") - base(year, "hh_free"), w).sum()
    tfc = _hh(ref(year, "hh_tfc") - base(year, "hh_tfc"), w).sum()
    net = -_hh(ref(year, "hh_gov_balance") - base(year, "hh_gov_balance"), w).sum()
    return free, tfc, net


def family_changes(base, ref, year):
    d_free = ref(year, "bu_free") - base(year, "bu_free")
    d_tfc = ref(year, "bu_tfc") - base(year, "bu_tfc")
    return d_free, d_tfc, d_free + d_tfc


def budget_block(runs, years=YEARS, pair=("baseline", "reform")):
    b, r = runs[pair[0]], runs[pair[1]]
    out = {"thirty_hours": {}, "tax_free_childcare": {}, "total": {}, "net_total": {}}
    for y in years:
        free, tfc, net = gross(b, r, y)
        out["thirty_hours"][str(y)] = _bn(free)
        out["tax_free_childcare"][str(y)] = _bn(tfc)
        out["total"][str(y)] = round(out["thirty_hours"][str(y)] + out["tax_free_childcare"][str(y)], 3)
        out["net_total"][str(y)] = _bn(net)
    return out


def thirty_hours_components(runs, years=YEARS, pair=("baseline", "reform"), scale=1.0):
    """The 30-hours leg split by entitlement (£bn): the pair's change times ``scale`` (the take-up rate for the
    claim-all pair, so the extended line is the expected cost). The universal and targeted lines stay at zero."""
    b, r = runs[pair[0]], runs[pair[1]]
    out = {}
    for v in FREE_HOURS_VARIABLES:
        key = v.replace("_childcare_entitlement", "")
        out[key] = {
            str(y): _bn(scale * _hh(r(y, f"hh_{v}") - b(y, f"hh_{v}"), _weights(b, r, y, "hh")).sum()) for y in years
        }
    return out


def sensitivities(runs, years=YEARS):
    """Each adjustment's effect on the gross total (£bn, + raises the cost), and the low/high range.

    ``low = central + tfc_routed_share`` (only 58% of childcare spending through a Tax-Free
    Childcare account) and ``high = central + full_30_hour_usage``. Every pair nets the new
    funded hours off childcare spending in its reform (engine.net_new_hours), so each effect
    is on the same basis as the central figure.
    """
    eff = {k: {} for k in ("full_30_hour_usage", ROUTED_LOW)}
    low, central, high = {}, {}, {}
    for y in years:
        c = sum(gross(runs["baseline"], runs["reform"], y)[:2])
        hours30 = sum(gross(runs["baseline_hours30"], runs["reform_hours30"], y)[:2]) - c
        routed = sum(gross(runs["baseline_routed"], runs["reform_routed"], y)[:2]) - c
        k = str(y)
        eff["full_30_hour_usage"][k] = _bn(hours30)
        eff[ROUTED_LOW][k] = _bn(routed)
        central[k] = _bn(c)
        low[k] = _bn(c + routed)
        high[k] = _bn(c + hours30)
    return {"effects_bn": eff, "range_bn": {"low": low, "central": central, "high": high}}


def tax_free_childcare_leg(runs, years=YEARS):
    """The Tax-Free Childcare leg (£bn): central (new funded hours netted off spending), before that netting, and
    with take-up among newly eligible families at ``TFC_TAKE_UP_NEWLY_ELIGIBLE_LOW``.

    The take-up line is on an expectation basis: the leg with every eligible family claiming in baseline and reform
    (the ``tfc_all`` pair, netted), times the rate. Families eligible today are in both runs of that pair, so their
    top-up does not change; the leg is the newly eligible families'. The baseline is unchanged.
    """
    b, r = runs["baseline"], runs["reform"]
    out = {"central": {}, "before_netting": {}, "take_up_newly_eligible_low": {}, "take_up_newly_eligible_all": {}}
    for y in years:
        w = _weights(b, r, y, "hh")
        k = str(y)
        out["central"][k] = _bn(gross(b, r, y)[1])
        out["before_netting"][k] = _bn(_hh(r(y, "hh_tfc_before_netting") - b(y, "hh_tfc"), w).sum())
        full = gross(runs["baseline_tfc_all"], runs["reform_tfc_all"], y)[1]
        out["take_up_newly_eligible_all"][k] = _bn(full)
        out["take_up_newly_eligible_low"][k] = _bn(TFC_TAKE_UP_NEWLY_ELIGIBLE_LOW * full)
    out["take_up_newly_eligible_low_rate"] = TFC_TAKE_UP_NEWLY_ELIGIBLE_LOW
    return out


def concentration(runs, years=YEARS):
    """How much of the shipped static cost rests on the few largest records, and the gaining cell's Kish effective
    sample size, (sum of weights)^2 / sum of squared weights, over the gaining benefit units."""
    b, r = runs["baseline"], runs["reform"]
    out = {}
    for y in years:
        bw = _weights(b, r, y, "bu")
        _, _, d = family_changes(b, r, y)
        gain = d > GAIN_THRESHOLD
        cost = np.sort((d * bw)[gain])[::-1]
        w = bw[gain]
        out[str(y)] = {
            "gaining_sample_size": int(gain.sum()),
            "top_ten_share_pct": round(float(100 * cost[:10].sum() / cost.sum()), 1),
            "largest_share_pct": round(float(100 * cost[0] / cost.sum()), 1),
            "kish_effective_sample_size": int(round(float(w.sum() ** 2 / (w ** 2).sum()))),
        }
    return out


def parents_over_limit(runs, years=YEARS):
    """Adults with adjusted net income over £100,000 (after pension contributions) and a child under 5 in the family
    (thousands). Ages are whole years, so under-5 includes children under 9 months; CenTax's ~200,000 counts parents
    of a child aged 9 months to 4."""
    b = runs["baseline"]
    out = {}
    for y in years:
        pw = b(y, "p_weight")
        adult = ~b(y, "p_is_child")
        young = b(y, "bu_child_under_5")[b(y, "p_benunit")]
        out[str(y)] = _k(MicroSeries((adult & young & b(y, "p_ani_over")).astype(float), weights=pw).sum())
    return out


def recipients(runs, years=YEARS):
    b, r = runs["baseline"], runs["reform"]
    out = {}
    for y in years:
        bw = _weights(b, r, y, "bu")
        pw = _weights(b, r, y, "p")
        d_free, d_tfc, d = family_changes(b, r, y)
        gain = d > GAIN_THRESHOLD
        # Each child's own change in funded hours and in TFC top-up. A child counts as gaining
        # only if their own value rises: a three-year-old switched from the universal to the
        # extended entitlement with the same hours does not gain, even if a sibling does.
        child = b(y, "p_is_child")
        new_ext = (r(y, "p_free_value") - b(y, "p_free_value")) > GAIN_THRESHOLD
        new_tfc = (r(y, "p_tfc_value") - b(y, "p_tfc_value")) > GAIN_THRESHOLD
        kid_gain = child & (new_ext | new_tfc)
        age = b(y, "p_age")

        def families(mask, w=bw):
            return _k(MicroSeries(mask.astype(float), weights=w).sum())

        def people(mask, w=pw):
            return _k(MicroSeries(mask.astype(float), weights=w).sum())

        mean_gain = round(float(MicroSeries(d, weights=bw)[gain].mean())) if gain.any() else None
        out[str(y)] = {
            "families_gaining": families(gain),
            "children_gaining": people(kid_gain),
            "by_scheme": {
                "thirty_hours": families(d_free > GAIN_THRESHOLD),
                "tax_free_childcare": families(d_tfc > GAIN_THRESHOLD),
            },
            "children_by_scheme": {
                "thirty_hours": people(child & new_ext),
                "tax_free_childcare": people(child & new_tfc),
            },
            "children_gaining_by_age": {
                band: people(kid_gain & (age >= lo) & (age < hi)) for band, lo, hi in AGE_BANDS
            },
            # Null (and flagged) when no family gains: a mean over nobody is not zero.
            "mean_gain_gbp": mean_gain,
            "mean_gain_suppressed": mean_gain is None,
            "families_losing": families(d < -GAIN_THRESHOLD),
        }
    return out


def _cell_ok(*n_records):
    """A cell is publishable when every count it rests on is zero or at least ``MIN_CELL_RECORDS``.

    Pass the gaining records and the records whose value changes at all (gaining or losing):
    a cell with no gainers but one losing record would otherwise publish that record's loss.
    """
    return all(n == 0 or n >= MIN_CELL_RECORDS for n in n_records)


_LABELS = ("decile", "region", "family_type", "group", "higher_earner")


def _suppress(cell):
    out = {k: (v if k in _LABELS else None) for k, v in cell.items()}
    out["suppressed"] = True
    return out


def _complement(cells, sizes):
    """Complementary suppression across cells that sum to a published total.

    If exactly one cell is suppressed, its value could be recovered as the published total
    less the others, so the smallest other cell with a nonzero change is suppressed too.
    ``sizes`` gives each cell's count of changed records (zero-change cells are skipped:
    suppressing a known zero would not protect anything). If no such cell exists, the whole
    breakdown is suppressed rather than published with a recoverable cell.
    """
    if sum(c["suppressed"] for c in cells) != 1:
        return cells
    candidates = [i for i, c in enumerate(cells) if not c["suppressed"] and sizes[i] > 0]
    if not candidates:
        return [_suppress(c) for c in cells]
    i = min(candidates, key=lambda j: sizes[j])
    cells[i] = _suppress(cells[i])
    return cells


def _groups(label, groups, bu_code, spend, fam_gain, bu_gain, bu_changed):
    """Total extra spending and families gaining for each group of benefit units, suppressed like the other breakdowns.

    Both measures rest on benefit units (a benefit unit's weight is its household's), so one
    gaining and one changed count gate each cell.
    """
    cells, sizes = [], []
    for i, name in enumerate(groups.values()):
        m = bu_code == i
        n_gain, n_changed = _records(bu_gain & m), _records(bu_changed & m)
        sizes.append(n_changed)
        if not _cell_ok(n_gain, n_changed):
            cells.append({label: name, "total_change_bn": None, "families_gaining": None, "suppressed": True})
            continue
        cells.append({
            label: name,
            "total_change_bn": _bn(spend[m].sum()),
            "families_gaining": _k(fam_gain[m].sum()),
            "suppressed": False,
        })
    return _complement(cells, sizes)


def distribution(runs, years=YEARS):
    b, r = runs["baseline"], runs["reform"]
    out = {}
    for y in years:
        hw = _weights(b, r, y, "hh")
        bw = _weights(b, r, y, "bu")
        base_inc = MicroSeries(b(y, "hh_net_income").astype(float), weights=hw)
        d_inc = r(y, "hh_net_income") - b(y, "hh_net_income")
        change = MicroSeries(d_inc, weights=hw)
        gaining = MicroSeries((d_inc > GAIN_THRESHOLD).astype(float), weights=hw)
        decile = b(y, "hh_decile")
        changed = np.abs(d_inc) > GAIN_THRESHOLD
        rows, row_sizes = [], []
        for dec in range(1, 11):
            m = decile == dec
            n = _records(m & (d_inc > GAIN_THRESHOLD))
            n_changed = _records(m & changed)
            row_sizes.append(n_changed)
            if not _cell_ok(n, n_changed):
                rows.append({"decile": dec, "mean_change_gbp": None, "pct_change": None, "share_gaining_pct": None,
                             "suppressed": True})
                continue
            rows.append({
                "decile": dec,
                "mean_change_gbp": round(float(change[m].mean()), 2),
                "pct_change": round(float(100 * change[m].sum() / base_inc[m].sum()), 3),
                "share_gaining_pct": round(float(100 * gaining[m].mean()), 2),
                "suppressed": False,
            })

        d_bu = family_changes(b, r, y)[2]
        bu_gain = d_bu > GAIN_THRESHOLD
        fam_gain = MicroSeries(bu_gain.astype(float), weights=bw)
        bu_changed = np.abs(d_bu) > GAIN_THRESHOLD
        # The deciles' mean changes and the groups' totals add up to published UK totals,
        # so a lone suppressed cell is protected by suppressing a second one.
        bu_spend = MicroSeries(d_bu, weights=bw)
        out[str(y)] = {
            "by_decile": _complement(rows, row_sizes),
            "by_region": _groups("region", REGIONS, b(y, "bu_region"), bu_spend, fam_gain, bu_gain, bu_changed),
            "by_family_type": _groups(
                "family_type", FAMILY_TYPES, b(y, "bu_family_type"), bu_spend, fam_gain, bu_gain, bu_changed
            ),
        }
    return out


def assumptions(runs, year=VALIDATION_YEAR + 1):
    """Weighted take-up draws, childcare spending and hours usage the model applies (aggregates only).

    The Tax-Free Childcare draw is a claim flag: a family that reports no paid registered childcare
    (``childcare_expenses`` of zero) gets no top-up whatever its flag, so use is the flag share times the
    share reporting spending, roughly.
    """
    b = runs["baseline"]
    w = b(year, "bu_weight")
    young = b(year, "bu_child_under_5")
    under12 = b(year, "bu_child_under_12")
    high = b(year, "bu_any_over")
    spend = b(year, "bu_spend") > 0
    uses = b(year, "bu_tfc") > 0

    def share(flag, m):
        return round(float(100 * MicroSeries(flag.astype(float), weights=w)[m].mean()), 1)

    ext, tfc = b(year, "bu_would_claim_extended"), b(year, "bu_would_claim_tfc")
    return {
        "year": year,
        "would_claim_30_hours_pct": {"families_with_child_under_5": share(ext, young),
                                     "of_which_parent_over_100k": share(ext, young & high)},
        "would_claim_tfc_pct": {"families_with_child_under_12": share(tfc, under12),
                                "of_which_parent_over_100k": share(tfc, under12 & high)},
        "reports_childcare_spend_pct": {"families_with_child_under_12": share(spend, under12),
                                        "of_which_parent_over_100k": share(spend, under12 & high)},
        "uses_tfc_pct": {"families_with_child_under_12": share(uses, under12)},
        "mean_extended_hours_usage": round(
            float(MicroSeries(b(year, "bu_hours_usage").astype(float), weights=w)[young].mean()), 1
        ),
    }


# ── Labour supply (labour_supply.py, hours_response.py) ──────────────────

BOUNDS = ("central", "low", "high")


def _round_to(x, step):
    return int(round(float(x) / step) * step)


def labour_supply(static_total, years=YEARS):
    """The labour supply job's aggregates, and the dynamic cost (static total less both margins' offsets).

    ``static_total`` is the published static gross total by year (``budget["total"]``),
    so the dynamic cost is the published static figure less the published offsets.
    Offsets are £bn a year, positive = money back to the Exchequer.
    """
    from .engine import LABOUR_SUPPLY_JOB
    from .labour_supply import ENTRY_CELL_LEVELS, ENTRY_SENSITIVITIES

    load_meta(LABOUR_SUPPLY_JOB)  # raises on a provenance mismatch
    z = np.load(run_path(LABOUR_SUPPLY_JOB))

    def get(year, margin, bound, metric):
        return float(z[f"{year}/{margin}/{bound}/{metric}"])

    def by_year(margin, metric, fn):
        return {b: {str(y): fn(get(y, margin, b, metric)) for y in years} for b in BOUNDS}

    extensive = {
        "offset_bn": by_year("extensive", "offset", _bn),
        "tax_and_ni_bn": by_year("extensive", "tax_and_ni", _bn),
        "entrants": by_year("extensive", "entrants", lambda x: _round_to(x, 100)),
        "leavers": by_year("extensive", "leavers", lambda x: _round_to(x, 100)),
        "ftes": by_year("extensive", "ftes", lambda x: _round_to(x, 100)),
        "earnings_bn": by_year("extensive", "earnings", _bn),
        # Diagnostics for the participation rule (labour_supply.participation_response): the part of the
        # entrants implied by workers over £100,000, and the entrants the earlier rule (e x dG/G applied to
        # each non-worker) would give.
        "implied_by_over_limit": by_year("extensive", "implied_by_over_limit", lambda x: _round_to(x, 100)),
        "non_worker_rule_entrants": by_year("extensive", "non_worker_rule_entrants", lambda x: _round_to(x, 100)),
        "entry_capped": by_year("extensive", "entry_capped", lambda x: _round_to(x, 100)),
        # Where the implied entrants were placed (labour_supply.allocate_entrants): among non-workers in the
        # same OBR cell, or, where it has none, in a coarser one.
        "allocated_by_cell_level": {level: by_year("extensive", f"allocated_{level}", lambda x: _round_to(x, 100))
                                    for level in ENTRY_CELL_LEVELS},
        # Sensitivities, not in the dynamic cost (labour_supply.ENTRY_SENSITIVITIES), central elasticities: the
        # entrants placed in a coarser cell dropped, or given the earnings of the workers who imply them. Offsets
        # in £m to 0.1 (they are a few £m), with the central offset at the same precision.
        "entry_sensitivity": {
            "central_offset_m": {str(y): round(get(y, "extensive", "central", "offset") / 1e6, 1) for y in years},
            **{name: {
                "offset_m": {str(y): round(float(z[f"{y}/extensive_sensitivity/{name}/offset"]) / 1e6, 1)
                             for y in years},
                "entrants": {str(y): _round_to(z[f"{y}/extensive_sensitivity/{name}/entrants"], 100) for y in years},
                "earnings_bn": {str(y): _bn(float(z[f"{y}/extensive_sensitivity/{name}/earnings"])) for y in years},
            } for name in ENTRY_SENSITIVITIES},
        },
    }
    # Hours response (hours_response.py) of every responding adult in work, split by their own income: a price
    # effect (positive: money back) and an income effect (negative: money out), and the net of the two.
    def group(margin):
        return {
            "offset_bn": by_year(margin, "offset", _bn),
            "price_offset_bn": by_year(margin, "price_offset", _bn),
            "income_offset_bn": by_year(margin, "income_offset", _bn),
            "ftes": by_year(margin, "ftes", lambda x: _round_to(x, 100)),
            "price_ftes": by_year(margin, "price_ftes", lambda x: _round_to(x, 100)),
            "income_ftes": by_year(margin, "income_ftes", lambda x: _round_to(x, 100)),
            "earnings_bn": by_year(margin, "earnings", _bn),
            # Diagnostics (thousands of adults; mean changes in %, among those responding to each).
            "workers": by_year(margin, "workers", _k),
            "workers_paying_for_childcare": by_year(margin, "workers_paying", _k),
            "workers_price_falls": by_year(margin, "workers_price_falls", _k),
            "workers_fully_covered": by_year(margin, "workers_fully_covered", _k),
            "mean_price_change_pct": by_year(margin, "mean_price_change", lambda x: round(100 * x, 1)),
            "mean_income_change_pct": by_year(margin, "mean_income_change", lambda x: round(100 * x, 2)),
        }

    def both(metric, fn):
        return {b: {str(y): fn(get(y, "intensive", b, metric) + get(y, "intensive_over_limit", b, metric))
                    for y in years} for b in BOUNDS}

    intensive = {
        "offset_bn": both("offset", _bn),
        "price_offset_bn": both("price_offset", _bn),
        "income_offset_bn": both("income_offset", _bn),
        "ftes": both("ftes", lambda x: _round_to(x, 100)),
        "earnings_bn": both("earnings", _bn),
        "at_or_below_limit": group("intensive"),
        "over_limit": group("intensive_over_limit"),
    }
    # Sensitivity, not in the dynamic cost: the free-hours displacement assumption (which families' paid care the
    # newly funded hours fully cover) varied alone, central elasticities, both groups.
    intensive_displacement = {
        "offset_bn": {side: {str(y): _bn(float(z[f"{y}/intensive_displacement/{side}/offset"])) for y in years}
                      for side in FREE_HOURS_DISPLACEMENT_RANGE},
        "price_offset_bn": {side: {str(y): _bn(float(z[f"{y}/intensive_displacement/{side}/price_offset"]))
                                   for y in years} for side in FREE_HOURS_DISPLACEMENT_RANGE},
        "displacement": {side: round(v, 4) for side, v in FREE_HOURS_DISPLACEMENT_RANGE.items()},
    }
    # Sensitivities, not in the dynamic cost, central elasticities, both groups: the income effect's gain with
    # spending held fixed (the support on the displaced spend kept) and with the funded hours at government cost
    # (hours_response.income_gain); the price effect's Tax-Free Childcare rate at today's spend
    # (hours_response.marginal_price_change).
    def sensitivity(block, bases):
        return {basis: {f"{k}_bn": {str(y): _bn(float(z[f"{y}/{block}/{basis}/{k}"])) for y in years}
                        for k in ("offset", "price_offset", "income_offset")}
                for basis in bases}

    intensive_income_basis = sensitivity("intensive_income_basis", INCOME_BASIS_SENSITIVITIES)
    intensive_price_basis = sensitivity("intensive_price_basis", PRICE_BASIS_SENSITIVITIES)
    total = {b: {str(y): round(extensive["offset_bn"][b][str(y)] + intensive["offset_bn"][b][str(y)], 3)
                 for y in years} for b in BOUNDS}
    dynamic = {b: {str(y): round(static_total[str(y)] - total[b][str(y)], 3) for y in years} for b in BOUNDS}
    checks = {}
    for y in years:
        unallocated = max(float(z[f"{y}/extensive/{b}/allocated_unallocated"]) for b in BOUNDS)
        if unallocated > 0:
            raise RuntimeError(f"{y}: {unallocated:,.0f} implied entrants found no non-worker to enter")
        moved = float(z[f"{y}/moved_outside_weighted"])
        # Up to 0.2% of the responding adults may be moved outside the population, and the count is published
        # (adults_moved_outside_population). On Microcosm a133f37a two survey records, about 1,300 weighted
        # adults in 2026-27 and 2027-28 (0.14% of the responding adults; none later), are non-workers whose own
        # income is just under £100,000, so entering work would take them over the limit. The 0.1% guard held
        # on a858c100 (about 100). The fix is to bring them into the population (issue #11), which needs every
        # run redone; until then the guard is raised rather than removed.
        if moved > MOVED_OUTSIDE_TOLERANCE * float(z[f"{y}/responding_adults"]):
            raise RuntimeError(f"{y}: the reform moves the gain to work of {moved:,.0f} adults outside the "
                               "responding population; the population filter misses someone")
        checks[str(y)] = {"responding_adults": _k(z[f"{y}/responding_adults"]),
                          "hours_responding_adults": _k(z[f"{y}/hours_responding_adults"]),
                          "adults_moved_outside_population": _round_to(moved, 100)}
    return {
        "extensive": extensive,
        "intensive": intensive,
        "intensive_displacement": intensive_displacement,
        "intensive_income_basis": intensive_income_basis,
        "intensive_price_basis": intensive_price_basis,
        "total_offset_bn": total,
        "dynamic_cost_bn": dynamic,
        "population": checks,
    }


EARNER_GROUPS = {
    "father": "Father over £100,000",
    "mother": "Mother over £100,000",
    "both": "Both parents over £100,000",
    "lone": "Lone parent over £100,000",
}


def _earner_counts(b, y):
    """Per benefit unit: adults, adults over £100,000, and of those how many are women (baseline)."""
    pb = b(y, "p_benunit")
    adult = ~b(y, "p_is_child")
    over = b(y, "p_ani_over") & adult
    n = len(b(y, "bu_weight"))
    count = lambda flag: np.bincount(pb, weights=flag.astype(float), minlength=n)  # noqa: E731
    return pb, adult, over, count(adult), count(over), count(over & b(y, "p_female"))


def gender(runs, years=YEARS):
    """Families gaining by who is over £100,000, and, among couples with a child under 12 where exactly one
    parent is over £100,000, the share whose other parent has no earnings, by the sex of the higher earner.

    Descriptive and static: it says who the reform reaches, not how anyone's work changes. A couple gains only if
    both parents pass the minimum earnings test, so a family whose other parent does not work gains nothing.
    """
    b, r = runs["baseline"], runs["reform"]
    out = {}
    for y in years:
        bw = _weights(b, r, y, "bu")
        d_bu = family_changes(b, r, y)[2]
        gain = d_bu > GAIN_THRESHOLD
        changed = np.abs(d_bu) > GAIN_THRESHOLD
        pb, adult, over, n_adult, n_over, n_over_f = _earner_counts(b, y)
        groups = {
            "father": (n_adult == 2) & (n_over == 1) & (n_over_f == 0),
            "mother": (n_adult == 2) & (n_over == 1) & (n_over_f == 1),
            "both": (n_adult == 2) & (n_over == 2),
            "lone": (n_adult == 1) & (n_over == 1),
        }
        fam = MicroSeries(gain.astype(float), weights=bw)
        cells, sizes = [], []
        for key, m in groups.items():
            n_gain, n_changed = _records(gain & m), _records(changed & m)
            sizes.append(n_changed)
            if not _cell_ok(n_gain, n_changed):
                cells.append({"group": EARNER_GROUPS[key], "families_gaining": None, "suppressed": True})
                continue
            cells.append({"group": EARNER_GROUPS[key], "families_gaining": _k(fam[m].sum()), "suppressed": False})

        # The other parent in a couple where exactly one parent is over £100,000.
        other_works = np.bincount(pb, weights=(adult & ~over & b(y, "p_in_work")).astype(float), minlength=len(bw)) > 0
        couples = b(y, "bu_child_under_12") & (n_adult == 2) & (n_over == 1)
        partner = []
        for key in ("father", "mother"):
            m = couples & groups[key]
            not_working = m & ~other_works
            n_all, n_nw = _records(m), _records(not_working)
            if not _cell_ok(n_all, n_nw):
                partner.append({"higher_earner": EARNER_GROUPS[key], "families": None, "partner_not_working_pct": None,
                                "suppressed": True})
                continue
            total = MicroSeries(m.astype(float), weights=bw).sum()
            partner.append({
                "higher_earner": EARNER_GROUPS[key],
                "families": _k(total),
                "partner_not_working_pct": round(float(100 * MicroSeries(not_working.astype(float), weights=bw).sum() / total), 1),
                "suppressed": False,
            })
        out[str(y)] = {"families_gaining_by_earner": _complement(cells, sizes), "partner_not_working": partner}
    return out


# ── Take-up bases, bootstrap and age profile (#7; María Juaristi, #8, 23 and 24 October 2026) ──────────


class ExpectedRun(Run):
    """An expected-mode run (expectation.py), refused unless its provenance and that module's hash match."""

    def __init__(self, scenario):
        from .expectation import load_meta as load_expected_meta

        load_expected_meta(scenario)
        self.z = np.load(run_path(scenario))


def load_expected():
    return {s: ExpectedRun(s) for s in EXPECTED_SCENARIOS}


# A person's funded hours or Tax-Free Childcare "changes" in a pair if it moves by more than this (£ a year): float
# noise in the stored values is far below it.
CHANGE_TOLERANCE = 0.005


def dfe_age_rates(rates, dfe_age):
    """Each person's take-up rate from their DfE age (on 31 December of the year), ``rates`` keyed by DfE age.

    NaN at any DfE age ``rates`` does not give (under 0, or 6 and over: no funded hours in the year).
    """
    age = np.asarray(dfe_age)
    out = np.full(age.shape, np.nan)
    for a, rate in rates.items():
        out[age == a] = rate
    return out


def person_changes(expected, year, basis):
    """Each person's change in the basis's pair, if they take up the new hours and if not, and their take-up rate.

    ``hours``: the change in funded hours (all three entitlements), and ``components`` by entitlement, if taken up.
    ``tfc_if_taken``: the change in Tax-Free Childcare with the new hours netted off the person's childcare spending;
    ``tfc_if_not``: with spending before that netting. ``rate``: the chance the person (for a child-level basis) or
    their family (the contract basis) takes up the new hours. A child-level rate is the one for the child's DfE age;
    a person whose hours and Tax-Free Childcare do not depend on it gets 1 (it has no effect), and a person whose
    values change at a DfE age with no rate stops the build.
    """
    spec = TAKE_UP_BASES[basis]
    bc, rc = (expected[s] for s in spec["pair"])
    for k in ("p_id", "p_weight"):
        if not np.array_equal(bc(year, k), rc(year, k)):
            raise ValueError(f"{year}: {k} differs between the runs of {spec['pair']}")
    hours = rc(year, "p_free_value") - bc(year, "p_free_value")
    taken, not_taken = rc(year, "p_tfc_value"), rc(year, "p_tfc_before_netting")
    changed = (np.abs(hours) > CHANGE_TOLERANCE) | (np.abs(taken - not_taken) > CHANGE_TOLERANCE)
    if spec["unit"] == "family":
        rate = np.full(len(hours), spec["rate"])
    else:
        rate = dfe_age_rates(spec["rates_by_dfe_age"], rc(year, "p_dfe_age"))
        if np.isnan(rate[changed]).any():
            raise ValueError(f"{year}: a person whose funded hours change has a DfE age with no {basis} rate")
        rate = np.where(changed, rate, 1.0)
    return {
        "rate": rate,
        "hours": hours,
        "components": {k: rc(year, f"p_free_{k}") - bc(year, f"p_free_{k}") for k in ("extended", "universal", "targeted")},
        "tfc_if_taken": taken - bc(year, "p_tfc_value"),
        "tfc_if_not": not_taken - bc(year, "p_tfc_value"),
    }


def _to_households(run, year, person_values):
    return np.bincount(run(year, "p_household"), weights=person_values, minlength=len(run(year, "hh_weight")))


def household_changes(runs, expected, year):
    """Each household's weighted change in spending (£) on the 30 hours and Tax-Free Childcare, on each basis.

    ``drawn``: the central pair, on the dataset's single take-up draw. ``contract``: the expected mode of #7, the cost
    averaged over the 30-hours take-up draw at the contract rate: every family claims in the claim-all pair, so a newly
    eligible family's 30-hours cost is the rate times its cost there; its Tax-Free Childcare is the netted top-up if
    it claims the new hours and the top-up before netting if it does not, weighted by the rate and one less it. The
    child-level bases (``dfe``, ``centax``): each child's change in the claim-and-use pair times its rate by DfE age,
    and its Tax-Free Childcare netted with the same chance (person_changes). The Tax-Free Childcare draws are held
    as drawn, and so are the hours-usage draws except as each pair sets them.
    """
    b, r = runs["baseline"], runs["reform"]
    w = _weights(b, r, year, "hh")
    out = {"drawn": {"thirty_hours": (r(year, "hh_free") - b(year, "hh_free")) * w,
                     "tax_free_childcare": (r(year, "hh_tfc") - b(year, "hh_tfc")) * w}}
    for basis, spec in TAKE_UP_BASES.items():
        bc, rc = (expected[s] for s in spec["pair"])
        if not np.array_equal(w, _weights(bc, rc, year, "hh")):
            raise ValueError(f"{year}: household weights differ between the drawn pair and {spec['pair']}")
        if spec["unit"] == "family":
            # Household totals, exactly as the expected mode of #7 computed them.
            rate = spec["rate"]
            claim_all = (rc(year, "hh_free") - bc(year, "hh_free")) * w
            tfc = rate * rc(year, "hh_tfc") + (1 - rate) * rc(year, "hh_tfc_before_netting") - bc(year, "hh_tfc")
            out[basis] = {"thirty_hours": rate * claim_all, "tax_free_childcare": tfc * w}
            out[f"{basis}_claim_all_thirty_hours"] = claim_all
            continue
        c = person_changes(expected, year, basis)
        tfc = c["rate"] * c["tfc_if_taken"] + (1 - c["rate"]) * c["tfc_if_not"]
        out[basis] = {"thirty_hours": _to_households(rc, year, c["rate"] * c["hours"]) * w,
                      "tax_free_childcare": _to_households(rc, year, tfc) * w}
    return out


def basis_costs(runs, expected, years=YEARS):
    """Static gross costs (£bn) by year on each take-up basis; for a family-rate basis, also the 30 hours' change per
    0.01 of the rate (£m)."""
    out = {}
    for basis, spec in TAKE_UP_BASES.items():
        out[basis] = {"thirty_hours": {}, "tax_free_childcare": {}, "total": {}}
        if spec["unit"] == "family":
            out[basis]["thirty_hours_per_point_m"] = {}
    for y in years:
        h = household_changes(runs, expected, y)
        k = str(y)
        for basis, spec in TAKE_UP_BASES.items():
            o = out[basis]
            o["thirty_hours"][k] = _bn(h[basis]["thirty_hours"].sum())
            o["tax_free_childcare"][k] = _bn(h[basis]["tax_free_childcare"].sum())
            o["total"][k] = round(o["thirty_hours"][k] + o["tax_free_childcare"][k], 3)
            if spec["unit"] == "family":
                o["thirty_hours_per_point_m"][k] = int(round(float(h[f"{basis}_claim_all_thirty_hours"].sum()) / 100 / 1e6))
    return out


def basis_components(runs, expected, basis, years=YEARS):
    """The 30-hours leg on a take-up basis split by entitlement (£bn): extended, universal and targeted."""
    spec = TAKE_UP_BASES[basis]
    if spec["unit"] == "family":
        return thirty_hours_components({**runs, **expected}, years, pair=spec["pair"], scale=spec["rate"])
    rc = expected[spec["pair"][1]]
    out = {k: {} for k in ("extended", "universal", "targeted")}
    for y in years:
        w = _weights(runs["baseline"], rc, y, "hh")
        c = person_changes(expected, y, basis)
        for k, change in c["components"].items():
            out[k][str(y)] = _bn((_to_households(rc, y, c["rate"] * change) * w).sum())
    return out


CONTRACT_GAP_AGE_GROUPS = {"0": (0,), "1": (1,), "2": (2,), "3-5": (3, 4, 5)}


def contract_gap_by_dfe_age(expected, year=LEAD_YEAR):
    """Why the headline moved from the contract basis to DfE's: the 30 hours' cost on each by DfE age (£m).

    ``every_child_m``: the claim-and-use pair (every family claiming, every child using its hours). ``contract_m``:
    the contract rate on the claim-all pair, where the hours used are the dataset's draws, so at age 0 it also
    carries the under-2 usage draw; ``contract_effective_rate`` is its cost over every child's, the rate it applies
    in effect. ``gap_m``: contract less DfE, by age group, adding up to the gap in the 30 hours' cost.
    """
    contract, dfe = TAKE_UP_BASES["contract"], TAKE_UP_BASES["dfe"]
    bc, rc = (expected[s] for s in contract["pair"])
    use_rc = expected[dfe["pair"][1]]
    if not np.array_equal(rc(year, "p_id"), use_rc(year, "p_id")):
        raise ValueError(f"{year}: people differ between the claim-all and claim-and-use pairs")
    w = rc(year, "p_weight")
    age = rc(year, "p_dfe_age")
    claim_all = (rc(year, "p_free_value") - bc(year, "p_free_value")) * w * contract["rate"]
    c = person_changes(expected, year, "dfe")
    every = c["hours"] * w
    on_dfe = c["rate"] * c["hours"] * w
    out = {"year": year, "every_child_m": {}, "contract_m": {}, "dfe_m": {}, "gap_m": {}, "contract_effective_rate": {}}
    for key, ages in CONTRACT_GAP_AGE_GROUPS.items():
        m = np.isin(age, ages)
        e, k, d = (float(x[m].sum()) / 1e6 for x in (every, claim_all, on_dfe))
        out["every_child_m"][key], out["contract_m"][key], out["dfe_m"][key] = round(e), round(k), round(d)
        out["gap_m"][key] = round(k - d)
        out["contract_effective_rate"][key] = round(k / e, 3) if e > 0 else None
    out["gap_total_m"] = round(float(claim_all.sum() - on_dfe.sum()) / 1e6)
    return out


def _any_member(benunit, chance, n):
    """The chance that at least one member of each benefit unit has an event, members independent."""
    miss = np.clip(1 - chance, 0.0, 1.0)
    certain = np.bincount(benunit, weights=(miss == 0).astype(float), minlength=n) > 0
    log_miss = np.bincount(benunit, weights=np.log(np.where(miss > 0, miss, 1.0)), minlength=n)
    return np.where(certain, 1.0, 1 - np.exp(log_miss))


def basis_recipients(expected, basis, years=YEARS):
    """Expected families and children gaining on a take-up basis, by year (to the nearest 1,000), and the mean gain.

    A child gains if its own funded hours or Tax-Free Childcare rise by more than ``GAIN_THRESHOLD``; a family gains
    if any member does. On a child-level basis each child takes up the new hours with its own chance, independently
    of its siblings; on a family-rate basis the family takes them up or not as a whole. The mean gain is the expected
    gain over the expected number of gaining families. Totals only: no breakdown is published on these bases.
    """
    spec = TAKE_UP_BASES[basis]
    bc, rc = (expected[s] for s in spec["pair"])
    out = {}
    for y in years:
        c = person_changes(expected, y, basis)
        rate = c["rate"]
        pb, bw, pw = rc(y, "p_benunit"), _weights(bc, rc, y, "bu"), _weights(bc, rc, y, "p")
        child = bc(y, "p_is_child")
        n = len(bw)
        t = GAIN_THRESHOLD
        hours_if_taken = child & (c["hours"] > t)
        tfc_if_taken, tfc_if_not = child & (c["tfc_if_taken"] > t), child & (c["tfc_if_not"] > t)
        gains_if_taken, gains_if_not = hours_if_taken | tfc_if_taken, tfc_if_not
        expected_gain = np.bincount(pb, weights=rate * (c["hours"] + c["tfc_if_taken"]) + (1 - rate) * c["tfc_if_not"],
                                    minlength=n)

        def child_chance(if_taken, if_not):
            return rate * if_taken + (1 - rate) * if_not

        def family_chance(if_taken, if_not):
            if spec["unit"] == "family":
                any_taken = np.bincount(pb, weights=if_taken.astype(float), minlength=n) > 0
                any_not = np.bincount(pb, weights=if_not.astype(float), minlength=n) > 0
                return spec["rate"] * any_taken + (1 - spec["rate"]) * any_not
            return _any_member(pb, child_chance(if_taken, if_not), n)

        none = np.zeros_like(child)
        families = family_chance(gains_if_taken, gains_if_not)
        n_families = float((bw * families).sum())
        out[str(y)] = {
            "families_gaining": _k(n_families),
            "children_gaining": _k((pw * child_chance(gains_if_taken, gains_if_not)).sum()),
            "by_scheme": {
                "thirty_hours": _k((bw * family_chance(hours_if_taken, none)).sum()),
                "tax_free_childcare": _k((bw * family_chance(tfc_if_taken, tfc_if_not)).sum()),
            },
            "children_by_scheme": {
                "thirty_hours": _k((pw * child_chance(hours_if_taken, none)).sum()),
                "tax_free_childcare": _k((pw * child_chance(tfc_if_taken, tfc_if_not)).sum()),
            },
            "mean_gain_gbp": round(float((bw * expected_gain).sum()) / n_families) if n_families > 0 else None,
        }
    return out


def household_source_codes(runs, year):
    """Each simulated household's FRS source household (an integer code), read from the pinned release.

    Microcosm copies an FRS household several times (SPI, high-value-home and CGT copies), so copies of one source
    household are not independent. The dataset's ``household_source_id`` is joined to the simulation's households
    through its person ids; every member of a household must share one source household.
    """
    import pandas as pd

    from .datasets import dataset_path

    b = runs["baseline"]
    path = dataset_path()
    person = pd.read_hdf(path, "person")[["person_id", "person_household_id"]]
    household = pd.read_hdf(path, "household")[["household_id", "household_source_id"]]
    if household["household_source_id"].isna().any():
        raise ValueError("a household has no source household id")
    hh_of_person = pd.Series(person["person_household_id"].to_numpy(), index=person["person_id"].to_numpy())
    source_of_hh = pd.Series(household["household_source_id"].to_numpy(), index=household["household_id"].to_numpy())
    p_source = source_of_hh.loc[hh_of_person.loc[b(year, "p_id")].to_numpy()].to_numpy()
    codes, uniques = pd.factorize(p_source)
    p_household = b(year, "p_household")
    hh_code = np.full(len(b(year, "hh_weight")), -1, dtype=np.int64)
    hh_code[p_household] = codes
    if (hh_code < 0).any():
        raise ValueError("a household has no members")
    if not np.array_equal(hh_code[p_household], codes):
        raise ValueError("a household's members come from different source households")
    return hh_code, len(uniques)


def bootstrap(runs, expected, years=(2027, 2029), draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED):
    """Sampling uncertainty of the static costs: a bootstrap over FRS source households, on every take-up basis.

    Each draw resamples the source households with replacement, each with all its Microcosm copies, the release
    weights fixed (calibration is not redone), and ignores the FRS's clustering, so it is a floor on the
    uncertainty. Every basis (``household_changes``: the single draw and each take-up basis) is resampled with the
    same draws. Also counts the source households the 30-hours cost rests on, on the single draw, and their effective
    number (Kish, over their shares of the cost). Aggregates only.
    """
    rng = np.random.default_rng(seed)
    out = {"draws": draws, "seed": seed, "by_year": {}}
    for y in years:
        code, n = household_source_codes(runs, y)
        counts = rng.multinomial(n, np.full(n, 1.0 / n), size=draws)
        h = household_changes(runs, expected, y)
        year_out = {}
        for basis in ("drawn", *TAKE_UP_BASES):
            legs = {leg: np.bincount(code, weights=h[basis][leg], minlength=n) for leg in h[basis]}
            legs["total"] = legs["thirty_hours"] + legs["tax_free_childcare"]
            year_out[basis] = {}
            for leg, per_source in legs.items():
                sample = counts @ per_source / BN
                p5, p95 = np.percentile(sample, [5, 95])
                year_out[basis][leg] = {"sd_bn": round(float(sample.std(ddof=1)), 3), "p5_bn": round(float(p5), 3),
                                        "p95_bn": round(float(p95), 3)}
        cost = np.bincount(code, weights=h["drawn"]["thirty_hours"], minlength=n)
        gaining = cost[cost > GAIN_THRESHOLD]
        year_out["source_households_30_hours"] = int(round(len(gaining), -1))
        year_out["effective_source_households_30_hours"] = int(round(float(gaining.sum() ** 2 / (gaining ** 2).sum()), -1))
        out["by_year"][str(y)] = year_out
    return out


def age_profile_sensitivity(runs, year=LEAD_YEAR):
    """The 30-hours cost with the newly entitled 1-to-4-year-olds spread evenly across those ages (£bn change).

    Holds their weighted number fixed and gives each age a quarter of it at that age's mean cost per newly entitled
    child. One-sided: the release has few 1-year-olds in families over £100,000, the dearest age to fund. Also
    each age's share of children in families with a parent over £100,000 (%).
    """
    b, r = runs["baseline"], runs["reform"]
    age, w = b(year, "p_age"), b(year, "p_weight")
    gain = r(year, "p_free_value") - b(year, "p_free_value")
    newly = gain > GAIN_THRESHOLD
    number, cost = {}, {}
    for a in (1, 2, 3, 4):
        m = newly & (age == a)
        number[a], cost[a] = float(w[m].sum()), float((gain * w)[m].sum())
    total_number = sum(number.values())
    even = sum(total_number / 4 * cost[a] / number[a] for a in number)
    over = b(year, "bu_any_over")[b(year, "p_benunit")]
    child = b(year, "p_is_child")
    share = {str(a): round(float(100 * w[child & over & (age == a)].sum() / w[child & (age == a)].sum()), 1)
             for a in range(5)}
    return {"year": year, "even_spread_bn": _bn(even - sum(cost.values())), "share_over_limit_by_age_pct": share,
            "babies_bn": _bn((gain * w)[newly & (age == 0)].sum())}
