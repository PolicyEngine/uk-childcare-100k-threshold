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

# Dataset: the Microcosm UK 2024-25 national release of 23 October 2026 (a133f37a), pinned by
# its cut tag and sha256 in datasets.py and run on the policyengine-uk version its manifest
# pins (2.147.2). No policyengine.py bundle registers it yet, so the runs pass the verified
# file to managed_microsimulation as an unmanaged dataset. It is the only dataset.
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


# Each scenario: the limits it removes and inputs it overrides in every year (overrides apply
# identically to a sensitivity's baseline and reform runs). A reform names its baseline
# (``base``): engine.run_job nets the value of each child's new funded hours off that child's
# childcare spending in the reform before Tax-Free Childcare is computed (``net_new_hours``),
# so the reform does not pay Tax-Free Childcare on care the new hours replace.
HOURS_USAGE_VARIABLE = "maximum_extended_childcare_hours_usage"
ROUTED_SHARE_VARIABLE = "tax_free_childcare_spend_routed_share"
TFC_TAKE_UP_VARIABLE = "would_claim_tfc"
# Share of childcare spend routed through a TFC account. The Microcosm
# release sets tax_free_childcare_spend_routed_share for every record, and the
# central run uses it; the low end sets 0.58 in baseline and reform.
ROUTED_SHARE_LOW = 0.58
# Tax-Free Childcare take-up among newly eligible families, sensitivity: today's average use among all
# eligible families (about 36% of them, which with about 52% of newly eligible families reporting paid
# registered childcare is about 70% of those with spending; María Juaristi, #8, 22 October 2026). On an
# expectation basis: the leg with every newly eligible family claiming (the ``tfc_all`` pair) times 0.70.
TFC_TAKE_UP_NEWLY_ELIGIBLE_LOW = 0.70
_REFORM = [THIRTY_HOURS_LIMIT, TFC_LIMIT]
SCENARIOS = {
    "baseline": {"params": [], "inputs": {}},
    "reform": {"params": _REFORM, "inputs": {}, "base": "baseline", "net_new_hours": True},
    # High: every family uses the full 30 extended hours (the data draw a mean of ~28.4).
    "baseline_hours30": {"params": [], "inputs": {HOURS_USAGE_VARIABLE: 30.0}},
    "reform_hours30": {"params": _REFORM, "inputs": {HOURS_USAGE_VARIABLE: 30.0}, "base": "baseline_hours30",
                       "net_new_hours": True},
    # Low: only 58% of childcare spend goes through a TFC account.
    "baseline_routed": {"params": [], "inputs": {ROUTED_SHARE_VARIABLE: ROUTED_SHARE_LOW}},
    "reform_routed": {"params": _REFORM, "inputs": {ROUTED_SHARE_VARIABLE: ROUTED_SHARE_LOW}, "base": "baseline_routed",
                      "net_new_hours": True},
    # Every family claims Tax-Free Childcare when eligible (baseline and reform), for the take-up sensitivity.
    "baseline_tfc_all": {"params": [], "inputs": {TFC_TAKE_UP_VARIABLE: True}},
    "reform_tfc_all": {"params": _REFORM, "inputs": {TFC_TAKE_UP_VARIABLE: True}, "base": "baseline_tfc_all",
                       "net_new_hours": True},
}

# Expected mode (expectation.py, #7): the take-up contract's working-parent rate for the 30 hours,
# extended_childcare from 6 April 2024, in take_up_contract.json at PolicyEngine/microcosm 829c1bc26
# (the commit the release was cut from). The universal flag is nested under it at a conditional
# rate of zero, so the pair sets both. The contract take-up basis (TAKE_UP_BASES below) is this rate
# times the pair's cost.
EXTENDED_TAKE_UP_RATE = 0.8361
EXTENDED_TAKE_UP_SOURCE_URL = (
    "https://github.com/PolicyEngine/microcosm/blob/829c1bc26/"
    "packages/microcosm-build/src/microcosm/build/uk/take_up_contract.json"
)
CLAIM_30_HOURS = {"would_claim_extended_childcare": True, "would_claim_universal_childcare": True}
# The child-level take-up bases (TAKE_UP_BASES below) also have every child use its funded hours: the dataset's
# under-2 usage draw (max_free_entitlement_hours_used, 0 or 30, drawn for children aged 0) is set to 30 for
# everyone, since DfE's and CenTax's rates already count whether the child uses the hours. The family's weekly
# hours cap (maximum_extended_childcare_hours_usage, how many hours a child who uses them takes) stays as drawn.
CHILD_USAGE_VARIABLE = "max_free_entitlement_hours_used"
CLAIM_AND_USE_30_HOURS = {**CLAIM_30_HOURS, CHILD_USAGE_VARIABLE: 30.0}
EXPECTED_SCENARIOS = {
    "baseline_claim_all": {"params": [], "inputs": CLAIM_30_HOURS},
    "reform_claim_all": {"params": _REFORM, "inputs": CLAIM_30_HOURS, "base": "baseline_claim_all"},
    "baseline_claim_use_all": {"params": [], "inputs": CLAIM_AND_USE_30_HOURS},
    "reform_claim_use_all": {"params": _REFORM, "inputs": CLAIM_AND_USE_30_HOURS, "base": "baseline_claim_use_all"},
}

