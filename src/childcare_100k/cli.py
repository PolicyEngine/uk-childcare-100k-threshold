"""Build data/results.json: run (or reuse) every population job, then aggregate.

    childcare-100k-build            # run missing jobs, then write results
    childcare-100k-build --rerun    # rerun every job
    childcare-100k-build --aggregate-only
"""

import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone

import numpy as np

from . import aggregate as agg
from .config import (
    BASELINE_LIMIT,
    BENCHMARK_YEAR,
    CENTAX_REPORT_URL,
    CONSERVATIVE_ANNOUNCEMENT_URL,
    CONSERVATIVE_SOURCE_URL,
    BREWER_HOURS_URL,
    ELASTICITY_SCALES,
    FREE_HOURS_DISPLACEMENT,
    FREE_HOURS_DISPLACEMENT_RANGE,
    HOURS_FOR_NEW_ENTRANTS,
    HOURS_PRICE_ELASTICITY,
    OBR_PARTICIPATION_URL,
    UPSTREAM_COUPLE_ISSUE_URL,
    PRICE_ELASTICITY_CENTRAL,
    PRICE_ELASTICITY_HIGH,
    PRICE_ELASTICITY_LOW,
    LEAD_YEAR,
    MIN_CELL_RECORDS,
    OUTPUT,
    PRIMARY_DATASET,
    REFORM_PARAMETERS,
    REPO,
    HOURS_USAGE_VARIABLE,
    ROUTED_SHARE_LOW,
    TFC_TAKE_UP_NEWLY_ELIGIBLE_LOW,
    SCENARIOS,
    YEARS,
)
from .datasets import MICROCOSM, POLICYENGINE_UK_VERSION
from .engine import JOBS, SOURCE_DIR, is_current, load_meta, run_isolated
from .validation import DFE_FUNDING_URL
from .household import cliff_example, household_grid
from .validation import baseline_validation


def _git_revision():
    """The commit the build runs on. Raises if it cannot be read (no "unknown" placeholder), or if the package
    source differs from that commit: the revision must be the code that produced the results."""
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    if len(revision) != 40:
        raise RuntimeError(f"unexpected git revision {revision!r}")
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=REPO, capture_output=True, text=True,
                           check=True).stdout.strip()
    if dirty:
        raise RuntimeError(f"uncommitted changes under src/; commit them before building:\n{dirty}")
    return revision


# The code that turns the cached runs into results.json (the runs' own code is in run_definition_sha256).
AGGREGATION_FILES = ("aggregate.py", "cli.py", "config.py", "household.py", "validation.py")


def _aggregation_hash():
    digest = hashlib.sha256()
    for name in AGGREGATION_FILES:
        digest.update((SOURCE_DIR / name).read_bytes())
    return digest.hexdigest()


def run_all(rerun=False, log=print):
    """Run every scenario whose cached run is missing or stale (one process at a time)."""
    metas = {}
    for scenario in JOBS:
        if rerun or not is_current(scenario):
            run_isolated(scenario, REPO, log=log)
        metas[f"{PRIMARY_DATASET}/{scenario}"] = load_meta(scenario)
    return metas


def _provenance_meta(metas):
    """Provenance fields for results.json, all required: every run must share one provenance."""
    provenances = {json.dumps({k: v for k, v in m["provenance"].items() if k != "scenario"}, sort_keys=True)
                   for m in metas.values()}
    if len(provenances) != 1:
        raise RuntimeError(f"runs disagree on provenance: {sorted(provenances)}")
    prov = json.loads(provenances.pop())
    required = ("dataset", "dataset_repo", "dataset_revision", "dataset_sha256", "policyengine", "policyengine_uk",
                "run_definition_sha256")
    missing = [k for k in required if not prov.get(k)]
    if missing:
        raise RuntimeError(f"provenance fields missing: {missing}")
    bundle = metas[f"{PRIMARY_DATASET}/baseline"]["bundle"]
    for key in ("bundle_id", "policyengine_version", "model_version", "managed_by"):
        if not bundle.get(key):
            raise RuntimeError(f"policyengine.py bundle field {key!r} missing from the baseline run")
    if bundle["policyengine_version"] != prov["policyengine"]:
        raise RuntimeError("the bundle's policyengine.py version differs from the installed one")
    # The release pins policyengine-uk 2.147.2, which no policyengine.py bundle carries yet: the
    # installed model must be the pinned one, and the bundle's own model version is recorded.
    if prov["policyengine_uk"] != POLICYENGINE_UK_VERSION:
        raise RuntimeError(f"runs used policyengine-uk {prov['policyengine_uk']}, not {POLICYENGINE_UK_VERSION}")
    return {
        "policyengine": prov["policyengine"],
        "policyengine_uk": prov["policyengine_uk"],
        "policyengine_bundle": bundle["bundle_id"],
        "policyengine_bundle_model_version": bundle["model_version"],
        "dataset": prov["dataset"],
        "dataset_label": MICROCOSM.label,
        "dataset_release": MICROCOSM.release,
        "dataset_repo": prov["dataset_repo"],
        "dataset_revision": prov["dataset_revision"],
        "dataset_sha256": prov["dataset_sha256"],
        # No policyengine.py bundle registers the release yet, so the runs pass the verified
        # file to managed_microsimulation(allow_unmanaged=True): policyengine.py builds the
        # simulation, datasets.py pins the data (revision and sha256, checked every run).
        "dataset_management": "pinned_by_repo_unmanaged_by_bundle",
        "dataset_status": DATASET_STATUS,
        "lead_year": LEAD_YEAR,
        "run_provenance": prov,
    }


