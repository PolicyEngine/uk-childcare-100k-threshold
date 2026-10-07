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

# Fiscal years named by start year ("2026" = 2026-27).
YEARS = [2026, 2027, 2028, 2029]
# Baseline-only year for validation against 2025-26 official statistics.
VALIDATION_YEAR = 2025
# The year compared with CenTax's 2030 static cost (the nearest fiscal year).
BENCHMARK_YEAR = 2029
# The year the dashboard leads with: 2026-27 is already half over and the proposal
# gives no start date, so 2026-27 is shown as illustrative.
LEAD_YEAR = 2027

# Dataset: the certified Microcosm UK 2024-25 national release, pinned by revision
# and sha256 in datasets.py (policyengine.py 6.2.1's bundle does not register it,
# so the runs pass the verified file to managed_microsimulation as an unmanaged
# dataset). It is the only dataset.
PRIMARY_DATASET = "microcosm_uk_2024_25"
DATASET_LABELS = {PRIMARY_DATASET: "Microcosm UK 2024-25 (national release)"}

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
# ITL1 regions (policyengine-uk's household ``region``), in ONS order.
REGIONS = {
    "NORTH_EAST": "North East",
    "NORTH_WEST": "North West",
    "YORKSHIRE": "Yorkshire and the Humber",
    "EAST_MIDLANDS": "East Midlands",
    "WEST_MIDLANDS": "West Midlands",
    "EAST_OF_ENGLAND": "East of England",
    "LONDON": "London",
    "SOUTH_EAST": "South East",
    "SOUTH_WEST": "South West",
    "WALES": "Wales",
    "SCOTLAND": "Scotland",
    "NORTHERN_IRELAND": "Northern Ireland",
}
# Family types for the gains breakdown: lone parent or couple, by number of children.
FAMILY_TYPES = {
    "LONE_PARENT": "Lone parent",
    "COUPLE_1": "Couple, one child",
    "COUPLE_2": "Couple, two children",
    "COUPLE_3": "Couple, three or more children",
    "OTHER": "Other family",
}

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

# ── Household form on the dashboard ──────────────────────────────────────
# Every combination is precomputed (household.household_grid). The default is the
# published cliff family above, so the form opens on a household that hits the cliff.
HOUSEHOLD_GRID = {
    # £1 to £140,001 in £1,000 steps, so the chart starts at zero and £99,001 and £100,001
    # sit either side of the limit.
    "earnings_min": 1,
    "earnings_step": 1_000,
    "earnings_count": 141,
    "parents": [
        {"id": "couple20", "label": "Couple, partner earns £20,000", "partner_earnings": 20_000},
        {"id": "couple40", "label": "Couple, partner earns £40,000", "partner_earnings": 40_000},
        {"id": "couple80", "label": "Couple, partner earns £80,000", "partner_earnings": 80_000},
        {"id": "lone", "label": "Lone parent", "partner_earnings": None},
    ],
    "children": [
        {"id": "3", "label": "One child aged 3", "ages": [3]},
        {"id": "2-3", "label": "Two children, aged 2 and 3", "ages": [2, 3]},
        {"id": "1-3", "label": "Two children, aged 1 and 3", "ages": [1, 3]},
        {"id": "3-7", "label": "Two children, aged 3 and 7", "ages": [3, 7]},
    ],
    "spend_per_child": [
        {"id": "5k", "label": "£5,000 a year per child", "amount": 5_000},
        {"id": "10k", "label": "£10,000 a year per child", "amount": 10_000},
        {"id": "15k", "label": "£15,000 a year per child", "amount": 15_000},
    ],
    "default": {"parent": "couple40", "children": "2-3", "spend_per_child": "10k"},
}

# ── Benchmark ────────────────────────────────────────────────────────────
CONSERVATIVE_COST_BN = 0.7
# The party's web announcement (conservatives.com, 4 October 2026) gives no figure; the party's
# briefing to PA and the BBC put it at about £700m a year;
# City AM reports it as "scrapped at a cost of about £700m per year" and says the
# costing "is based on a recent report by the Centre for the Analysis of Taxation":
# CenTax's net £640m in 2030 for the free hours only (static £980m, Table 4.2; the £340m
# difference is £210m intensive-margin tax from parents plus £130m tax and NI from partners
# entering work).
CONSERVATIVE_SOURCE_URL = (
    "https://www.cityam.com/badenoch-vows-to-end-100k-childcare-cliff-edge-introduced-under-last-tory-government/"
)
CONSERVATIVE_ANNOUNCEMENT_URL = (
    "https://www.conservatives.com/news/conservatives-pledge-to-abolish-absurd-childcare-cliff-edge"
)
CENTAX_REPORT_URL = (
    "https://centax.org.uk/wp-content/uploads/2026/09/"
    "AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf"
)
