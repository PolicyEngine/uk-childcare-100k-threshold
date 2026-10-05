"""Turn the record-level run arrays into the published aggregates.

Nothing record-level leaves this module: every output is a weighted total, a
weighted mean or a share, and a breakdown cell resting on fewer than
``MIN_CELL_RECORDS`` gaining records is suppressed (published as null).
"""

import numpy as np

from .config import (
    COUNTRIES,
    FREE_HOURS_VARIABLES,
    GAIN_THRESHOLD,
    MIN_CELL_RECORDS,
    UNDER_ONE_SHARE_ELIGIBLE,
    UNDER_ONE_WEEKLY_HOURS,
    VALIDATION_YEAR,
    WEEKS_PER_YEAR,
    YEARS,
)
from .engine import run_path

BN = 1e9
AGE_BANDS = [("0-1", 0, 2), ("2", 2, 3), ("3-4", 3, 5), ("5-11", 5, 12), ("12+", 12, 200)]


class Run:
    """One (dataset, scenario) run's arrays, read lazily by year."""

    def __init__(self, dataset, scenario):
        self.z = np.load(run_path(dataset, scenario))

    def __call__(self, year, name):
        return self.z[f"{year}/{name}"]


def load(dataset, scenarios):
    return {s: Run(dataset, s) for s in scenarios}


def _bn(x):
    return round(float(x) / BN, 3)


def _k(x):
    """Counts rounded to the nearest thousand."""
    return int(round(float(x) / 1000.0) * 1000)


def gross(base, ref, year):
    """Extra spending (£, unrounded) on free hours and TFC top-ups, and the net change in the government balance."""
    w = base(year, "hh_weight")
    free = (w * (ref(year, "hh_free") - base(year, "hh_free"))).sum()
    tfc = (w * (ref(year, "hh_tfc") - base(year, "hh_tfc"))).sum()
    net = -(w * (ref(year, "hh_gov_balance") - base(year, "hh_gov_balance"))).sum()
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
        out[key] = {str(y): _bn((b(y, "hh_weight") * (r(y, f"hh_{v}") - b(y, f"hh_{v}"))).sum()) for y in years}
    return out


def variant_totals(runs, variant, years=YEARS):
    b, r = runs["baseline"], runs[variant]
    return {str(y): _bn(sum(gross(b, r, y)[:2])) for y in years}


def sensitivities(runs, years=YEARS):
    """Each adjustment's effect on the gross total (£bn, + raises the cost), and the low/high range."""
    b, r = runs["baseline"], runs["reform"]
    eff = {k: {} for k in ("full_30_hour_usage", "under_ones", "ani_net_of_pension_contributions", "tfc_routed_share")}
    low, central, high = {}, {}, {}
    for y in years:
        c = sum(gross(b, r, y)[:2])
        hours30 = sum(gross(runs["baseline_hours30"], runs["reform_hours30"], y)[:2]) - c
        routed = sum(gross(runs["baseline_routed"], runs["reform_routed"], y)[:2]) - c

        # ANI net of pension contributions: a family with no adult above £100,000
        # on that measure already qualifies in law, so its modelled gain is not a
        # cost of the reform.
        _, _, d = family_changes(b, r, y)
        pb = b(y, "p_benunit")
        over_law = np.bincount(pb, weights=b(y, "p_ani_net_pension_over").astype(float), minlength=len(d)) > 0
        pension = -(b(y, "bu_weight") * d * (~over_law)).sum()

        # Under-1s (9-11 months) newly eligible: outside the model.
        newly = r(y, "bu_ext_eligible") & ~b(y, "bu_ext_eligible")
        age0 = np.bincount(pb, weights=(b(y, "p_age") < 1).astype(float), minlength=len(newly))
        rate0 = float(b(y, "rate_by_age")[0])
        under1 = (
            b(y, "bu_weight") * newly * age0 * UNDER_ONE_SHARE_ELIGIBLE * UNDER_ONE_WEEKLY_HOURS * WEEKS_PER_YEAR * rate0
        ).sum()

        k = str(y)
        eff["full_30_hour_usage"][k] = _bn(hours30)
        eff["under_ones"][k] = _bn(under1)
        eff["ani_net_of_pension_contributions"][k] = _bn(pension)
        eff["tfc_routed_share"][k] = _bn(routed)
        central[k] = _bn(c)
        low[k] = _bn(c + pension + routed)
        high[k] = _bn(c + hours30 + under1)
    return {"effects_bn": eff, "range_bn": {"low": low, "central": central, "high": high}}


