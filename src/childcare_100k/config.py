"""Fixed choices for the £100,000 childcare income limit analysis.

Everything a reader might want to check or change lives here: the reform, the
years, the datasets, the official statistics the baseline is compared with and
the limitations the results file reports.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
OUTPUT = DATA / "results.json"
CACHE = REPO / ".cache"
RUNS = CACHE / "runs"  # record-level arrays per run: gitignored, never published
WORKER = CACHE / "worker"  # policyengine materialises datasets into WORKER/data

# Fiscal years named by start year ("2026" = 2026-27).
YEARS = [2026, 2027, 2028, 2029]
# Baseline-only year for validation against 2025-26 official statistics.
VALIDATION_YEAR = 2025
HEADLINE_YEAR = 2029

# Datasets (names in the policyengine.py release bundle).
PRIMARY_DATASET = "populace_uk_2023"  # "Microcosm"
CROSS_CHECK_DATASET = "enhanced_frs_2024_25"
DATASET_LABELS = {PRIMARY_DATASET: "Microcosm (populace_uk_2023)", CROSS_CHECK_DATASET: "Enhanced FRS 2024-25"}

# The two parameters the reform touches, and nothing else.
THIRTY_HOURS_LIMIT = "gov.dfe.extended_childcare_entitlement.income.limit"
TFC_LIMIT = "gov.hmrc.tax_free_childcare.income.income_limit"
REFORM_PARAMETERS = [THIRTY_HOURS_LIMIT, TFC_LIMIT]
BASELINE_LIMIT = 100_000
REMOVED = float("inf")


def parameter_changes(parameters):
    """policyengine-uk Scenario parameter changes: each limit removed in every analysis year.

    A bare year key names the UK fiscal year (6 April to 5 April) in policyengine-uk.
    """
    return {p: {str(y): REMOVED for y in YEARS} for p in parameters}


# Each scenario: the limits it removes, and inputs it overrides in every year
# (overrides apply identically to a sensitivity's baseline and reform runs).
HOURS_USAGE_VARIABLE = "maximum_extended_childcare_hours_usage"
ROUTED_SHARE_VARIABLE = "tax_free_childcare_spend_routed_share"
# Share of childcare spend routed through a TFC account in later
# policyengine-uk-data builds (>= 1.57.0); the bundled datasets predate it, so
# the model's default of 1 applies in the central run.
ROUTED_SHARE_LOW = 0.58
SCENARIOS = {
    "baseline": {"params": [], "inputs": {}},
    "reform": {"params": [THIRTY_HOURS_LIMIT, TFC_LIMIT], "inputs": {}},
    "thirty_hours_only": {"params": [THIRTY_HOURS_LIMIT], "inputs": {}},
    "tfc_only": {"params": [TFC_LIMIT], "inputs": {}},
    # High: every family uses the full 30 extended hours (the data draw a mean of ~15).
    "baseline_hours30": {"params": [], "inputs": {HOURS_USAGE_VARIABLE: 30.0}},
    "reform_hours30": {"params": [THIRTY_HOURS_LIMIT, TFC_LIMIT], "inputs": {HOURS_USAGE_VARIABLE: 30.0}},
    # Low: only 58% of childcare spend goes through a TFC account.
    "baseline_routed": {"params": [], "inputs": {ROUTED_SHARE_VARIABLE: ROUTED_SHARE_LOW}},
    "reform_routed": {"params": [THIRTY_HOURS_LIMIT, TFC_LIMIT], "inputs": {ROUTED_SHARE_VARIABLE: ROUTED_SHARE_LOW}},
}
# Under-1s: the model holds age in whole years and gives age 0 no hours, so
# 9-11-month-olds never qualify. Added outside the model: a quarter of the
# age-0 children in newly eligible families (who already pass the model's
# take-up draw), at 30 hours x 38 weeks x the under-2 funding rate.
UNDER_ONE_SHARE_ELIGIBLE = 0.25
UNDER_ONE_WEEKLY_HOURS = 30
WEEKS_PER_YEAR = 38

# Free-hours spending: the 30-hours leg is the change in all three entitlements,
# because the model switches the universal 15 hours off for a family once it is
# eligible for the extended entitlement (the extended 30 hours replace them).
FREE_HOURS_VARIABLES = [
    "extended_childcare_entitlement",
    "universal_childcare_entitlement",
    "targeted_childcare_entitlement",
]
TFC_VARIABLE = "tax_free_childcare"

# Disclosure control: no breakdown cell is published if it rests on fewer than
# this many gaining survey/synthetic records. Record counts are never published.
MIN_CELL_RECORDS = 10
# A family or household "gains" if its income rises by more than this (£/year).
GAIN_THRESHOLD = 1.0

COUNTRIES = {"ENGLAND": "England", "SCOTLAND": "Scotland", "WALES": "Wales", "NORTHERN_IRELAND": "Northern Ireland"}

# ── Cliff example ────────────────────────────────────────────────────────
CLIFF = {
    "year": 2027,
    "earnings_min": 80_000,
    "earnings_max": 130_000,
    "earnings_step": 1_000,
    "partner_earnings": 40_000,
    "child_ages": [2, 3],
    "childcare_spend_per_child": 10_000,
    "region": "SOUTH_EAST",
}

# ── Benchmark ────────────────────────────────────────────────────────────
CONSERVATIVE_COST_BN = 0.7
# The party's announcement (conservatives.com, 4 October 2026) gives no figure;
# City AM reports it as "scrapped at a cost of about £700m per year".
CONSERVATIVE_SOURCE_URL = (
    "https://www.cityam.com/badenoch-vows-to-end-100k-childcare-cliff-edge-introduced-under-last-tory-government/"
)
CONSERVATIVE_ANNOUNCEMENT_URL = (
    "https://www.conservatives.com/news/conservatives-pledge-to-abolish-absurd-childcare-cliff-edge"
)
