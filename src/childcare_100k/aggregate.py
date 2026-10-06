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
    COUNTRIES,
    FREE_HOURS_VARIABLES,
    GAIN_THRESHOLD,
    MIN_CELL_RECORDS,
    UNDER_ONE_WEEKLY_HOURS,
    VALIDATION_YEAR,
    WEEKS_PER_YEAR,
    YEARS,
)
from .engine import load_meta, run_path

BN = 1e9
AGE_BANDS = [("0-1", 0, 2), ("2", 2, 3), ("3-4", 3, 5), ("5-11", 5, 12), ("12+", 12, 200)]

# Under-1s (outside the model, which holds age in whole years and gives age 0 no
# hours). A child becomes eligible at the start of the term after it turns nine
# months, and the extended entitlement's terms start on 1 September, 1 January and
# 1 April (4-, 3- and 5-month terms). With birthdays spread evenly, the wait from
# nine months to the next term start averages sum(L^2/2)/12 = 25/12 months, and
# the months a child is funded before its first birthday average
# sum over terms of (L/12) * E[max(0, 3 - wait | term L)] = (4*1.125 + 3*1.5 + 5*0.9)/12
# = 1.125 months. So an age-0 child in a newly eligible family is funded for
# 1.125/12 of the year on average (it was 3/12 when the term delay was ignored).
UNDER_ONE_FUNDED_MONTHS = 1.125
UNDER_ONE_SHARE_OF_YEAR = UNDER_ONE_FUNDED_MONTHS / 12

# The low end's single, non-overlapping adjustment (see ``sensitivities``).
JOINT_LOW = "ani_net_of_pension_contributions_and_tfc_routed_share"


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


def budget_block(runs, years=YEARS):
    b, r = runs["baseline"], runs["reform"]
    out = {"thirty_hours": {}, "tax_free_childcare": {}, "total": {}, "net_total": {}}
    for y in years:
        free, tfc, net = gross(b, r, y)
        out["thirty_hours"][str(y)] = _bn(free)
        out["tax_free_childcare"][str(y)] = _bn(tfc)
        out["total"][str(y)] = round(out["thirty_hours"][str(y)] + out["tax_free_childcare"][str(y)], 3)
        out["net_total"][str(y)] = _bn(net)
    return out


def thirty_hours_components(runs, years=YEARS):
    """The 30-hours leg split by entitlement (£bn). The universal line is the 3-4-year-olds' switch."""
    b, r = runs["baseline"], runs["reform"]
    out = {}
    for v in FREE_HOURS_VARIABLES:
        key = v.replace("_childcare_entitlement", "")
        out[key] = {
            str(y): _bn(_hh(r(y, f"hh_{v}") - b(y, f"hh_{v}"), _weights(b, r, y, "hh")).sum()) for y in years
        }
    return out


def variant_totals(runs, variant, years=YEARS):
    b, r = runs["baseline"], runs[variant]
    return {str(y): _bn(sum(gross(b, r, y)[:2])) for y in years}