DATASET_STATUS = (
    "Cut on 23 October 2026 from PolicyEngine/microcosm 829c1bc26, a head of #1338 before its last commit (#1338 "
    "merged later that day at a12885f9), with its own signed release certification, and run on policyengine-uk "
    "2.147.2, the version its manifest pins. It is "
    "published as a non-default release (the national line still points at 6cba5d71). No policyengine.py bundle "
    "registers it yet, so this repository pins the file by revision and sha256."
)

LIMITATIONS = [
    "Eligibility uses each parent's realised annual adjusted net income, while the law tests the income a parent "
    "expects when applying or reconfirming (SI 2022/1134 reg 14(3)(c)(i) and 15(3)(b)(i); SI 2015/448 reg 15(1)). "
    "A parent who expected to stay under £100,000 but ended the year above it can already receive support, and the "
    "model counts it as a reform cost; a parent who expected to exceed £100,000 but ended below it is modelled as "
    "eligible today. CenTax found that a third (33%) of parents whose year-end income was £100,000-£120,000 claimed "
    "and received some free childcare (Removing the childcare cliff-edge, September 2026, pp. 5-6 and 59-60). The "
    "net direction for the cost is not known, and it is not tested.",
    "The release is cut from Microcosm #1338 at 829c1bc26, before its last commit (a12885f9). So it does not key "
    "the under-2 working-parent take-up draw on DfE's age at 31 December (it uses age at 6 October, so its age-0 rate mixes "
    "9-11-month-olds with children aged 12-14 months), and its DfE rows bind the January 2025 census, a year before "
    "the spring term of 2025-26. Both bear on the under-3 cost of the 30 hours.",
    "In the reform, each child's childcare spending is reduced by the value of its new funded hours at the funding "
    "rate before Tax-Free Childcare is computed. Fees are above funding rates, so this removes less spending than "
    "the hours replace and the Tax-Free Childcare leg may still be a little high. The hours response's income "
    "effect recomputes the family's cash income on the care it still buys, on its own displacement rule.",
    "A partner who does not work because of caring or incapacity qualifies through the benefits the data hold "
    "(policyengine-uk 2.147.2 applies SI 2022/1134 reg 14(4)/15(4) and SI 2015/448 reg 13), but not through limited "
    "capability for work, NI credits or carer's leave, which the data do not hold.",
    "Breakdown cells resting on fewer than ten gaining or changed records are suppressed, and where a single cell "
    "would be suppressed a second is suppressed with it (or the whole breakdown, if no second cell can protect it), "
    "so no suppressed cell can be recovered from the published UK totals.",
]


def _validation_value(rows, label, year):
    """A model figure from the baseline validation rows. Raises if the row is missing."""
    matches = [r for r in rows if r["label"] == label and r["year"] == year]
    if len(matches) != 1:
        raise KeyError(f"baseline_validation has {len(matches)} rows for {label!r} in {year}")
    return matches[0]


def data_limitations(rows):
    """Limitations stated with this dataset's own validation figures (the figures live in baseline_validation)."""
    free = _validation_value(rows, "Free early years entitlements spending (all three entitlements)", 2026)
    ratio = free["model"] / free["official"] - 1
    versus = f"about {abs(ratio):.0%} {'above' if ratio > 0 else 'below'}"
    return [
        f"Funded hours, baseline context: the baseline's free-hours spending in 2026-27 is {versus} DfE's "
        "illustrative total (see baseline_validation). DfE's totals are illustrative (based partly on forecasts) and "
        "are context only: matching the aggregate baseline does not bound the incremental cost for newly eligible "
        "families above £100,000, whose take-up and hours may differ.",
    ]