# ── Take-up of the 30 hours among newly eligible children (the take-up toggle) ─────────────────────────
# Three bases for who takes up the 30 hours once the limit goes (María Juaristi, 24 October 2026). DfE's rates by
# age are the headline: they are official and by age, and most of the cost is for under-3s, where the flat contract
# rate (83.6%) is well above DfE's at 9-11 months and age 1 (42%, 70%) and about level at 2 (84%). DfE's and
# CenTax's rates are child-level take-up (registered children over DfE's estimate of eligible children), so they
# include whether the family claims and whether the child uses the hours. Each applies to each child's change in
# funded hours in the claim-and-use pair above (every family claiming, every child using its hours), by the child's
# DfE age: its age on 31 December of the model year (the year less policyengine-uk's ``birth_year``), the age DfE's
# January census counts it by. DfE age 0 is the 9-11-month-olds of the spring term; a child born September to
# December who is funded for the summer term before it starts reception (aged 4 then) has DfE age 5 and takes the
# 3-and-4 rate. DfE's caveats on the rates (provisional; parental leave; 2-year-olds) are in docs/METHOD.md. The
# contract basis is the expected mode of #7: the take-up contract's flat family rate on the claim-all pair, with
# every family's hours as drawn.
DFE_TAKE_UP_URL = (
    "https://explore-education-statistics.service.gov.uk/find-statistics/funded-early-education-and-childcare/2025"
)
CENTAX_REPORT_URL = (
    "https://centax.org.uk/wp-content/uploads/2026/09/"
    "AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf"
)
TAKE_UP_BASES = {
    "dfe": {
        "label": "DfE, by age",
        "description": "DfE's take-up of the working-parent hours in January 2025: 42% at 9-11 months, 70% at "
                       "age 1, 84% at 2 and 91% at 3 and 4, child by child",
        "unit": "child",
        # Estimated % of eligible children registered, January 2025 ("Funded early education and childcare",
        # reporting year 2025, published 31 July 2025; formerly "Education provision: children under 5 years of age").
        # DfE age 5 (the summer term before reception) is in DfE's 3-and-4 group, so on every basis it keeps the
        # rate of ages 3 and 4 (tests/test_take_up.py checks it).
        "rates_by_dfe_age": {0: 0.42, 1: 0.70, 2: 0.84, 3: 0.91, 4: 0.91, 5: 0.91},
        "source": "DfE, Funded early education and childcare, January 2025",
        "source_url": DFE_TAKE_UP_URL,
        "pair": ("baseline_claim_use_all", "reform_claim_use_all"),
    },
    "centax": {
        "label": "CenTax, under 3 and 3-4",
        "description": "CenTax's assumption: 73% of children under 3 and 91% of 3- and 4-year-olds (DfE's 2025 "
                       "take-up for the two groups), child by child",
        "unit": "child",
        # Removing the childcare cliff-edge (September 2026), pp. 33-34 and 75: newly eligible parents take up as
        # today, 73% of parents of 9-month- to 2-year-olds and 91% of parents of 3- and 4-year-olds (DfE, 2025).
        "rates_by_dfe_age": {0: 0.73, 1: 0.73, 2: 0.73, 3: 0.91, 4: 0.91, 5: 0.91},
        "source": "CenTax, Removing the childcare cliff-edge, pp. 33-34 and 75",
        "source_url": CENTAX_REPORT_URL,
        "pair": ("baseline_claim_use_all", "reform_claim_use_all"),
    },
    "contract": {
        "label": "Microcosm, one rate",
        "description": f"The take-up contract's flat rate, {EXTENDED_TAKE_UP_RATE:.1%} of families, family by "
                       "family, with the dataset's draws of the hours used",
        "unit": "family",
        "rate": EXTENDED_TAKE_UP_RATE,
        "source": "Microcosm take-up contract (829c1bc26)",
        "source_url": EXTENDED_TAKE_UP_SOURCE_URL,
        "pair": ("baseline_claim_all", "reform_claim_all"),
    },
}
HEADLINE_TAKE_UP_BASIS = "dfe"
# Bootstrap over FRS source households (aggregate.bootstrap): each source household is drawn with all
# its Microcosm copies, the release weights fixed.
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20261023

# Free-hours spending: the 30-hours leg is the change in all three entitlements.
# policyengine-uk 2.147.2 keeps the universal and targeted 15 hours when a family becomes
# eligible for the extended entitlement and counts as extended only each child's hours
# above them, so the universal and targeted lines should barely move, but all three are
# summed so that nothing is missed if they do.
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
# CENTAX_REPORT_URL is with the take-up bases above.

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
# Childcare and the Universal Credit childcare element included), the same resource
# definition as its HBAI disposable-income base, with the reform's cash income
# recomputed at the spend left after displacement (the family no longer pays for that
# care, so the support tied to it goes). Published as sensitivities
# (``intensive_income_basis``): "paid_care_fixed_spend", the same gain with spending held
# fixed, and "government_cost", which counts the funded hours at their funding value.
INCOME_BASIS = "paid_care"
INCOME_BASIS_SENSITIVITIES = ("paid_care_fixed_spend", "government_cost")
# The price effect's marginal net price of paid care, 1 less every childcare-linked cash support's
# rate on the next £1 (hours_response.marginal_price_change): "remaining_spend" reads the reform's
# at the spend left after displacement, the income effect's spending; published as sensitivities
# (``intensive_price_basis``): "original_spend", at the family's spend today, and "tfc_only",
# Tax-Free Childcare alone (the Universal Credit childcare element left out).
PRICE_BASIS = "remaining_spend"
PRICE_BASIS_SENSITIVITIES = ("original_spend", "tfc_only")
# Cells within which implied entrants are allocated to non-workers (labour_supply.entry_cells):
# the OBR Table A1 groups' youngest-child bands.
YOUNGEST_CHILD_BANDS = (0, 3, 6, 11)
# The responding population: adults in a benefit unit whose youngest child is under 12
# (the Tax-Free Childcare band, which contains the 30 hours' 9 months-4 years) and in
# which at least one adult's income, as the limits test it, is over £100,000.
YOUNGEST_CHILD_MAX_AGE = 11