def recipients(runs, years=YEARS):
    b, r = runs["baseline"], runs["reform"]
    out = {}
    for y in years:
        w = b(y, "bu_weight")
        d_free, d_tfc, d = family_changes(b, r, y)
        gain = d > GAIN_THRESHOLD
        pb = b(y, "p_benunit")
        pw = w[pb]
        child = b(y, "p_is_child")
        new_ext = r(y, "p_extended") & ~b(y, "p_extended") & (d_free > GAIN_THRESHOLD)[pb]
        new_tfc = r(y, "p_tfc") & ~b(y, "p_tfc") & (d_tfc > GAIN_THRESHOLD)[pb]
        kid_gain = child & (new_ext | new_tfc)
        age = b(y, "p_age")
        out[str(y)] = {
            "families_gaining": _k((w * gain).sum()),
            "children_gaining": _k((pw * kid_gain).sum()),
            "by_scheme": {
                "thirty_hours": _k((w * (d_free > GAIN_THRESHOLD)).sum()),
                "tax_free_childcare": _k((w * (d_tfc > GAIN_THRESHOLD)).sum()),
            },
            "children_by_scheme": {
                "thirty_hours": _k((pw * (child & new_ext)).sum()),
                "tax_free_childcare": _k((pw * (child & new_tfc)).sum()),
            },
            "children_gaining_by_age": {
                band: _k((pw * kid_gain * (age >= lo) * (age < hi)).sum()) for band, lo, hi in AGE_BANDS
            },
            "mean_gain_gbp": round(float((w * d * gain).sum() / (w * gain).sum())) if gain.any() else 0,
            "families_losing": _k((w * (d < -GAIN_THRESHOLD)).sum()),
        }
    return out


def _cell_ok(n_records):
    return n_records == 0 or n_records >= MIN_CELL_RECORDS


def distribution(runs, years=YEARS):
    b, r = runs["baseline"], runs["reform"]
    out = {}
    for y in years:
        w = b(y, "hh_weight")
        base_inc = b(y, "hh_net_income")
        d = r(y, "hh_net_income") - base_inc
        gain = d > GAIN_THRESHOLD
        decile = b(y, "hh_decile")
        rows = []
        for dec in range(1, 11):
            m = decile == dec
            n = int((m & gain).sum())
            if not _cell_ok(n):
                rows.append({"decile": dec, "mean_change_gbp": None, "pct_change": None, "share_gaining_pct": None,
                             "suppressed": True})
                continue
            rows.append({
                "decile": dec,
                "mean_change_gbp": round(float((w * d * m).sum() / (w * m).sum()), 2),
                "pct_change": round(float(100 * (w * d * m).sum() / (w * base_inc * m).sum()), 3),
                "share_gaining_pct": round(float(100 * (w * gain * m).sum() / (w * m).sum()), 2),
                "suppressed": False,
            })
        country = b(y, "hh_country")
        d_bu = family_changes(b, r, y)[2]
        bu_gain = d_bu > GAIN_THRESHOLD
        bu_country = country[b(y, "bu_household")]
        dh = (r(y, "hh_free") + r(y, "hh_tfc")) - (b(y, "hh_free") + b(y, "hh_tfc"))
        by_country = []
        for code, name in COUNTRIES.items():
            m = country == code
            mb = bu_country == code
            n = int((bu_gain & mb).sum())
            if not _cell_ok(n):
                by_country.append({"country": name, "total_change_bn": None, "families_gaining": None, "suppressed": True})
                continue
            by_country.append({
                "country": name,
                "total_change_bn": _bn((w * dh * m).sum()),
                "families_gaining": _k((b(y, "bu_weight") * bu_gain * mb).sum()),
                "suppressed": False,
            })
        out[str(y)] = {"by_decile": rows, "by_country": by_country}
    return out


def assumptions(runs, year=VALIDATION_YEAR + 1):
    """Weighted take-up draws and hours usage the model applies (aggregates only)."""
    b = runs["baseline"]
    w = b(year, "bu_weight")
    pb = b(year, "p_benunit")
    age = b(year, "p_age")
    kid = b(year, "p_is_child")
    young = np.bincount(pb, weights=(kid & (age < 5)).astype(float), minlength=len(w)) > 0
    under12 = np.bincount(pb, weights=(kid & (age < 12)).astype(float), minlength=len(w)) > 0
    high = np.bincount(pb, weights=b(year, "p_ani_over").astype(float), minlength=len(w)) > 0

    def share(flag, m):
        return round(float(100 * (w * flag * m).sum() / (w * m).sum()), 1)

    ext, tfc = b(year, "bu_would_claim_extended"), b(year, "bu_would_claim_tfc")
    return {
        "year": year,
        "would_claim_30_hours_pct": {"families_with_child_under_5": share(ext, young),
                                     "of_which_parent_over_100k": share(ext, young & high)},
        "would_claim_tfc_pct": {"families_with_child_under_12": share(tfc, under12),
                                "of_which_parent_over_100k": share(tfc, under12 & high)},
        "mean_extended_hours_usage": round(float((w * b(year, "bu_hours_usage") * young).sum() / (w * young).sum()), 1),
    }