def concentration_limitation(concentration, year):
    """How much of the static cost rests on the few largest-gaining weighted records."""
    c = concentration[str(year)]
    return (f"The static cost rests on {c['gaining_sample_size']:,} gaining survey records in {_fy(year)} (a Kish "
            f"effective sample size of about {c['kish_effective_sample_size']:,}); the ten largest (by weight times "
            f"gain) carry {c['top_ten_share_pct']:.0f}% of it and the largest alone {c['largest_share_pct']:.0f}%. "
            "No bootstrap of the sampling noise has been run on this release; on the previous one (a858c100) the "
            f"Microcosm team's bootstrap over FRS source households gave a standard deviation of about "
            f"£{PREVIOUS_BOOTSTRAP_SD_BN[LEAD_YEAR]:.2f}bn in {_fy(LEAD_YEAR)} and "
            f"£{PREVIOUS_BOOTSTRAP_SD_BN[BENCHMARK_YEAR]:.2f}bn in {_fy(BENCHMARK_YEAR)} on the 30 funded hours.")


SALARY_SACRIFICE_URL = (
    "https://www.gov.uk/government/publications/salary-sacrifice-reform-for-pension-contributions-effective-from-"
    "6-april-2029/salary-sacrifice-reform-for-pension-contributions"
)
PEUK = "https://github.com/PolicyEngine/policyengine-uk/blob/2.147.2/policyengine_uk/variables/gov"
MICROCOSM_UK = "https://github.com/PolicyEngine/microcosm/blob/main/packages/microcosm-build/src/microcosm/build/uk"
THIS_REPO = "https://github.com/PolicyEngine/uk-childcare-100k-threshold/blob/main/src/childcare_100k"


def _src(label, url):
    return {"label": label, "url": url}


LSR_ALTERNATIVE = ("Parents respond: partners move into work (OBR participation elasticities), and parents in work "
                   "change their hours as the price of an extra hour of childcare falls and as their family's "
                   "income rises (a childcare-price and an OBR income elasticity)")


