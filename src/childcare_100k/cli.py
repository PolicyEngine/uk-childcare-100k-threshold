"""Build data/results.json: run (or reuse) every population job, then aggregate.

    childcare-100k-build            # run missing jobs, then write results
    childcare-100k-build --rerun    # rerun every job
    childcare-100k-build --aggregate-only
"""

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone

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
    SCENARIOS,
    YEARS,
)
from .datasets import MICROCOSM
from .engine import JOBS, is_current, load_meta, run_isolated
from .validation import DFE_FUNDING_URL
from .household import cliff_example, household_grid
from .validation import baseline_validation


def _git_revision():
    """The commit the build runs on. Raises if it cannot be read (no "unknown" placeholder)."""
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    if len(revision) != 40:
        raise RuntimeError(f"unexpected git revision {revision!r}")
    return revision


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
    if bundle["policyengine_version"] != prov["policyengine"] or bundle["model_version"] != prov["policyengine_uk"]:
        raise RuntimeError("the bundle's versions differ from the installed versions")
    return {
        "policyengine": prov["policyengine"],
        "policyengine_uk": prov["policyengine_uk"],
        "policyengine_bundle": bundle["bundle_id"],
        "dataset": prov["dataset"],
        "dataset_label": MICROCOSM.label,
        "dataset_release": MICROCOSM.release,
        "dataset_repo": prov["dataset_repo"],
        "dataset_revision": prov["dataset_revision"],
        "dataset_sha256": prov["dataset_sha256"],
        # policyengine.py 6.2.1's bundle does not register the certified release, so the runs pass
        # the verified file to managed_microsimulation(allow_unmanaged=True): policyengine.py runs
        # the model, datasets.py certifies the data (pinned revision and sha256, checked every run).
        "dataset_management": "pinned_by_repo_unmanaged_by_bundle",
        "lead_year": LEAD_YEAR,
        "run_provenance": prov,
    }


