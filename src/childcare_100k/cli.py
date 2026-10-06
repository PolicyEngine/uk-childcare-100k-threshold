"""Build data/results.json: run (or reuse) every population job, then aggregate.

    childcare-100k-build            # run missing jobs, then write results
    childcare-100k-build --rerun    # rerun every job
    childcare-100k-build --aggregate-only
"""

import argparse
import importlib.metadata
import json
import subprocess
import time
from datetime import datetime, timezone

from . import aggregate as agg
from .config import (
    BASELINE_LIMIT,
    CENTAX_REPORT_URL,
    CONSERVATIVE_ANNOUNCEMENT_URL,
    CONSERVATIVE_COST_BN,
    CONSERVATIVE_SOURCE_URL,
    CROSS_CHECK_DATASET,
    HEADLINE_YEAR,
    MIN_CELL_RECORDS,
    OUTPUT,
    PRIMARY_DATASET,
    REFORM_PARAMETERS,
    REPO,
    ROUTED_SHARE_LOW,
    SCENARIOS,
    YEARS,
)
from .engine import meta_path, run_isolated, run_path
from .household import cliff_example
from .validation import baseline_validation


def _git_revision():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


def run_all(rerun=False, log=print):
    metas = {}
    for dataset in (PRIMARY_DATASET, CROSS_CHECK_DATASET):  # one process at a time
        for scenario in SCENARIOS:
            if rerun or not run_path(dataset, scenario).exists() or not meta_path(dataset, scenario).exists():
                run_isolated(dataset, scenario, REPO, log=log)
            metas[f"{dataset}/{scenario}"] = json.loads(meta_path(dataset, scenario).read_text())
    return metas


LIMITATIONS = [
    "Static costing: no labour-supply or earnings response. Parents just above £100,000 who would work more, and "
    "parents now holding income below £100,000 through pension contributions or reduced hours, are not modelled; the "
    "Conservatives' claimed growth effects are not scored.",
    "Eligibility uses each parent's realised annual adjusted net income, while the law tests the income a parent "
    "expects when applying or reconfirming (SI 2022/1134 reg 14(3)(c)(i) and 15(3)(b)(i); SI 2015/448 reg 15(1)). "
    "A parent who expected to stay under £100,000 but ended the year above it can already receive support, and the "
    "model counts it as a reform cost; a parent who expected to exceed £100,000 but ended below it is modelled as "
    "eligible today. CenTax found that a third (33%) of parents whose year-end income was £100,000-£120,000 claimed "
    "and received some free childcare (Removing the childcare cliff-edge, September 2026, pp. 5-6 and 59-60). The "
    "net direction for the cost is not known, and the range does not include it.",
    "Funded hours use the dataset's draw of weekly extended hours used (mean about 15 of 30). The model also switches "
    "off the universal 15 hours when a family becomes eligible for the extended hours, so a newly eligible 3- or "
    "4-year-old with a low draw gains little or loses hours in the model (families_losing). The high end of the range "
    "sets usage to the full 30 hours.",
    "Children aged 9-11 months never qualify in the model (whole-year ages, age 0 gets no hours); the high end adds "
    "them outside the model.",
    "Adjusted net income in policyengine-uk does not deduct pension contributions or Gift Aid (Income Tax Act 2007 "
    "s58), so too many parents sit above £100,000 in the baseline and the reform cost is overstated; the low end "
    "removes families who would already qualify on a net-of-pension-contributions measure.",
    "Tax-Free Childcare assumes all of a family's childcare spending goes through the account (routed share 1, the "
    f"model default; the bundled datasets predate the routed-share calibration). The low end uses {ROUTED_SHARE_LOW}.",
    "Childcare spending is held fixed: a family that gains funded hours would in practice pay for fewer hours, which "
    "would cut its Tax-Free Childcare top-up; the combined cost is overstated slightly.",
    "Funded hours are valued at the model's hourly funding rates (2024-25 rates uprated by CPI), close to but not "
    "equal to DfE's 2026-27 national average rates (see baseline_validation).",
    "The central figure likely sits low on funded hours: the central baseline spends about £7.0bn on free hours "
    "in 2026-27 against DfE's £9.9bn, while full 30-hour use gives about £11.7bn, so the truth lies between the "
    "central and high ends on that leg.",
    "The low and high ends add the separate adjustments; interactions between them are ignored.",
    "Distributional and recipient figures come from the Enhanced FRS; Microcosm is a cross-check of the budget totals "
    "only. Breakdown cells resting on fewer than ten gaining or changed records are suppressed, and where a "
    "single cell would be suppressed a second is suppressed with it, so neither can be recovered from the published "
    "UK totals (by country this suppresses Wales and Northern Ireland together).",
    "Microcosm holds about 2.9 million people with income of £100,000 or more in 2025-26 against HMRC's projected "
    "2.0 million (the Enhanced FRS holds 1.7 million), so it likely overstates the pool of families the reform "
    "reaches; this is why the Enhanced FRS is the headline and the main reason the Microcosm cross-check is well above it. Microcosm "
    "also holds fewer households in Scotland, Wales and Northern Ireland than official estimates, so the "
    "by-country split understates the devolved nations (where only Tax-Free Childcare changes).",
    "Policy assumed in force for the whole of each fiscal year from 2026-27; the proposal's start date is not given.",
]