def modelling_assumptions(a, effects, labour_supply_offset, tfc):
    """The choices behind every figure, each as the code makes it, with the tested alternative's effect where there is one."""
    e30, etfc = a["would_claim_30_hours_pct"], a["would_claim_tfc_pct"]
    return [
        {
            "id": "static",
            "title": "No change in work, pay or childcare",
            "ours": "No change in work, pay or pension contributions",
            "source_says": "CenTax allow for parents earning more and partners entering work (see the comparison on Budget impact)",
            "source": _src("CenTax, Table 4.2", CENTAX_REPORT_URL),
            "modelled": "Both runs use the same households with the same earnings, hours of work and childcare "
                        "spending. Nobody works more or less, or changes their pension contributions, because the "
                        "limit goes.",
            "sources": [
                _src("Our runs (engine.py)", f"{THIS_REPO}/engine.py"),
                _src("Moving into work (labour_supply.py)", f"{THIS_REPO}/labour_supply.py"),
                _src("Hours (hours_response.py)", f"{THIS_REPO}/hours_response.py"),
                _src("OBR participation and income elasticities", OBR_PARTICIPATION_URL),
                _src("Brewer et al., hours", BREWER_HOURS_URL),
            ],
            "alternative": LSR_ALTERNATIVE,
            # Money back to the Exchequer lowers the cost.
            "effect_bn": {y: round(-v, 3) for y, v in labour_supply_offset.items()},
        },
        {
            "id": "take_up",
            "title": "Who claims",
            "ours": f"{int(e30['families_with_child_under_5'] + 0.5)}% of eligible families claim the 30 hours; "
                    f"{int(etfc['families_with_child_under_12'] + 0.5)}% of families carry a Tax-Free Childcare claim "
                    "flag, but only those reporting paid registered childcare get a top-up",
            "source_says": "Dataset draws, calibrated in Microcosm's take-up contract",
            "source": _src("Microcosm take-up contract", f"{MICROCOSM_UK}/take_up_contract.json"),
            "modelled": "Each family's decision to claim comes from the dataset's existing take-up draws, held "
                        "fixed for newly eligible families: a family that would not claim today does not claim under "
                        "the reform either. The Tax-Free Childcare draw is a claim flag fitted to HMRC's top-up and "
                        "account counts, not a take-up rate: a family gets a top-up only on the paid registered "
                        "childcare it reports, so use is limited by reported spending (the table shows both). "
                        "Nothing identifies take-up among families over £100,000, who are not eligible today, so the "
                        "alternative sets it to 70% of newly eligible families, about today's use among all eligible "
                        "families.",
            "sources": [
                _src("Microcosm take-up contract", f"{MICROCOSM_UK}/take_up_contract.json"),
                _src("would_claim_extended_childcare",
                     f"{PEUK}/dfe/extended_childcare_entitlement/would_claim_extended_childcare.py"),
                _src("would_claim_tfc", f"{PEUK}/hmrc/tax_free_childcare/would_claim_tfc.py"),
                _src("How we compute the rates (aggregate.py)", f"{THIS_REPO}/aggregate.py"),
                _src("Microcosm's take-up analysis (#8)", TFC_TAKE_UP_SOURCE_URL),
            ],
            "alternative": f"{TFC_TAKE_UP_NEWLY_ELIGIBLE_LOW:.0%} of newly eligible families claim Tax-Free Childcare",
            "effect_bn": {y: round(tfc["take_up_newly_eligible_low"][y] - tfc["central"][y], 3) for y in tfc["central"]},
        },
        {
            "id": "hours",
            "title": "Hours of childcare used",
            "ours": f"About {a['mean_extended_hours_usage']:.0f} of the 30 extended hours a week",
            "source_says": "DfE January 2025 census implies about 28.5 hours",
            "source": _src("DfE funding technical note", DFE_FUNDING_URL),
            "modelled": "Each family's weekly extended hours come from the dataset's draw of "
                        f"{HOURS_USAGE_VARIABLE}, which averages about {a['mean_extended_hours_usage']:.0f} of the "
                        "30 hours: since PolicyEngine/microcosm#1126 the draw is set to DfE's January 2025 census, "
                        "about 28.5 (earlier releases drew about 15). policyengine-uk keeps a 3- or 4-year-old's universal 15 "
                        "hours when the family becomes eligible for the extended hours and counts only the hours "
                        "above them as extended, so a family that becomes eligible never loses funded hours.",
            "sources": [
                _src(HOURS_USAGE_VARIABLE,
                     f"{PEUK}/dfe/extended_childcare_entitlement/{HOURS_USAGE_VARIABLE}.py"),
                _src("Microcosm take-up contract", f"{MICROCOSM_UK}/take_up_contract.json"),
                _src("microcosm#1126", "https://github.com/PolicyEngine/microcosm/issues/1126"),
                _src("DfE funding technical note", DFE_FUNDING_URL),
            ],
            "alternative": "Every family uses all 30 extended hours",
            "effect_bn": effects["full_30_hour_usage"],
        },
        {
            "id": "under_ones",
            "title": "Babies under one",
            "ours": "From the first term after a child turns 9 months",
            "source_says": "Eligible from the term after the child turns 9 months",
            "source": _src("GOV.UK: childcare if you work", "https://www.gov.uk/free-childcare-if-working"),
            "modelled": "policyengine-uk starts the working-parent hours on 1 September, 1 January or 1 April after a "
                        "child turns 9 months, each term a third of the year, and ends the funded hours when a child "
                        "starts reception. Both dates come from the date of birth, which the release holds as age and "
                        "months since the last birthday.",
            "sources": [
                _src("extended_childcare_entitlement_term_share",
                     f"{PEUK}/dfe/extended_childcare_entitlement/extended_childcare_entitlement_term_share.py"),
                _src("policyengine-uk#2570", "https://github.com/PolicyEngine/policyengine-uk/pull/2570"),
            ],
        },
        {
            "id": "income_test",
            "title": "The income each limit tests",
            "ours": "Income after pension contributions; 59% of childcare spending through Tax-Free Childcare",
            "source_says": "The law deducts pension contributions (ITA 2007 s58)",
            "source": _src("Income Tax Act 2007 s58", "https://www.legislation.gov.uk/ukpga/2007/3/section/58"),
            "modelled": "Adjusted net income as policyengine-uk computes it: each parent's realised income for the "
                        "year, after pension contributions and Gift Aid. Tax-Free Childcare is paid on the dataset's "
                        "share of childcare spending that goes through an account (59%).",
            "sources": [
                _src("Income Tax Act 2007 s58", "https://www.legislation.gov.uk/ukpga/2007/3/section/58"),
                _src("adjusted_net_income", f"{PEUK}/hmrc/income_tax/adjusted_net_income.py"),
                _src("Tax-Free Childcare share of spending (Microcosm)", f"{MICROCOSM_UK}/take_up_contract.json"),
            ],
            "alternative": f"Put {ROUTED_SHARE_LOW:.0%} of childcare spending through Tax-Free Childcare accounts",
            "effect_bn": effects[agg.ROUTED_LOW],
        },
        {
            "id": "timing",
            "title": "In force for the whole year",
            "ours": "Whole of each year from 2026-27",
            "source_says": "\"A future Conservative government\"; no start date",
            "source": _src("Conservative announcement", CONSERVATIVE_ANNOUNCEMENT_URL),
            "modelled": "The limit is removed for the whole of each fiscal year from 2026-27 to 2029-30. The pledge "
                        "gives no start date and 2026-27 is already half over, so 2026-27 is illustrative.",
            "sources": [_src("Conservative announcement", CONSERVATIVE_ANNOUNCEMENT_URL)],
        },
    ]


