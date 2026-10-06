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
    ROUTED_SHARE_LOW,
    SCENARIOS,
    YEARS,
)
from .datasets import MICROCOSM
from .engine import is_current, load_meta, run_isolated
from .household import cliff_example
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
    "them outside the model, allowing for funding starting in the term after a child turns 9 months.",
    "Four-year-olds in reception still receive funded hours in the model (compulsory school age starts at 5), so the "
    "baseline counts more funded 3- and 4-year-olds than DfE.",
    "Adjusted net income in policyengine-uk does not deduct pension contributions or Gift Aid (Income Tax Act 2007 "
    "s58), so too many parents sit above £100,000 in the baseline and the reform cost is overstated; the low end "
    "removes families who would already qualify on a net-of-pension-contributions measure.",
    "From 2029-30, policyengine-uk adds pension salary sacrifice above the new £2,000 National Insurance cap back "
    "into pay, which raises adjusted net income. HMRC says the cap changes National Insurance only and leaves "
    "adjusted net income, and so the childcare limits, unchanged. Both childcare income tests here therefore use "
    "adjusted net income less the returned salary sacrifice in every run, baseline and reform. Income tax and "
    "National Insurance are left as the model computes them. This correction is pending an upstream fix in "
    "policyengine-uk.",
    "Tax-Free Childcare uses the Microcosm release's share of each person's childcare spending paid through an "
    f"account (0.593 for every record); the low end sets it to {ROUTED_SHARE_LOW}, counted jointly with the pension "
    "adjustment so the two are not double-counted.",
    "Childcare spending is held fixed: a family that gains funded hours would in practice pay for fewer hours, which "
    "would cut its Tax-Free Childcare top-up; the combined cost is overstated slightly.",
    "Funded hours are valued at the model's hourly funding rates (2024-25 rates uprated by CPI), 1-6% below DfE's "
    "2026-27 national average rates (see baseline_validation), so the 30-hours leg is slightly understated.",
    "The high end adds the full-usage and under-1s adjustments; their interaction is ignored.",
    "Breakdown cells resting on fewer than ten gaining or changed records are suppressed, and where a single cell "
    "would be suppressed a second is suppressed with it (or the whole breakdown, if no second cell can protect it), "
    "so no suppressed cell can be recovered from the published UK totals.",
    "Policy assumed in force for the whole of each fiscal year from 2026-27; the proposal's start date is not given, "
    "and 2026-27 is already half over, so its figures are illustrative.",
]


def _validation_value(rows, label, year):
    """A model figure from the baseline validation rows. Raises if the row is missing."""
    matches = [r for r in rows if r["label"] == label and r["year"] == year]
    if len(matches) != 1:
        raise KeyError(f"baseline_validation has {len(matches)} rows for {label!r} in {year}")
    return matches[0]


def data_limitations(rows):
    """Limitations stated with this dataset's own validation figures."""
    free = _validation_value(rows, "Free early years entitlements spending (all three entitlements)", 2026)
    free30 = _validation_value(
        rows, "Free early years entitlements spending if every family used all 30 extended hours", 2026)
    high = _validation_value(rows, "People with income of £100,000 or more", 2025)
    return [
        f"The central figure likely sits low on funded hours: the central baseline spends £{free['model']:.1f}bn on "
        f"free hours in 2026-27 against DfE's £{free['official']:.1f}bn, while full 30-hour use gives "
        f"£{free30['model']:.1f}bn. DfE's total is illustrative (based partly on forecasts) and is context only: "
        "bracketing the aggregate baseline does not bound the incremental cost for newly eligible families above "
        "£100,000, whose take-up and hours may differ.",
        f"Microcosm holds {high['model'] / 1e6:.2f} million people with income of £100,000 or more in 2025-26 "
        f"against HMRC's projected {high['official'] / 1e6:.2f} million (see baseline_validation).",
    ]


def take_up_limitation(a):
    """The take-up caveat, stated with the draw rates the results report."""
    e30, etfc = a["would_claim_30_hours_pct"], a["would_claim_tfc_pct"]
    return (
        "Take-up holds the dataset's existing take-up draws fixed; it is not modelled afresh for newly eligible "
        "families. The draw rates differ by income: families with a child under 5 would claim the 30 hours at "
        f"{e30['families_with_child_under_5']}% ({e30['of_which_parent_over_100k']}% where a parent is over "
        f"£100,000); families with a child under 12 would claim Tax-Free Childcare at "
        f"{etfc['families_with_child_under_12']}% ({etfc['of_which_parent_over_100k']}%) "
        f"({a['year']}-{(a['year'] + 1) % 100:02d}, see assumptions)."
    )


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
    limitations.insert(1, take_up_limitation(assumptions))
    limitations[-1:-1] = data_limitations(validation)

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
                "The Conservative proposal (3-4 October 2026) to remove the £100,000 adjusted-net-income limit, "
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
            "variants": {
                "thirty_hours_only": agg.variant_totals(runs, "thirty_hours_only"),
                "tfc_only": agg.variant_totals(runs, "tfc_only"),
            },
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
        "baseline_validation": validation,
        "assumptions": {"microcosm": assumptions},
        "cliff_example": cliff_example(),
        "benchmarks": [
            {
                "source": "Conservative Party",
                "figure": "£0.7bn a year",
                "ours": thirty,
                "ours_label": f"Static gross cost of the 30 funded hours in {_fy(BENCHMARK_YEAR)}",
                "year": BENCHMARK_YEAR,
                "like_for_like": (
                    "City AM reports the cost as 'about £700m per year' and says the costing 'is based on a recent "
                    "report by the Centre for the Analysis of Taxation'; the party's announcement gives no figure, "
                    "year or method. CenTax (Removing the childcare cliff-edge: impacts and cost of reform, September "
                    "2026, Table 4.2) estimates a static cost of £980m in 2030 for removing the £100,000 threshold "
                    "on the free childcare hours only, and a net cost of £640m after £340m of extra revenue: £210m "
                    "of tax from parents who no longer keep their income below £100,000 and £130m of tax and "
                    "National Insurance from partners who enter work. It does not cover Tax-Free Childcare. The like-for-like "
                    f"comparison is our static cost of the 30 funded hours in {_fy(BENCHMARK_YEAR)}, "
                    f"£{thirty:.2f}bn, against CenTax's static £0.98bn. Our total for both schemes is "
                    f"£{budget['total'][y]:.2f}bn (range £{sens['range_bn']['low'][y]:.2f}bn to "
                    f"£{sens['range_bn']['high'][y]:.2f}bn), with no behavioural response."
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