def take_up_limitation(a_p, a_x):
    """The take-up caveat, stated with the draw rates the results report."""
    e30, x30 = a_p["would_claim_30_hours_pct"], a_x["would_claim_30_hours_pct"]
    etfc, xtfc = a_p["would_claim_tfc_pct"], a_x["would_claim_tfc_pct"]
    return (
        "Take-up holds each dataset's existing take-up draws fixed; it is not modelled afresh for newly eligible "
        "families. The draw rates differ by income: families with a child under 5 would claim the 30 hours at "
        f"{e30['families_with_child_under_5']}% on the Enhanced FRS ({e30['of_which_parent_over_100k']}% where a "
        f"parent is over £100,000) and {x30['families_with_child_under_5']}% on Microcosm "
        f"({x30['of_which_parent_over_100k']}%); families with a child under 12 would claim Tax-Free Childcare at "
        f"{etfc['families_with_child_under_12']}% ({etfc['of_which_parent_over_100k']}%) and "
        f"{xtfc['families_with_child_under_12']}% ({xtfc['of_which_parent_over_100k']}%) respectively "
        f"({a_p['year']}-{(a_p['year'] + 1) % 100:02d}, see assumptions)."
    )


def build(metas):
    p = agg.load(PRIMARY_DATASET, SCENARIOS)
    x = agg.load(CROSS_CHECK_DATASET, SCENARIOS)
    budget_p = agg.budget_block(p)
    budget_x = agg.budget_block(x)
    sens_p = agg.sensitivities(p)
    sens_x = agg.sensitivities(x)
    # The central figure is the published gross total, to the last rounded digit.
    sens_p["range_bn"]["central"] = dict(budget_p["total"])
    sens_x["range_bn"]["central"] = dict(budget_x["total"])
    bundle = metas[f"{PRIMARY_DATASET}/baseline"]["bundle"]
    bundle_x = metas[f"{CROSS_CHECK_DATASET}/baseline"]["bundle"]

    head = budget_p["total"][str(HEADLINE_YEAR)]
    assumptions_p, assumptions_x = agg.assumptions(p), agg.assumptions(x)
    limitations = list(LIMITATIONS)
    limitations.insert(1, take_up_limitation(assumptions_p, assumptions_x))
    results = {
        "meta": {
            "policyengine": importlib.metadata.version("policyengine"),
            "policyengine_uk": importlib.metadata.version("policyengine-uk"),
            "dataset": PRIMARY_DATASET,
            "dataset_revision": bundle.get("runtime_dataset_revision", ""),
            "dataset_sha256": bundle.get("runtime_dataset_sha256", ""),
            "cross_check_dataset": CROSS_CHECK_DATASET,
            "cross_check_dataset_revision": bundle_x.get("runtime_dataset_revision", ""),
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
                "The Conservative proposal (3-4 October 2026) to remove the £100,000 adjusted-net-income limit, "
                "tested on each parent, for the 30 funded hours for working parents in England (children aged 9 "
                "months to 4 years) and for Tax-Free Childcare (UK-wide: £2 top-up for every £8 paid in, up to "
                "£2,000 a child a year, £4,000 if disabled). The universal 15 hours for 3- and 4-year-olds is "
                "unaffected. Static microsimulation, 2026-27 to 2029-30."
            ),
            "parameters": [{"name": n, "baseline": BASELINE_LIMIT, "reform": "removed"} for n in REFORM_PARAMETERS],
        },
        "budget": {
            "gross_bn": {k: budget_p[k] for k in ("thirty_hours", "tax_free_childcare", "total")},
            "net_bn": {"total": budget_p["net_total"]},
            "thirty_hours_components_bn": agg.thirty_hours_components(p),
            "variants": {
                "thirty_hours_only": agg.variant_totals(p, "thirty_hours_only"),
                "tfc_only": agg.variant_totals(p, "tfc_only"),
            },
            "cross_check": {
                "total": budget_x["total"],
                "thirty_hours": budget_x["thirty_hours"],
                "tax_free_childcare": budget_x["tax_free_childcare"],
                "net_total": budget_x["net_total"],
                "thirty_hours_components_bn": agg.thirty_hours_components(x),
                "variants": {
                    "thirty_hours_only": agg.variant_totals(x, "thirty_hours_only"),
                    "tfc_only": agg.variant_totals(x, "tfc_only"),
                },
                "range_bn": sens_x["range_bn"],
                "effects_bn": sens_x["effects_bn"],
            },
            "range_bn": sens_p["range_bn"],
            "sensitivities": {
                "effects_bn": sens_p["effects_bn"],
                "low": ["ani_net_of_pension_contributions", "tfc_routed_share"],
                "high": ["full_30_hour_usage", "under_ones"],
                "descriptions": {
                    "full_30_hour_usage": "Every family uses all 30 extended hours (baseline and reform); "
                                          "the data draw a mean of about 15. Raises the cost.",
                    "under_ones": "Adds newly eligible 9-11-month-olds outside the model: a quarter of age-0 "
                                  "children in newly eligible families x 30 hours x 38 weeks x the under-2 funding "
                                  "rate, at the model's take-up. Raises the cost.",
                    "ani_net_of_pension_contributions": "Families whose parents are all at or below £100,000 once "
                                                        "pension contributions are deducted already qualify in law; "
                                                        "their modelled gain is removed. Lowers the cost.",
                    "tfc_routed_share": f"Only {ROUTED_SHARE_LOW:.0%} of childcare spending goes through a Tax-Free "
                                        "Childcare account (baseline and reform). Lowers the cost.",
                },
            },
        },
        "recipients": agg.recipients(p),
        "recipients_cross_check": {
            y: {k: v[k] for k in ("families_gaining", "children_gaining", "by_scheme", "mean_gain_gbp")}
            for y, v in agg.recipients(x).items()
        },
        "distribution": agg.distribution(p),
        "baseline_validation": baseline_validation(PRIMARY_DATASET, p, CROSS_CHECK_DATASET, x),
        "assumptions": {"enhanced_frs": assumptions_p, "microcosm": assumptions_x},
        "cliff_example": cliff_example(),
        "benchmarks": [
            {
                "source": "Conservative Party",
                "figure": "£0.7bn a year",
                "ours": head,
                "year": HEADLINE_YEAR,
                "like_for_like": (
                    "Not like for like. City AM reports the cost as 'about £700m per year' and says the costing 'is "
                    "based on a recent report by the Centre for the Analysis of Taxation'; the party's announcement "
                    "gives no figure, year or method. CenTax (Removing the childcare cliff-edge: impacts and cost of "
                    "reform, September 2026, Table 4.2) estimates a net fiscal cost of £640m in 2030 for removing the "
                    "£100,000 threshold on the free childcare hours only: a static cost of £980m less £340m of tax "
                    "from parents who stop holding their income below £100,000. It does not cover Tax-Free "
                    "Childcare. Ours is the static gross cost of both schemes in "
                    f"{HEADLINE_YEAR}-{(HEADLINE_YEAR + 1) % 100:02d} on the Enhanced FRS (range "
                    f"£{sens_p['range_bn']['low'][str(HEADLINE_YEAR)]:.2f}bn to "
                    f"£{sens_p['range_bn']['high'][str(HEADLINE_YEAR)]:.2f}bn), with no behavioural response; its 30 "
                    f"hours leg is £{budget_p['thirty_hours'][str(HEADLINE_YEAR)]:.2f}bn, against CenTax's static "
                    "£0.98bn. The Microcosm cross-check is higher "
                    f"(£{budget_x['total'][str(HEADLINE_YEAR)]:.2f}bn) because it holds about 47% more people on "
                    "£100,000 or more than HMRC projects."
                ),
                "url": CONSERVATIVE_SOURCE_URL,
                "announcement_url": CONSERVATIVE_ANNOUNCEMENT_URL,
                "underlying_source": "CenTax, Removing the childcare cliff-edge: impacts and cost of reform (2026)",
                "underlying_source_url": CENTAX_REPORT_URL,
                "difference_bn": round(head - CONSERVATIVE_COST_BN, 3),
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
        metas = {f"{d}/{s}": json.loads(meta_path(d, s).read_text())
                 for d in (PRIMARY_DATASET, CROSS_CHECK_DATASET) for s in SCENARIOS}
    else:
        metas = run_all(rerun=a.rerun)
    results = build(metas)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUTPUT} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