LIMITATIONS = [
    "Eligibility uses each parent's realised annual adjusted net income, while the law tests the income a parent "
    "expects when applying or reconfirming (SI 2022/1134 reg 14(3)(c)(i) and 15(3)(b)(i); SI 2015/448 reg 15(1)). "
    "A parent who expected to stay under £100,000 but ended the year above it can already receive support, and the "
    "model counts it as a reform cost; a parent who expected to exceed £100,000 but ended below it is modelled as "
    "eligible today. CenTax found that a third (33%) of parents whose year-end income was £100,000-£120,000 claimed "
    "and received some free childcare (Removing the childcare cliff-edge, September 2026, pp. 5-6 and 59-60). The "
    "net direction for the cost is not known, and it is not tested.",
    "Four-year-olds in reception still receive funded hours in the model (compulsory school age starts at 5), which "
    "overstates the funded 3- and 4-year-olds slightly.",
    "Childcare spending is held fixed: a family that gains funded hours would in practice pay for fewer hours, which "
    "would cut its Tax-Free Childcare top-up; the combined cost is overstated slightly. The hours response's income "
    "effect counts the paid care the funded hours displace, but likewise leaves the top-up on that care in place.",
    "Funded hours are valued at the model's hourly funding rates (2024-25 rates uprated by CPI), 1-6% below DfE's "
    "2026-27 national average rates (see baseline_validation), so the 30-hours leg is slightly understated.",
    "A partner who does not work because of caring or incapacity: for the 30 hours the model now applies SI "
    "2022/1134 reg 14(4)/15(4) through the benefits it holds (carer's allowance, ESA, incapacity benefit, severe "
    "disablement allowance, the Universal Credit carer element; corrections.py), but not limited capability for work "
    "or NI credits, which the data do not hold. Tax-Free Childcare's route (SI 2015/448 reg 13: the partner is "
    "regarded as in qualifying paid work with the minimum income) is applied the same way (corrections.py, "
    "mirroring policyengine-uk#2079) for incapacity benefit, severe disablement allowance, carer's allowance, "
    "Scottish carer support payment and contributory ESA, but not NI credits or carer's leave.",
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


FUNDED_HOURS_SPENDING = "Free early years entitlements spending"


def data_limitations(rows):
    """Limitations stated with this dataset's own validation figures."""
    free = _validation_value(rows, "Free early years entitlements spending (all three entitlements)", 2026)
    free30 = _validation_value(
        rows, "Free early years entitlements spending if every family used all 30 extended hours", 2026)
    high = _validation_value(rows, "People with income of £100,000 or more", 2025)
    return [
        f"Funded hours, baseline context: the central baseline spends £{free['model']:.1f}bn on "
        f"free hours in 2026-27 against DfE's £{free['official']:.1f}bn, while full 30-hour use gives "
        f"£{free30['model']:.1f}bn. DfE's total is illustrative (based partly on forecasts) and is context only: "
        "bracketing the aggregate baseline does not bound the incremental cost for newly eligible families above "
        "£100,000, whose take-up and hours may differ. Most of the gap is the dataset's draw of weekly "
        "extended hours used; it is filed upstream as PolicyEngine/microcosm#1126.",
        f"Microcosm holds {high['model'] / 1e6:.2f} million people with income of £100,000 or more in 2025-26 "
        f"against HMRC's projected {high['official'] / 1e6:.2f} million (see baseline_validation).",
    ]


SALARY_SACRIFICE_URL = (
    "https://www.gov.uk/government/publications/salary-sacrifice-reform-for-pension-contributions-effective-from-"
    "6-april-2029/salary-sacrifice-reform-for-pension-contributions"
)
PEUK = "https://github.com/PolicyEngine/policyengine-uk/blob/2.102.3/policyengine_uk/variables/gov"
MICROCOSM_UK = "https://github.com/PolicyEngine/microcosm/blob/main/packages/microcosm-build/src/microcosm/build/uk"
THIS_REPO = "https://github.com/PolicyEngine/uk-childcare-100k-threshold/blob/main/src/childcare_100k"


def _src(label, url):
    return {"label": label, "url": url}


LSR_ALTERNATIVE = ("Parents respond: partners move into work (OBR participation elasticities), and parents in work "
                   "change their hours as the price of an extra hour of childcare falls and as their family's "
                   "income rises (a childcare-price and an OBR income elasticity)")


def modelling_assumptions(a, effects, labour_supply_offset):
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
            "ours": f"{int(e30['families_with_child_under_5'] + 0.5)}% of eligible families claim the 30 hours and "
                    f"{int(etfc['families_with_child_under_12'] + 0.5)}% Tax-Free Childcare, unchanged by the reform",
            "source_says": "Dataset draws, calibrated in Microcosm's take-up contract",
            "source": _src("Microcosm take-up contract", f"{MICROCOSM_UK}/take_up_contract.json"),
            "modelled": "Each family's decision to claim comes from the dataset's existing take-up draws, held "
                        "fixed for newly eligible families: a family that would not claim today does not claim under "
                        "the reform either. The table shows the rates the draws give.",
            "sources": [
                _src("Microcosm take-up contract", f"{MICROCOSM_UK}/take_up_contract.json"),
                _src("would_claim_extended_childcare",
                     f"{PEUK}/dfe/extended_childcare_entitlement/would_claim_extended_childcare.py"),
                _src("would_claim_tfc", f"{PEUK}/hmrc/tax_free_childcare/would_claim_tfc.py"),
                _src("How we compute the rates (aggregate.py)", f"{THIS_REPO}/aggregate.py"),
            ],
        },
        {
            "id": "hours",
            "title": "Hours of childcare used",
            "ours": f"About {a['mean_extended_hours_usage']:.0f} of the 30 extended hours a week",
            "source_says": "DfE January 2025 census implies about 28.5 hours",
            "source": _src("DfE funding technical note", DFE_FUNDING_URL),
            "modelled": "Each family's weekly extended hours come from the dataset's draw of "
                        f"{HOURS_USAGE_VARIABLE}, which averages about {a['mean_extended_hours_usage']:.0f} of the "
                        "30 hours. DfE's January 2025 census implies about 28.5; the draw is under review upstream "
                        "(PolicyEngine/microcosm#1126). policyengine-uk switches off a 3- or 4-year-old's universal 15 "
                        "hours once the family is eligible for the extended hours (PolicyEngine/policyengine-uk#1930); "
                        "we keep them, as the law does, and count only the hours above them as extended "
                        "(corrections.py), so a family that becomes eligible never loses funded hours.",
            "sources": [
                _src(HOURS_USAGE_VARIABLE,
                     f"{PEUK}/dfe/extended_childcare_entitlement/{HOURS_USAGE_VARIABLE}.py"),
                _src("Microcosm take-up contract", f"{MICROCOSM_UK}/take_up_contract.json"),
                _src("microcosm#1126", "https://github.com/PolicyEngine/microcosm/issues/1126"),
                _src("policyengine-uk#1930", "https://github.com/PolicyEngine/policyengine-uk/issues/1930"),
                _src("DfE funding technical note", DFE_FUNDING_URL),
            ],
            "alternative": "Every family uses all 30 extended hours",
            "effect_bn": effects["full_30_hour_usage"],
        },
        {
            "id": "under_ones",
            "title": "Babies under one",
            "ours": "No funded hours below age 1",
            "source_says": "Eligible from the term after the child turns 9 months",
            "source": _src("GOV.UK: childcare if you work", "https://www.gov.uk/free-childcare-if-working"),
            "modelled": "The model holds ages in whole years and gives age 0 no funded hours, so 9- to 11-month-olds "
                        "never qualify.",
            "sources": [_src("Under-1s adjustment (aggregate.py)", f"{THIS_REPO}/aggregate.py")],
            "alternative": "Add 9- to 11-month-olds outside the model, from the term after they turn 9 months, at the "
                           "under-2 funding rate",
            "effect_bn": effects["under_ones"],
        },
        {
            "id": "income_test",
            "title": "The income each limit tests",
            "ours": "Income before pension contributions; 59% of childcare spending through Tax-Free Childcare",
            "source_says": "The law deducts pension contributions (ITA 2007 s58)",
            "source": _src("Income Tax Act 2007 s58", "https://www.legislation.gov.uk/ukpga/2007/3/section/58"),
            "modelled": "Adjusted net income as policyengine-uk computes it: each parent's realised income for the "
                        "year, before pension contributions and Gift Aid are deducted. From 2029-30 we remove pension "
                        "salary sacrifice that the model adds back to pay under the new National Insurance cap, "
                        "because HMRC says the cap leaves adjusted net income unchanged (corrections.py). Tax-Free "
                        "Childcare is paid on the dataset's share of childcare spending that goes through an account "
                        "(59%).",
            "sources": [
                _src("Income Tax Act 2007 s58", "https://www.legislation.gov.uk/ukpga/2007/3/section/58"),
                _src("HMRC: salary sacrifice reform from April 2029", SALARY_SACRIFICE_URL),
                _src("Our correction (corrections.py)", f"{THIS_REPO}/corrections.py"),
                _src("Tax-Free Childcare share of spending (Microcosm)", f"{MICROCOSM_UK}/take_up_contract.json"),
            ],
            "alternative": "Deduct pension contributions before the £100,000 test, and put "
                           f"{ROUTED_SHARE_LOW:.0%} of childcare spending through Tax-Free Childcare accounts",
            "effect_bn": effects[agg.JOINT_LOW],
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
    limitations[-1:] = data_limitations(validation) + limitations[-1:]

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
            "range_bn": sens["range_bn"],
            "sensitivities": {
                "effects_bn": sens["effects_bn"],
                "low": [agg.JOINT_LOW],
                "high": ["full_30_hour_usage", "under_ones"],
                "descriptions": {
                    "full_30_hour_usage": "Every family uses all 30 extended hours (baseline and reform); "
                                          "the data draw a mean of about 15. Raises the cost.",
                    "under_ones": "Adds newly eligible 9-11-month-olds outside the model, allowing for funding "
                                  "starting in the term after a child turns 9 months, at 30 hours x 38 weeks x the "
                                  "under-2 funding rate and the model's take-up. Raises the cost.",
                    agg.JOINT_LOW: "Families whose parents are all at or below £100,000 once pension contributions "
                                   "are deducted already qualify in law, so their modelled gain is removed; for the "
                                   f"remaining families, only {ROUTED_SHARE_LOW:.0%} of childcare spending goes "
                                   "through a Tax-Free Childcare account. Counted jointly so no family's gain is "
                                   "reduced twice. Lowers the cost.",
                },
            },
        },
        "recipients": agg.recipients(runs),
        "distribution": agg.distribution(runs),
        "gender": agg.gender(runs),
        # The funded-hours spending rows only feed the limitation above: the gap to DfE is a
        # model/data issue filed upstream, stated once there rather than as a validation row.
        "baseline_validation": [r for r in validation if not r["label"].startswith(FUNDED_HOURS_SPENDING)],
        "assumptions": {"microcosm": assumptions},
        "cliff_example": cliff_example(grid),
        "household_grid": grid,
        "modelling_assumptions": modelling_assumptions(assumptions, sens["effects_bn"],
                                                       lsr["total_offset_bn"]["central"]),
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
                "margin. Tax-Free Childcare lowers the marginal price where the reform newly pays it and the cap "
                "does not bind (the model's own rate on the next pound of spend). The 30 funded hours are a fixed "
                "amount, conditional only on both parents meeting the minimum earnings test, so for a family that "
                "still buys paid care on top of them they do not change what an extra hour costs; they lower the "
                "marginal price (to zero) only where they are worth more than all the paid care the family buys. "
                "Income effect: the OBR income elasticities (Table A2, policyengine-uk's "
                "calculate_labour_net_income_elasticities, assigned to married and cohabiting couples alike) times "
                "the household's static gain as a percentage of its disposable income, as policyengine-uk's "
                "apply_progression_responses applies them except for the income measure. The gain is on the same "
                "disposable-income basis: the change in cash income (Tax-Free Childcare included) plus the paid "
                "childcare the newly funded hours displace (their value at the displacement rate below, capped at "
                "what the family pays), less the Tax-Free Childcare top-up on that displaced spend (recomputed by "
                "the model on the care the family still buys), not the funded hours at government cost. "
                "intensive_income_basis publishes the gain with spending held fixed (paid_care_fixed_spend: the "
                "top-up on displaced spend kept) and at government cost (government_cost). Neither elasticity is "
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
                    f"hours in {_fy(BENCHMARK_YEAR)}, £{thirty:.2f}bn, against CenTax's static £0.98bn. Our total "
                    f"for both schemes, £{budget['total'][y]:.2f}bn (range £{sens['range_bn']['low'][y]:.2f}bn to "
                    f"£{sens['range_bn']['high'][y]:.2f}bn), covers both schemes on the same static basis."
                ),
                "url": CONSERVATIVE_SOURCE_URL,
                "announcement_url": CONSERVATIVE_ANNOUNCEMENT_URL,
                "underlying_source": "CenTax, Removing the childcare cliff-edge: impacts and cost of reform (2026)",
                "underlying_source_url": CENTAX_REPORT_URL,
                "underlying_static_bn": 0.98,
                "underlying_net_bn": 0.64,
                "difference_from_underlying_static_bn": round(thirty - 0.98, 3),
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
