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
# Share of childcare spend routed through a TFC account. The certified Microcosm
# release sets tax_free_childcare_spend_routed_share = 0.593 for every record, and the
# central run uses it; the low end sets 0.58 in baseline and reform.
ROUTED_SHARE_LOW = 0.58
SCENARIOS = {
    "baseline": {"params": [], "inputs": {}},
    "reform": {"params": [THIRTY_HOURS_LIMIT, TFC_LIMIT], "inputs": {}},
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

# Free-hours spending: the 30-hours leg is the change in all three entitlements.
# policyengine-uk switches the universal and targeted 15 hours off once a family is
# eligible for the extended entitlement; corrections.py keeps them and counts as
# extended only each child's hours above them, so the universal and targeted lines
# should not move, but all three are summed so that nothing is missed if they do.
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
    # A second, finer sweep across the limit, so the drop at £100,000 is drawn sharply.
    "fine_min": 95_001,
    "fine_step": 100,
    "fine_count": 101,
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

# ── Labour supply (labour_supply.py, hours_response.py) ──────────────────
# Ported from PolicyEngine/free-childcare-reform (src/free_childcare_reform/sources.py),
# where each figure's derivation is set out in full.
#
# Weekly hours assumed for someone entering work: the OBR note's and policyengine-uk's
# default. Load-bearing (it sets every entrant's earnings) and not varied in the bounds.
HOURS_FOR_NEW_ENTRANTS = 18.8
FULL_TIME_HOURS = 37.5
LSR_WEEKS_PER_YEAR = 52
# Low and high bounds scale both margins' elasticities by 1/3 and 2. The factors are
# illustrative, not a sourced uncertainty interval: they are the ratios of low and high
# childcare-price elasticities of maternal employment to a central one (-0.05 / -0.15 and
# -0.30 / -0.15, a reading of Akgündüz and Plantenga's meta-analysis for the UK), a
# different outcome from the OBR participation elasticities and Brewer's hours effect
# they scale.
PRICE_ELASTICITY_CENTRAL = -0.15
PRICE_ELASTICITY_LOW = -0.05
PRICE_ELASTICITY_HIGH = -0.30
ELASTICITY_SCALES = {
    "central": 1.0,
    "low": PRICE_ELASTICITY_LOW / PRICE_ELASTICITY_CENTRAL,
    "high": PRICE_ELASTICITY_HIGH / PRICE_ELASTICITY_CENTRAL,
}
# Cap on the modelled proportional change in any one person's probability of working
# (a numerical guard, not a published figure).
PARTICIPATION_CHANGE_BOUND = 0.5
# Childcare price elasticity of hours worked: an extrapolated scenario assumption, not an
# estimated price elasticity. Brewer, Cattan, Crawford and Rabe (IFS WP20/09, Table A.3
# panel B) estimate +0.600 weekly hours on a mean of 14.319 (+4.19%) for mothers whose
# youngest child becomes eligible for full-time instead of part-time free care. Treating
# that eligibility as a 100% price fall, and applying the result to the change in the price
# of the marginal hour of paid care of every working adult in the responding population
# (hours_response.py), extends it to interventions, parents and child ages it was not
# estimated on. A total-hours effect that contains the participation channel, so adding it
# to the extensive margin overstates the whole slightly. The hours margin's income effect
# uses the OBR income elasticities from policyengine-uk (no setting here).
HOURS_PRICE_ELASTICITY = -0.042
BREWER_HOURS_URL = (
    "https://ifs.org.uk/sites/default/files/output_url_files/"
    "WP202009-Does-more-free-childcare-help-parents-work-more.pdf#page=41"
)
OBR_PARTICIPATION_URL = "https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf"
# policyengine-uk assigns the OBR groups by legal marriage; labour_supply.CoupleView assigns them by couple.
UPSTREAM_COUPLE_ISSUE_URL = "https://github.com/PolicyEngine/policyengine-uk/issues/2190"
AKGUNDUZ_PLANTENGA_URL = "https://www.uu.nl/sites/default/files/rebo_use_dp_2015_15-14.pdf"
# An assumption, not a measured figure: of the free hours a family is newly offered, the
# share assumed to displace care it was already paying for. The hours margin uses it to
# decide whether newly funded hours cover all the paid care a family buys (then the
# marginal hour is free; otherwise the funded hours are inframarginal, hours_response.py).
# IFS BN189 (pp. 11-12): 570 more funded hours raised subsidisable care by 163 hours and
# all care outside the immediate family by 54. 1 - 54/570 (90.5%, central) treats every
# displaced hour of non-family care, paid or unpaid, as paid; 1 - 163/570 (71.4%, low)
# displaces only subsidisable care already being bought; 100% (high) displaces every
# newly funded hour. Varied on its own at central elasticities (``intensive_displacement``).
FREE_HOURS_DISPLACEMENT = 1 - 54 / 570
FREE_HOURS_DISPLACEMENT_RANGE = {"low": 1 - 163 / 570, "high": 1.0}
# The income effect's gain (hours_response.income_gain): "paid_care" counts the paid
# childcare the newly funded hours displace plus cash (disposable income, Tax-Free
# Childcare included), the same resource definition as its HBAI disposable-income base;
# The Tax-Free Childcare top-up on the displaced spend is withdrawn, since the family no
# longer pays for that care. Published as sensitivities (``intensive_income_basis``):
# "paid_care_fixed_spend", the same gain with the top-up kept on the displaced spend
# (spending held fixed), and "government_cost", which counts the funded hours at their
# funding value.
INCOME_BASIS = "paid_care"
INCOME_BASIS_SENSITIVITIES = ("paid_care_fixed_spend", "government_cost")
# Cells within which implied entrants are allocated to non-workers (labour_supply.entry_cells):
# the OBR Table A1 groups' youngest-child bands.
YOUNGEST_CHILD_BANDS = (0, 3, 6, 11)
# The responding population: adults in a benefit unit whose youngest child is under 12
# (the Tax-Free Childcare band, which contains the 30 hours' 9 months-4 years) and in
# which at least one adult's income, as the limits test it, is over £100,000.
YOUNGEST_CHILD_MAX_AGE = 11

