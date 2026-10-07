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
from .engine import is_current, load_meta, run_isolated
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
    for scenario in SCENARIOS:
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
    "Four-year-olds in reception still receive funded hours in the model (compulsory school age starts at 5), so the "
    "baseline counts more funded 3- and 4-year-olds than DfE.",
    "Childcare spending is held fixed: a family that gains funded hours would in practice pay for fewer hours, which "
    "would cut its Tax-Free Childcare top-up; the combined cost is overstated slightly.",
    "Funded hours are valued at the model's hourly funding rates (2024-25 rates uprated by CPI), 1-6% below DfE's "
    "2026-27 national average rates (see baseline_validation), so the 30-hours leg is slightly understated.",
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
        "£100,000, whose take-up and hours may differ.",
        f"Microcosm holds {high['model'] / 1e6:.2f} million people with income of £100,000 or more in 2025-26 "
        f"against HMRC's projected {high['official'] / 1e6:.2f} million (see baseline_validation).",
    ]


def modelling_assumptions(a, effects):
    """The choices behind every figure, each as the code makes it, with the tested alternative's effect where there is one."""
    e30, etfc = a["would_claim_30_hours_pct"], a["would_claim_tfc_pct"]
    return [
        {
            "id": "static",
            "title": "No change in work, pay or childcare",
            "modelled": "Both runs use the same households with the same earnings, hours of work and childcare "
                        "spending. Nobody works more or less, or changes their pension contributions, because the "
                        "limit goes.",
        },
        {
            "id": "take_up",
            "title": "Who claims",
            "modelled": "Each family's decision to claim comes from the dataset's existing take-up draws "
                        "(would_claim_extended_childcare, would_claim_tfc), held fixed for newly eligible families. "
                        f"In {a['year']}-{(a['year'] + 1) % 100:02d}, {e30['families_with_child_under_5']}% of families "
                        f"with a child under 5 would claim the 30 hours ({e30['of_which_parent_over_100k']}% where a "
                        f"parent is over £100,000), and {etfc['families_with_child_under_12']}% of families with a "
                        f"child under 12 would claim Tax-Free Childcare ({etfc['of_which_parent_over_100k']}%).",
        },
        {
            "id": "hours",
            "title": "Hours of childcare used",
            "modelled": "Each family's weekly extended hours come from the dataset's draw of "
                        f"{HOURS_USAGE_VARIABLE}, which averages about {a['mean_extended_hours_usage']:.0f} of the "
                        "30 hours. DfE's January 2025 census implies about 28.5; the draw is under review upstream "
                        "(PolicyEngine/microcosm#1126). The model also switches off a 3- or 4-year-old's universal 15 "
                        "hours once the family is eligible for the extended hours (PolicyEngine/policyengine-uk#1930).",
            "alternative": "Every family uses all 30 extended hours, today and under the reform.",
            "effect_bn": effects["full_30_hour_usage"],
        },
        {
            "id": "under_ones",
            "title": "Babies under one",
            "modelled": "The model holds ages in whole years and gives age 0 no funded hours, so 9- to 11-month-olds "
                        "never qualify.",
            "alternative": "Add newly eligible 9- to 11-month-olds outside the model, from the term after they turn "
                           "9 months, at 30 hours x 38 weeks x the under-2 funding rate and the model's take-up.",
            "effect_bn": effects["under_ones"],
        },
        {
            "id": "income_test",
            "title": "The income each limit tests",
            "modelled": "Adjusted net income as policyengine-uk computes it: each parent's realised income for the "
                        "year, before pension contributions and Gift Aid are deducted. From 2029-30 we remove pension "
                        "salary sacrifice that the model adds back to pay under the new National Insurance cap, "
                        "because HMRC says the cap leaves adjusted net income unchanged (corrections.py). Tax-Free "
                        "Childcare is paid on the dataset's share of childcare spending that goes through an account "
                        "(59%).",
            "alternative": "Deduct pension contributions before testing the £100,000 limit, and put "
                           f"{ROUTED_SHARE_LOW:.0%} of childcare spending through Tax-Free Childcare accounts, counted "
                           "together so no family's gain is cut twice.",
            "effect_bn": effects[agg.JOINT_LOW],
        },
        {
            "id": "timing",
            "title": "In force for the whole year",
            "modelled": "The limit is removed for the whole of each fiscal year from 2026-27 to 2029-30. The pledge "
                        "gives no start date and 2026-27 is already half over, so 2026-27 is illustrative.",
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
        # The funded-hours spending rows only feed the limitation above: the gap to DfE is a
        # model/data issue filed upstream, stated once there rather than as a validation row.
        "baseline_validation": [r for r in validation if not r["label"].startswith(FUNDED_HOURS_SPENDING)],
        "assumptions": {"microcosm": assumptions},
        "cliff_example": cliff_example(grid),
        "household_grid": grid,
        "modelling_assumptions": modelling_assumptions(assumptions, sens["effects_bn"]),
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
        metas = {f"{PRIMARY_DATASET}/{s}": load_meta(s) for s in SCENARIOS}
    else:
        metas = run_all(rerun=a.rerun)
    results = build(metas)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUTPUT} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
