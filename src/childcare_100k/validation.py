"""Baseline validation: the unreformed model against official statistics.

Official figures were read from the publications below on 5 and 6 October 2026.
"""

from microdf import MicroSeries

from .aggregate import BN, Run
from .config import DATASET_LABELS, PRIMARY_DATASET, VALIDATION_YEAR

DFE_EY_URL = "https://explore-education-statistics.service.gov.uk/find-statistics/education-provision-children-under-5"
DFE_EY_SOURCE = "DfE, Education provision: children under 5 years of age, January 2026 (published 2 July 2026)"
HMRC_TFC_URL = "https://www.gov.uk/government/statistics/tax-free-childcare-statistics-june-2026"
HMRC_TFC_SOURCE = "HMRC, Tax-Free Childcare statistics, June 2026"
DFE_FUNDING_URL = (
    "https://www.gov.uk/government/publications/early-years-funding-2026-to-2027/"
    "2026-to-2027-early-years-national-funding-formulae-technical-note"
)
DFE_FUNDING_SOURCE = "DfE, 2026 to 2027 early years national funding formulae: technical note"
HMRC_ITL_URL = (
    "https://www.gov.uk/government/statistics/"
    "income-tax-liabilities-statistics-tax-year-2023-to-2024-to-tax-year-2026-to-2027"
)
HMRC_ITL_SOURCE = "HMRC, Income Tax liabilities statistics 2023-24 to 2026-27 (projected), July 2026, Table 2.5"

OFFICIAL = {
    # Sum of monthly government top-up, April 2025 to March 2026 (Table 1).
    "tfc_topup_bn": 0.5998,
    # Children / families with a used account at any point in 2025-26 (Tables 11 and 10, UK).
    "tfc_children": 1_151_515,
    "tfc_families": 868_095,
    # Working parent entitlement registrations, January 2026.
    "wpe_under_3": 501_700,  # 9 months to 2 years (30,700 aged 9-11 months)
    "wpe_3_4": 388_700,
    # Illustrative 2026-27 funding: 3-4s £4.2bn + 2-year-olds £2.7bn + under-2s £3.0bn.
    "ey_funding_bn": 9.9,
    "rate_under_2": 12.04,
    "rate_2": 8.90,
    "rate_3_4": 6.61,
    # Taxpayers with total income (before deductions) of £100,000 or more: the
    # £100k+ ranges of Table 2.5 summed, 2025-26 and 2026-27 projections.
    "taxpayers_100k_2025": 1_950_000,
    "taxpayers_100k_2026": 2_063_000,
}


def _row(label, year, model, official, unit, source, url, dataset, note=None):
    row = {"label": label, "year": year, "model": model, "official": official, "unit": unit,
           "source": source, "url": url, "dataset": dataset}
    if note:
        row["note"] = note
    return row


def _total(values, weights):
    """Weighted total of a record-level array (microdf)."""
    return float(MicroSeries(values.astype(float), weights=weights).sum())


def rows_for(runs):
    b: Run = runs["baseline"]
    y = VALIDATION_YEAR
    lab = DATASET_LABELS[PRIMARY_DATASET]
    hw = b(y, "hh_weight")
    bw = b(y, "bu_weight")
    pw = b(y, "p_weight")
    age = b(y, "p_age")
    ext = b(y, "p_extended")
    out = [
        _row("Tax-Free Childcare government top-up", y, round(_total(b(y, "hh_tfc"), hw) / BN, 3),
             OFFICIAL["tfc_topup_bn"], "£bn", HMRC_TFC_SOURCE + ", Table 1 (sum of Apr 2025-Mar 2026)", HMRC_TFC_URL, lab),
        _row("Children with a used Tax-Free Childcare account in the year", y,
             int(round(_total(b(y, "p_tfc"), pw), -3)), OFFICIAL["tfc_children"], "children",
             HMRC_TFC_SOURCE + ", Table 11", HMRC_TFC_URL, lab),
        _row("Families with a used Tax-Free Childcare account in the year", y,
             int(round(_total(b(y, "bu_tfc") > 0, bw), -3)), OFFICIAL["tfc_families"], "families",
             HMRC_TFC_SOURCE + ", Table 10", HMRC_TFC_URL, lab),
        _row("Children under 3 using the working parent entitlement", y,
             int(round(_total(ext & (age < 3), pw), -3)), OFFICIAL["wpe_under_3"], "children",
             DFE_EY_SOURCE + " (9 months to 2 years registered)", DFE_EY_URL, lab,
             "The model holds age in whole years and gives age 0 no hours, so 9-11-month-olds (30,700) cannot appear."),
        _row("3- and 4-year-olds using the working parent entitlement", y,
             int(round(_total(ext & (age >= 3) & (age < 5), pw), -3)), OFFICIAL["wpe_3_4"], "children",
             DFE_EY_SOURCE, DFE_EY_URL, lab,
             "Model: a 3- or 4-year-old counts once the family's working-parent hours go beyond the universal 15 "
             "(a family drawing 15 hours or fewer keeps the universal hours; corrections.py), which lowers the "
             "count; the model also gives 4-year-olds in reception funded hours (compulsory school age starts at 5 "
             "in the model), which raises it."),
    ]
    for year, key in ((VALIDATION_YEAR, "taxpayers_100k_2025"), (VALIDATION_YEAR + 1, "taxpayers_100k_2026")):
        out.append(_row("People with income of £100,000 or more", year,
                        int(round(_total(b(year, "p_ani_at_least"), b(year, "p_weight")), -3)), OFFICIAL[key],
                        "people", HMRC_ITL_SOURCE + ", income before deductions", HMRC_ITL_URL, lab,
                        "Model: adjusted net income as policyengine-uk computes it (before pension contributions), "
                        "which matches HMRC's 'total income before any deductions' ranges."))
    y2 = VALIDATION_YEAR + 1
    out.append(_row("Free early years entitlements spending (all three entitlements)", y2,
                    round(_total(b(y2, "hh_free"), b(y2, "hh_weight")) / BN, 2), OFFICIAL["ey_funding_bn"], "£bn",
                    DFE_FUNDING_SOURCE + " (sum of illustrative totals by age)", DFE_FUNDING_URL, lab))
    h = runs["baseline_hours30"]
    out.append(_row("Free early years entitlements spending if every family used all 30 extended hours", y2,
                    round(_total(h(y2, "hh_free"), h(y2, "hh_weight")) / BN, 2),
                    OFFICIAL["ey_funding_bn"], "£bn", DFE_FUNDING_SOURCE, DFE_FUNDING_URL, lab,
                    "Sensitivity run: brackets the official figure with the central run."))
    return out


def rate_rows(runs):
    b = runs["baseline"]
    y = VALIDATION_YEAR + 1
    rates = b(y, "rate_by_age")
    src = DFE_FUNDING_SOURCE + " (national average hourly rate)"
    return [
        _row("Hourly funding rate, under-2s", y, round(float(rates[1]), 2), OFFICIAL["rate_under_2"], "£/hour", src,
             DFE_FUNDING_URL, "parameters"),
        _row("Hourly funding rate, 2-year-olds", y, round(float(rates[2]), 2), OFFICIAL["rate_2"], "£/hour", src,
             DFE_FUNDING_URL, "parameters"),
        _row("Hourly funding rate, 3- and 4-year-olds", y, round(float(rates[3]), 2), OFFICIAL["rate_3_4"], "£/hour", src,
             DFE_FUNDING_URL, "parameters"),
    ]


def baseline_validation(runs):
    return rows_for(runs) + rate_rows(runs)