def sensitivities(runs, years=YEARS):
    """Each adjustment's effect on the gross total (£bn, + raises the cost), and the low/high range.

    The low end is one joint adjustment, so the two parts cannot double count: families that
    already qualify in law once pension contributions are deducted from adjusted net income
    lose their whole modelled gain, and the TFC routed-share change is counted only for the
    families that remain. ``low = central + joint`` and ``high = central + hours + under-1s``.
    """
    b, r = runs["baseline"], runs["reform"]
    eff = {k: {} for k in ("full_30_hour_usage", "under_ones", JOINT_LOW)}
    low, central, high = {}, {}, {}
    for y in years:
        c = sum(gross(b, r, y)[:2])
        hours30 = sum(gross(runs["baseline_hours30"], runs["reform_hours30"], y)[:2]) - c

        bw = _weights(b, r, y, "bu")
        _, _, d = family_changes(b, r, y)
        # ANI net of pension contributions: a family with no adult above £100,000 on that
        # measure already qualifies in law, so its modelled gain is not a cost of the reform.
        # The flag is each year's own. Salary sacrifice returned to pay under the April 2029
        # National Insurance cap is excluded from adjusted net income in every run
        # (corrections.py), as HMRC says the cap leaves adjusted net income unchanged.
        over_law = b(y, "bu_any_over_law")
        pension = -MicroSeries(d, weights=bw)[~over_law].sum()

        # TFC routed share: the change in each remaining family's gain when only 58% of
        # childcare spending runs through a TFC account.
        rb, rr = runs["baseline_routed"], runs["reform_routed"]
        if not (np.array_equal(rb(y, "bu_weight"), bw) and np.array_equal(rr(y, "bu_weight"), bw)):
            raise ValueError(f"{y}: routed runs' benunit weights differ from the central runs'")
        d_routed = family_changes(rb, rr, y)[2]
        routed = MicroSeries(d_routed - d, weights=bw)[over_law].sum()

        # Under-1s (9-11 months) in newly eligible families: outside the model.
        newly = r(y, "bu_ext_eligible") & ~b(y, "bu_ext_eligible")
        rate0 = float(b(y, "rate_by_age")[0])
        under1 = MicroSeries(
            b(y, "bu_n_age0") * UNDER_ONE_SHARE_OF_YEAR * UNDER_ONE_WEEKLY_HOURS * WEEKS_PER_YEAR * rate0,
            weights=bw,
        )[newly].sum()

        k = str(y)
        eff["full_30_hour_usage"][k] = _bn(hours30)
        eff["under_ones"][k] = _bn(under1)
        eff[JOINT_LOW][k] = _bn(pension + routed)
        central[k] = _bn(c)
        low[k] = _bn(c + pension + routed)
        high[k] = _bn(c + hours30 + under1)
    return {"effects_bn": eff, "range_bn": {"low": low, "central": central, "high": high}}


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


_LABELS = ("decile", "country")


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

        hh_country = b(y, "hh_country")
        bu_country = b(y, "bu_country")  # index into COUNTRIES, mapped by the simulation
        d_bu = family_changes(b, r, y)[2]
        bu_gain = d_bu > GAIN_THRESHOLD
        dh = (r(y, "hh_free") + r(y, "hh_tfc")) - (b(y, "hh_free") + b(y, "hh_tfc"))
        spend = MicroSeries(dh, weights=hw)
        fam_gain = MicroSeries(bu_gain.astype(float), weights=bw)
        bu_changed = np.abs(d_bu) > GAIN_THRESHOLD
        hh_changed = np.abs(dh) > GAIN_THRESHOLD
        by_country, country_sizes = [], []
        for i, (code, name) in enumerate(COUNTRIES.items()):
            m = hh_country == code
            mb = bu_country == i
            n = _records(bu_gain & mb)
            n_changed = max(_records(bu_changed & mb), _records(hh_changed & m))
            country_sizes.append(n_changed)
            if not _cell_ok(n, n_changed):
                by_country.append({"country": name, "total_change_bn": None, "families_gaining": None, "suppressed": True})
                continue
            by_country.append({
                "country": name,
                "total_change_bn": _bn(spend[m].sum()),
                "families_gaining": _k(fam_gain[mb].sum()),
                "suppressed": False,
            })
        # The deciles' mean changes and the countries' totals add up to published UK totals,
        # so a lone suppressed cell is protected by suppressing a second one.
        out[str(y)] = {"by_decile": _complement(rows, row_sizes), "by_country": _complement(by_country, country_sizes)}
    return out


def assumptions(runs, year=VALIDATION_YEAR + 1):
    """Weighted take-up draws and hours usage the model applies (aggregates only)."""
    b = runs["baseline"]
    w = b(year, "bu_weight")
    young = b(year, "bu_child_under_5")
    under12 = b(year, "bu_child_under_12")
    high = b(year, "bu_any_over")

    def share(flag, m):
        return round(float(100 * MicroSeries(flag.astype(float), weights=w)[m].mean()), 1)

    ext, tfc = b(year, "bu_would_claim_extended"), b(year, "bu_would_claim_tfc")
    return {
        "year": year,
        "would_claim_30_hours_pct": {"families_with_child_under_5": share(ext, young),
                                     "of_which_parent_over_100k": share(ext, young & high)},
        "would_claim_tfc_pct": {"families_with_child_under_12": share(tfc, under12),
                                "of_which_parent_over_100k": share(tfc, under12 & high)},
        "mean_extended_hours_usage": round(
            float(MicroSeries(b(year, "bu_hours_usage").astype(float), weights=w)[young].mean()), 1
        ),
    }