# CenTax, Removing the childcare cliff-edge (September 2026), Table 4.2: static cost of removing the limit on
# the free hours, by our fiscal-year key (CenTax's "2028" is 2027-28 and "2030" is 2029-30), after and before
# their deduction for parents bunching just under £100,000.
CENTAX_STATIC_BN = {2027: 0.80, 2029: 0.98}
CENTAX_STATIC_BEFORE_BUNCHING_BN = {2027: 0.86, 2029: 1.07}
# Sampling noise on the 30 funded hours' static cost: a bootstrap over FRS source households by the Microcosm
# team on the previous release, a858c100 (María Juaristi, uk-childcare-100k-threshold#8, 21 October 2026). None
# has been run on a133f37a.
PREVIOUS_BOOTSTRAP_SD_BN = {2027: 0.13, 2029: 0.18}
# Microcosm's analysis of the Tax-Free Childcare claim flag and the netting of new funded hours (#8, 22 October 2026).
TFC_TAKE_UP_SOURCE_URL = "https://github.com/PolicyEngine/uk-childcare-100k-threshold/pull/8"


def moved_outside_note(population):
    """Whether the reform changes anyone's gain to work outside the responding population."""
    moved = {y: p["adults_moved_outside_population"] for y, p in population.items()}
    if not any(moved.values()):
        return ("Outside the responding population the reform leaves every adult's gain to work unchanged, in "
                "every year.")
    years = [y for y, v in moved.items() if v]
    return ("Outside the responding population the reform should leave every adult's gain to work unchanged. In "
            + " and ".join(f"{_fy(int(y))} (about {moved[y]:,.0f} adults)" for y in years)
            + " it does not: in 2026-27 these are non-working adults whose own income is just under £100,000, so "
            "entering work would take them over the limit; the reform raises their gain to work by under £100 a "
            "year. They are not given a response, and the effect on the cost is negligible.")


def _fy(year):
    return f"{year}-{(year + 1) % 100:02d}"


