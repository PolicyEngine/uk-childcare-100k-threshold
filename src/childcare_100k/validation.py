"""Baseline validation: the unreformed model against official statistics.

Official figures were read from the publications below on 5 and 6 October 2026; the
2025-26 early years funding totals on 21 October 2026.
"""

from microdf import MicroSeries

from .aggregate import BN, Run
from .config import DATASET_LABELS, PRIMARY_DATASET, VALIDATION_YEAR

DFE_EY_URL = "https://explore-education-statistics.service.gov.uk/find-statistics/funded-early-education-and-childcare/2025"
DFE_EY_SOURCE = "DfE, Education provision: children under 5 years of age, January 2025 census"
HMRC_TFC_URL = "https://www.gov.uk/government/statistics/tax-free-childcare-statistics-june-2026"
HMRC_TFC_SOURCE = "HMRC, Tax-Free Childcare statistics, June 2026"
DFE_FUNDING_URL = (
    "https://www.gov.uk/government/publications/early-years-funding-2026-to-2027/"
    "2026-to-2027-early-years-national-funding-formulae-technical-note"
)
DFE_FUNDING_SOURCE = "DfE, 2026 to 2027 early years national funding formulae: technical note"
DFE_FUNDING_2025_URL = (
    "https://www.gov.uk/government/publications/early-years-funding-2025-to-2026/"
    "2025-to-2026-early-years-national-funding-formulae-technical-note"
)
DFE_FUNDING_2025_SOURCE = "DfE, 2025 to 2026 early years national funding formulae: technical note (withdrawn 10 August 2026)"
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
    # Working parent entitlement registrations in the January 2025 census, the figures the release's DfE
    # calibration rows bind (PolicyEngine/microcosm#1338): 9-11 months 29,155, age 1 195,104, age 2 242,453;
    # ages 3 and 4 about 379,000. The January 2026 census (published 2 July 2026) has 501,700 under 3 and
    # 388,700 aged 3 and 4.
    "wpe_under_3": 466_700,
    "wpe_3_4": 379_000,
    # Illustrative funding totals by age, summed (neither note states a combined total).
    # 2026-27, section 3.3: 3-4s £4.2bn + 2-year-olds £2.7bn + under-2s £3.0bn.
    "ey_funding_bn": 9.9,
    # 2025-26, section 3.2: 3-4s £3.8bn + 2-year-olds £2.1bn + under-2s £2.3bn. The under-2s and
    # 2-year-old working-parent offer rose from 15 to 30 hours in September 2025 (the note assumes
    # 14 hours a week taken April-August and 26 from September).
    "ey_funding_bn_2025": 8.2,
    "rate_under_2": 12.04,
    "rate_2": 8.90,
    "rate_3_4": 6.61,
    # Taxpayers with total income (before deductions) of £100,000 or more: the
    # £100k+ ranges of Table 2.5 summed, 2025-26 and 2026-27 projections.
    "taxpayers_100k_2025": 1_950_000,
    "taxpayers_100k_2026": 2_063_000,
}


CENSUS_NOTE = (
    "Against the January 2025 census the dataset is calibrated to; DfE counted 501,700 under 3 and 388,700 aged 3 "
    "and 4 in January 2026. The under-3 figure includes 29,200 aged 9-11 months."
)


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
    spring = b(y, "p_wpe_spring")
    dfe_age = b(y, "p_dfe_age")
    out = [
        _row("Tax-Free Childcare government top-up", y, round(_total(b(y, "hh_tfc"), hw) / BN, 3),
             OFFICIAL["tfc_topup_bn"], "£bn", HMRC_TFC_SOURCE + ", Table 1 (sum of Apr 2025-Mar 2026)", HMRC_TFC_URL, lab),
        _row("Children with a used Tax-Free Childcare account in the year", y,
             int(round(_total(b(y, "p_tfc"), pw), -3)), OFFICIAL["tfc_children"], "children",
             HMRC_TFC_SOURCE + ", Table 11", HMRC_TFC_URL, lab),
        _row("Families with a used Tax-Free Childcare account in the year", y,
             int(round(_total(b(y, "bu_tfc") > 0, bw), -3)), OFFICIAL["tfc_families"], "families",
             HMRC_TFC_SOURCE + ", Table 10", HMRC_TFC_URL, lab),
        _row("Children under 3 on the working parent entitlement in the spring term", y,
             int(round(_total(spring & (dfe_age < 3), pw), -3)), OFFICIAL["wpe_under_3"], "children",
             DFE_EY_SOURCE + " (9 months to 2 years registered)", DFE_EY_URL, lab, CENSUS_NOTE),
        _row("3- and 4-year-olds on the working parent entitlement in the spring term", y,
             int(round(_total(spring & (dfe_age >= 3) & (dfe_age < 5), pw), -3)), OFFICIAL["wpe_3_4"], "children",
             DFE_EY_SOURCE, DFE_EY_URL, lab, "Counted as in the row above."),
    ]
    for year, key in ((VALIDATION_YEAR, "taxpayers_100k_2025"), (VALIDATION_YEAR + 1, "taxpayers_100k_2026")):
        out.append(_row("People with income of £100,000 or more", year,
                        int(round(_total(b(year, "p_income_before_deductions_at_least"), b(year, "p_weight")), -3)),
                        OFFICIAL[key], "people", HMRC_ITL_SOURCE + ", income before deductions", HMRC_ITL_URL, lab,
                        "Income before pension contributions and Gift Aid, as HMRC counts it here; the limits test "
                        "income after them."))
    funding = {VALIDATION_YEAR: ("ey_funding_bn_2025", DFE_FUNDING_2025_SOURCE, DFE_FUNDING_2025_URL),
               VALIDATION_YEAR + 1: ("ey_funding_bn", DFE_FUNDING_SOURCE, DFE_FUNDING_URL)}
    h = runs["baseline_hours30"]
    for year, (key, source, url) in funding.items():
        out.append(_row("Free early years entitlements spending (all three entitlements)", year,
                        round(_total(b(year, "hh_free"), b(year, "hh_weight")) / BN, 2), OFFICIAL[key], "£bn",
                        source, url, lab,
                        "England, all three entitlements at DfE's funding rates."))
        out.append(_row("Free early years entitlements spending if every family used all 30 extended hours", year,
                        round(_total(h(year, "hh_free"), h(year, "hh_weight")) / BN, 2), OFFICIAL[key], "£bn",
                        source, url, lab))
    return out


def rate_rows(runs):
    b = runs["baseline"]
    y = VALIDATION_YEAR + 1
    rates = b(y, "rate_by_age")
    src = DFE_FUNDING_SOURCE
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