def build(metas):
    runs = agg.load(SCENARIOS)
    budget = agg.budget_block(runs)
    sens = agg.sensitivities(runs)
    # The central figure is the published gross total, to the last rounded digit.
    sens["range_bn"]["central"] = dict(budget["total"])
    validation = baseline_validation(runs)
    assumptions = agg.assumptions(runs)
    limitations = list(LIMITATIONS)
    concentration = agg.concentration(runs)
    limitations[-1:] = (data_limitations(validation) + [concentration_limitation(concentration, LEAD_YEAR)]
                        + limitations[-1:])
    tfc = agg.tax_free_childcare_leg(runs)

    lsr = agg.labour_supply(budget["total"])
    grid = household_grid()
    y = str(BENCHMARK_YEAR)
    thirty = budget["thirty_hours"][y]
    results = {
        "meta": {
            **_provenance_meta(metas),
            "years": YEARS,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_revision": _git_revision(),
            "aggregation_sha256": _aggregation_hash(),
            "min_cell_size": MIN_CELL_RECORDS,
            "run_seconds": {k: v["seconds"] for k, v in metas.items()},
            "peak_rss_gb": {k: v["peak_rss_gb"] for k, v in metas.items()},
        },
        "reform": {
            "title": "Remove the £100,000 income limit on 30 funded hours and Tax-Free Childcare",
            "description": (
                "The Conservative pledge (announced 4 October 2026, with no start date) to remove the £100,000 adjusted-net-income limit, "
                "tested on each parent, for the 30 funded hours for working parents in England (children aged 9 "
                "months to 4 years) and for Tax-Free Childcare (UK-wide: £2 top-up for every £8 paid in, up to "
                "£2,000 a child a year, £4,000 if disabled). The universal 15 hours for 3- and 4-year-olds is "
                "unaffected. Static microsimulation on the Microcosm UK 2024-25 national release, 2026-27 to "
                "2029-30."
            ),
            "parameters": [{"name": n, "baseline": BASELINE_LIMIT, "reform": "removed"} for n in REFORM_PARAMETERS],
        },
        "budget": {
            "gross_bn": {k: budget[k] for k in ("thirty_hours", "tax_free_childcare", "total")},
            "net_bn": {"total": budget["net_total"]},
            "thirty_hours_components_bn": agg.thirty_hours_components(runs),
            # The Tax-Free Childcare leg: central (new funded hours netted off childcare spending), before that
            # netting, and with take-up among newly eligible families at 70% (expectation basis).
            "tax_free_childcare_bn": tfc,
            "range_bn": sens["range_bn"],
            "sensitivities": {
                "effects_bn": sens["effects_bn"],
                "low": [agg.ROUTED_LOW],
                "high": ["full_30_hour_usage"],
                "descriptions": {
                    "full_30_hour_usage": "Every family uses all 30 extended hours (baseline and reform); "
                                          f"the data draw a mean of about {assumptions['mean_extended_hours_usage']:.0f} "
                                          "(microcosm#1126), so this raises the cost only a little.",
                    agg.ROUTED_LOW: f"Only {ROUTED_SHARE_LOW:.0%} of childcare spending goes through a Tax-Free "
                                    "Childcare account (baseline and reform). Lowers the cost.",
                },
            },
        },
        "reconciliation": {
            "concentration": concentration,
            "parents_over_100k_with_child_under_5_thousands": agg.parents_over_limit(runs),
            "centax_parents_over_100k": 200_000,
        },
        "recipients": agg.recipients(runs),
        "distribution": agg.distribution(runs),
        "gender": agg.gender(runs),
        "baseline_validation": validation,
        "assumptions": {"microcosm": assumptions},
        "cliff_example": cliff_example(grid),
        "household_grid": grid,
        "modelling_assumptions": modelling_assumptions(assumptions, sens["effects_bn"],
                                                       lsr["total_offset_bn"]["central"], tfc),
        "labour_supply": {
            **lsr,
            "assumptions": {
                "participation_elasticities": "OBR Table A1, by sex, partner's work, age of youngest child and "
                                              "earnings quintile, converted to the gain to work and applied to the "
                                              "employed share (Adam and Phillips, Appendix E)",
                "price_elasticity_central": PRICE_ELASTICITY_CENTRAL,
                "price_elasticity_low": PRICE_ELASTICITY_LOW,
                "price_elasticity_high": PRICE_ELASTICITY_HIGH,
                "elasticity_scales": {k: round(v, 4) for k, v in ELASTICITY_SCALES.items()},
                "hours_price_elasticity": HOURS_PRICE_ELASTICITY,
                "income_elasticities": "Table A2, by sex, whether in a couple and age of youngest child: from "
                                       "-0.185 (a woman in a couple, youngest child 0-2) to -0.037 (a lone "
                                       "mother, youngest 0-4); -0.05 for a man in a couple",
                "couples": "The OBR groups (Tables A1 and A2) apply to married and cohabiting couples alike. "
                           "policyengine-uk assigns them by legal marriage, which would give a cohabiting father no "
                           "elasticity and a cohabiting mother the lone-parent rates (about a fifth of couples with "
                           "children are not married); we assign them by whether the adult is in a couple.",
                "couples_issue_url": UPSTREAM_COUPLE_ISSUE_URL,
                "hours_for_new_entrants": HOURS_FOR_NEW_ENTRANTS,
                "free_hours_displacement": round(FREE_HOURS_DISPLACEMENT, 4),
                "free_hours_displacement_range": {k: round(v, 4) for k, v in FREE_HOURS_DISPLACEMENT_RANGE.items()},
                "hours_price_elasticity_status": "extrapolated scenario assumption, not an estimated price elasticity",
                "elasticity_scales_status": "illustrative, not a sourced uncertainty interval",
            },
            "responding_population": (
                "Every adult (the first two in each family; not self-employed, students or aged 60 and over, the "
                "OBR's exclusions) in a family whose youngest child is under 12 and in which at least one adult's "
                "income, as the limits test it, is over £100,000: the parent over the limit as well as their "
                "partner. Those not in work may move into work, except disabled adults (receiving DLA or PIP), "
                "whom the OBR excludes from participation (Table A4) but not from hours (Table A3); those in work "
                "may change their hours."
            ),
            "not_modelled": "Bunching: parents who today keep their income at or just below "
                            "£100,000 and would earn more without the limit.",
            "notes": [
                "The dynamic cost is an illustrative scenario, not a forecast: its hours price elasticity is "
                "extrapolated, the OBR elasticities are not measured on parents over £100,000, and its range is "
                "not a confidence interval. Offsets are £bn a year; positive is money back to the Exchequer. The "
                "dynamic cost is the static total less the two offsets (moving into work and hours), at the same "
                "bound; the hours offset is its price effect (money back) plus its income effect (money out). "
                "They apply to the total: they are not split by scheme.",
                "Moving into work (extensive margin): the OBR elasticities are the percentage change in the "
                "probability of working for a percentage change in the gain to work (net of the childcare a parent "
                "would buy), converted from in-work income by the gain over in-work income. As in Adam and "
                "Phillips (Appendix E) they apply to the employed share: new employment is the sum over working "
                "adults of their own response, and it is shared among the non-working adults like them (who are "
                "the ones entering): those in the same OBR cell (sex, couple, age band of the youngest child, "
                "earnings quintile), in proportion to their own response, or, where the cell has no responding "
                "non-worker, in the nearest coarser cell (allocated_by_cell_level). The offset is entrants' earnings less the rise in their "
                "household's net income (tax and National Insurance paid, less the childcare support the family "
                "now receives) and less the Tax-Free Childcare top-up on the care they start buying. Entrants placed "
                "in a coarser cell take the non-workers' earnings, gain and subsidy from other earnings quintiles; "
                "entry_sensitivity reports the offset with them dropped (same_cell_only) and with them given the "
                "weighted median hourly wage of the workers who imply them, gain and subsidy recomputed "
                "(worker_profile), at central elasticities.",
                "Hours (intensive margin), for every responding adult in work, at or below £100,000 and over it, "
                "in two parts. The model recomputes tax and benefits once, on everyone's combined earnings change; "
                "the parts are an attribution that adds up to it (the price change recomputed alone, the income "
                "effect the remainder; the at-or-below group alone, the over group the remainder). Price "
                f"effect: {HOURS_PRICE_ELASTICITY} times the change in the price of the family's marginal hour of "
                "paid childcare, for adults whose family pays for childcare. The elasticity is an extrapolated "
                "scenario assumption, not an estimated price elasticity: Brewer et al. estimate +0.600 weekly hours "
                "for mothers whose youngest child becomes eligible for full-time rather than part-time free care, "
                "treated as a 100% price fall; it is a total-hours estimate, so it overlaps with the extensive "
                "margin. The marginal price is net of all the childcare-linked cash support on the next pound of "
                "spend, the model's own (Tax-Free Childcare, the Universal Credit childcare element and the other "
                "payments tied to childcare_expenses), read by raising the family's spend by £1 (not 1%, which near a "
                "cap averages over spending beyond it), today and, under the reform, at the spend the family still makes "
                "once the funded hours displace paid care; intensive_price_basis publishes it at today's spend "
                "(original_spend) and with Tax-Free Childcare alone (tfc_only). The 30 "
                "funded hours are a fixed "
                "amount, conditional only on both parents meeting the minimum earnings test, so for a family that "
                "still buys paid care on top of them they do not change what an extra hour costs; they lower the "
                "marginal price (to zero) only where they are worth more than all the paid care the family buys. "
                "Income effect: the OBR income elasticities (Table A2, policyengine-uk's "
                "calculate_labour_net_income_elasticities, assigned to married and cohabiting couples alike) times "
                "the household's static gain as a percentage of its disposable income, as policyengine-uk's "
                "apply_progression_responses applies them except for the income measure. The gain is on the same "
                "disposable-income basis: the change in cash income (Tax-Free Childcare included) plus the paid "
                "childcare the newly funded hours displace (their value at the displacement rate below, capped at "
                "what the family pays), with the reform's cash income recomputed by the model on the care the family "
                "still buys, so Tax-Free Childcare and the Universal Credit childcare element on the displaced "
                "spend go; not the funded hours at government cost. intensive_income_basis publishes the gain with "
                "spending held fixed (paid_care_fixed_spend) and at government cost (government_cost). Neither "
                "elasticity is "
                "measured on parents over £100,000.",
                "Whether newly funded hours cover a family's paid care, and how much paid care they save it, is "
                "judged on value, with funded hours "
                f"assumed to displace paid care at {FREE_HOURS_DISPLACEMENT:.1%} of their value (1 - 54/570, IFS "
                "BN189, which counts all displaced non-family care as paid). It is an assumption, published at "
                f"{FREE_HOURS_DISPLACEMENT_RANGE['low']:.1%} (only subsidisable care displaced, 1 - 163/570) and "
                f"{FREE_HOURS_DISPLACEMENT_RANGE['high']:.0%} (intensive_displacement), at central elasticities.",
                "Low and high scale every elasticity (participation, price and income) by 1/3 and 2. The range is illustrative, not a sourced "
                "uncertainty interval: the factors are ratios of childcare-price elasticities of maternal "
                "employment (-0.05 and -0.30 against -0.15), a different outcome from the elasticities they scale.",
                "The income and family-type breakdowns, who gains and the household calculator are static.",
                moved_outside_note(lsr["population"]),
            ],
        },
        "benchmarks": [
            {
                "source": "Conservative Party",
                "figure": "£0.7bn a year",
                "ours": thirty,
                "ours_label": f"Static gross cost of the 30 funded hours in {_fy(BENCHMARK_YEAR)}",
                "year": BENCHMARK_YEAR,
                "like_for_like": (
                    "The Conservatives put the cost at about £700m a year when they announced the pledge (PA, "
                    "BBC), to be paid for by cutting staff at arm's-length public bodies (about £1.6bn by the end of "
                    "the decade); they published no method. City AM says the costing 'is based on a recent report by "
                    "the Centre for the Analysis of Taxation' and that removing the Tax-Free Childcare limit as well "
                    "'pushed up the costs slightly'. CenTax (Removing the childcare cliff-edge: impacts and cost of "
                    "reform, September 2026, Table 4.2) covers the free childcare hours only: a static cost of £980m "
                    "in 2030 (CenTax label tax years by their later year, so this is 2029-30) and a net cost of £640m "
                    "after £340m of extra revenue: £210m of tax from parents who no longer keep their income below "
                    "£100,000 and £130m of tax and National Insurance from partners who enter work. The £0.7bn is "
                    "therefore close to CenTax's net free-hours figure with a small addition for Tax-Free Childcare. "
                    "Our figures are static, so the like-for-like comparison is our static cost of the 30 funded "
                    f"hours in {_fy(BENCHMARK_YEAR)}, £{thirty:.2f}bn, against CenTax's static £0.98bn "
                    f"(£{CENTAX_STATIC_BEFORE_BUNCHING_BN[BENCHMARK_YEAR]:.2f}bn before their deduction for bunching): "
                    f"{abs(thirty / CENTAX_STATIC_BN[BENCHMARK_YEAR] - 1):.0%} "
                    f"{'above' if thirty > CENTAX_STATIC_BN[BENCHMARK_YEAR] else 'below'} it "
                    f"(in {_fy(LEAD_YEAR)}, £{budget['thirty_hours'][str(LEAD_YEAR)]:.2f}bn against CenTax's "
                    f"£{CENTAX_STATIC_BN[LEAD_YEAR]:.2f}bn for 2028, £{CENTAX_STATIC_BEFORE_BUNCHING_BN[LEAD_YEAR]:.2f}bn "
                    "before bunching). Our total for both schemes, "
                    f"£{budget['total'][y]:.2f}bn (range £{sens['range_bn']['low'][y]:.2f}bn to "
                    f"£{sens['range_bn']['high'][y]:.2f}bn), covers both schemes on the same static basis."
                ),
                "url": CONSERVATIVE_SOURCE_URL,
                "announcement_url": CONSERVATIVE_ANNOUNCEMENT_URL,
                "underlying_source": "CenTax, Removing the childcare cliff-edge: impacts and cost of reform (2026)",
                "underlying_source_url": CENTAX_REPORT_URL,
                "underlying_static_bn": CENTAX_STATIC_BN[BENCHMARK_YEAR],
                "underlying_static_by_year_bn": {str(k): v for k, v in CENTAX_STATIC_BN.items()},
                "underlying_static_before_bunching_by_year_bn": {
                    str(k): v for k, v in CENTAX_STATIC_BEFORE_BUNCHING_BN.items()},
                "underlying_net_bn": 0.64,
                "difference_from_underlying_static_bn": round(thirty - CENTAX_STATIC_BN[BENCHMARK_YEAR], 3),
            }
        ],
        "limitations": limitations,
    }
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rerun", action="store_true", help="rerun every population job")
    ap.add_argument("--aggregate-only", action="store_true", help="only aggregate existing runs")
    a = ap.parse_args(argv)
    t0 = time.time()
    if a.aggregate_only:
        metas = {f"{PRIMARY_DATASET}/{s}": load_meta(s) for s in JOBS}
    else:
        metas = run_all(rerun=a.rerun)
    results = build(metas)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUTPUT} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
