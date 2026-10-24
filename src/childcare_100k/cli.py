"""Build data/results.json: run (or reuse) every population job, then aggregate.

    childcare-100k-build            # run missing jobs, then write results
    childcare-100k-build --rerun    # rerun every job
    childcare-100k-build --aggregate-only
"""

import argparse
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone

from . import aggregate as agg
from . import expectation
from .config import (
    BASELINE_LIMIT,
    BENCHMARK_YEAR,
    BREWER_HOURS_URL,
    CENTAX_REPORT_URL,
    CONSERVATIVE_ANNOUNCEMENT_URL,
    CONSERVATIVE_SOURCE_URL,
    ELASTICITY_SCALES,
    EXTENDED_TAKE_UP_RATE,
    EXTENDED_TAKE_UP_SOURCE_URL,
    FREE_HOURS_DISPLACEMENT,
    FREE_HOURS_DISPLACEMENT_RANGE,
    HEADLINE_TAKE_UP_BASIS,
    HOURS_FOR_NEW_ENTRANTS,
    HOURS_PRICE_ELASTICITY,
    HOURS_USAGE_VARIABLE,
    LEAD_YEAR,
    MIN_CELL_RECORDS,
    OBR_PARTICIPATION_URL,
    OUTPUT,
    PRICE_ELASTICITY_CENTRAL,
    PRICE_ELASTICITY_HIGH,
    PRICE_ELASTICITY_LOW,
    PRIMARY_DATASET,
    REFORM_PARAMETERS,
    REPO,
    ROUTED_SHARE_LOW,
    SCENARIOS,
    TAKE_UP_BASES,
    TFC_TAKE_UP_NEWLY_ELIGIBLE_LOW,
    UPSTREAM_COUPLE_ISSUE_URL,
    YEARS,
)
from .datasets import MICROCOSM, POLICYENGINE_UK_VERSION
from .engine import JOBS, SOURCE_DIR, is_current, load_meta, run_isolated
from .household import cliff_example, household_grid
from .validation import DFE_FUNDING_URL, baseline_validation


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
    # The expected-mode pairs (expectation.py: claim-all and claim-and-use) run after the central baseline, which
    # their reforms do not need.
    for scenario in expectation.JOBS:
        if rerun or not expectation.is_current(scenario):
            expectation.run_isolated(scenario, REPO, log=log)
        metas[f"{PRIMARY_DATASET}/{scenario}"] = expectation.load_meta(scenario)
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
    "2.147.2, the version its manifest pins. It is the latest national release (latest-national.json has pointed "
    "at it since 23 October 2026). No policyengine.py bundle registers it yet (6.10.2's still registers 6cba5d71), "
    "so this repository pins the file by revision and sha256."
)

# CenTax, Removing the childcare cliff-edge, pp. 100-101: about 60% of parents below £100,000 held a live account
# in 2022, the take-up in their low-cost scenario.
CENTAX_LIVE_ACCOUNT_SHARE = 0.60
# Among children eligible today, the share the release has receiving the working-parent hours at some point in
# 2027-28 (annual, not January only, so a rough check against DfE's rates): review of #12, 24 October 2026.
RELEASE_TAKE_UP_CHECK_URL = (
    "https://github.com/PolicyEngine/uk-childcare-100k-threshold/pull/12#issuecomment-6385210332"
)
RELEASE_TAKE_UP_BY_AGE_PCT = {1: 75, 2: 82, 3: 90}
RELEASE_TAKE_UP_TEXT = (
    "The release itself sits close to DfE's rates: among children eligible today, about "
    f"{RELEASE_TAKE_UP_BY_AGE_PCT[1]}% at age 1, {RELEASE_TAKE_UP_BY_AGE_PCT[2]}% at 2 and "
    f"{RELEASE_TAKE_UP_BY_AGE_PCT[3]}% at 3 receive the hours at some point in 2027-28 (an annual measure, so a rough "
    "check), as a build calibrated to DfE's January 2025 registration counts should; on DfE's rates, baseline and "
    "reform therefore sit on the same take-up by age."
)

LIMITATIONS = [
    (
        "Expected, not realised, income",
        "Eligibility uses each parent's realised annual adjusted net income, while the law tests the income a parent "
        "expects when applying or reconfirming ([SI 2022/1134 reg 14(3)(c)(i)](https://www.legislation.gov.uk/uksi/2022/1134/regulation/14) and [15(3)(b)(i)](https://www.legislation.gov.uk/uksi/2022/1134/regulation/15); "
        "[SI 2015/448 reg 15(1)](https://www.legislation.gov.uk/uksi/2015/448/regulation/15)). "
        "A parent who expected to stay under £100,000 but ended the year above it can already receive support, and the "
        "model counts it as a reform cost; a parent who expected to exceed £100,000 but ended below it is modelled as "
        "eligible today. CenTax found that a third (33%) of parents whose year-end income was £100,000-£120,000 claimed "
        "and received some free childcare ([Removing the childcare cliff-edge](https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf#page=6), September 2026, pp. 5-6 and [59-60](https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf#page=60)). The "
        "net direction for the cost is not known, and it is not tested.",
    ),
    (
        "The release predates the age-date fix",
        "The release is cut from [Microcosm #1338](https://github.com/PolicyEngine/microcosm/pull/1338) at [829c1bc26](https://github.com/PolicyEngine/microcosm/commit/829c1bc26), before its last "
        "commit ([a12885f9](https://github.com/PolicyEngine/microcosm/commit/a12885f9)). So it keys the under-2 "
        "working-parent take-up draw on age at 6 October rather than DfE's age at 31 December (its age-0 rate mixes "
        "9-11-month-olds with children aged 12-14 months). On DfE's and CenTax's rates the headline sets both the claim "
        "and the usage of the hours for newly eligible children, so that draw does not feed it; it still feeds the "
        "contract basis, the single take-up draw and the breakdowns measured on it. The release's DfE rows bind the "
        "January 2025 census, a year before the spring term of 2025-26, which still bears on every basis through the "
        "eligible population. The next national release will be built on [PolicyEngine/microcosm#1347](https://github.com/PolicyEngine/microcosm/pull/1347), which carries the "
        "age-date fix (a12885f9) and [#1344](https://github.com/PolicyEngine/microcosm/pull/1344); the Microcosm team's preview build with the fix moved the 30 hours' cost on "
        "the dataset's own draw by about -£0.02bn, and these figures will be rerun on that release.",
    ),
    (
        "Tax-Free Childcare on the replaced care",
        "In the reform, each child's childcare spending is reduced by the value of its new funded hours at the funding "
        "rate before Tax-Free Childcare is computed. Fees are above funding rates, so this removes less spending than "
        "the hours replace and the Tax-Free Childcare leg may still be a little high. The hours response's income "
        "effect recomputes the family's cash income on the care it still buys, on its own displacement rule.",
    ),
    (
        "Partners who do not work",
        "A partner who does not work because of caring or incapacity qualifies through the benefits the data hold "
        "([policyengine-uk 2.147.2](https://github.com/PolicyEngine/policyengine-uk/tree/2.147.2) applies "
        "[SI 2022/1134 reg 14(4)](https://www.legislation.gov.uk/uksi/2022/1134/regulation/14)/[15(4)](https://www.legislation.gov.uk/uksi/2022/1134/regulation/15) and [SI 2015/448 reg 13](https://www.legislation.gov.uk/uksi/2015/448/regulation/13)), but not through limited "
        "capability for work, NI credits or carer's leave, which the data do not hold.",
    ),
    (
        "Take-up among newly eligible families",
        "Take-up of the 30 hours among newly eligible families is [DfE's January 2025 take-up](https://explore-education-statistics.service.gov.uk/find-statistics/funded-early-education-and-childcare/2025) among all eligible "
        "children, by age. Nothing measures it for families over £100,000, who are not eligible today: they may use "
        "formal childcare more than average, which would raise it, or claim less where the hours are worth little to "
        "them. DfE says its 2025 rates should be treated with caution and will be revised next year; its estimate of "
        "eligible 9-11-month-olds does not account for maternity or paternity leave; and its 2-year-olds under the "
        "working-parent entitlement include some who should have been recorded under the disadvantaged 2-year-old "
        "offer, which may put the 84% too high. The under-3 rates were measured on the 15-hour offer, before it rose "
        "to 30 hours in September 2025; take-up of 30 hours may differ. For the low end, CenTax's low-cost scenario "
        f"assumes {CENTAX_LIVE_ACCOUNT_SHARE:.0%} take-up, the share of parents below £100,000 who held a live childcare "
        "account in 2022 ([Removing the childcare cliff-edge, pp. 100-101](https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf#page=101)). CenTax's two rates and the dataset's flat "
        "rate are on [Budget impact](?tab=budget#take-up-options); the breakdowns by family, income and region, who gains by age, the range's adjustments "
        "and the labour supply offsets are measured on the dataset's single take-up draw.",
    ),
    (
        "Small cells suppressed",
        "Breakdown cells resting on fewer than ten gaining or changed records are suppressed, and where a single cell "
        "would be suppressed a second is suppressed with it (or the whole breakdown, if no second cell can protect it), "
        "so no suppressed cell can be recovered from the published UK totals.",
    ),
]


def limitation(title, text):
    """A limitation as a short title, its first sentence (the summary) and the rest (the detail, possibly empty)."""
    parts = re.split(r"(?<=[a-z0-9)%])\. (?=[A-Z])", text, maxsplit=1)
    return {"title": title, "summary": parts[0] + ("." if len(parts) > 1 else ""),
            "detail": parts[1] if len(parts) > 1 else ""}


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
    return [(
        "Funded hours: baseline context",
        f"The baseline's free-hours spending in 2026-27 is {versus} DfE's "
        "illustrative total (see [Baseline validation](#validation)). DfE's totals are illustrative (based partly on forecasts) and "
        "are context only: matching the aggregate baseline does not bound the incremental cost for newly eligible "
        "families above £100,000, whose take-up and hours may differ.",
    )]


def concentration_limitation(concentration, year):
    """How much of the static cost rests on the few largest-gaining weighted records."""
    c = concentration[str(year)]
    return ("Concentration on a few families", f"In {_fy(year)} the ten largest gaining families (by weight times gain, on the single take-up draw) carry "
            f"{c['top_ten_share_pct']:.0f}% of the static cost and the largest alone {c['largest_share_pct']:.0f}%. "
            "The sampling uncertainty this leaves is on the [Budget impact tab](?tab=budget#uncertainty).")


SALARY_SACRIFICE_URL = (
    "https://www.gov.uk/government/publications/salary-sacrifice-reform-for-pension-contributions-effective-from-"
    "6-april-2029/salary-sacrifice-reform-for-pension-contributions"
)
PEUK = "https://github.com/PolicyEngine/policyengine-uk/blob/2.147.2/policyengine_uk/variables/gov"
MICROCOSM_UK = "https://github.com/PolicyEngine/microcosm/blob/829c1bc26/packages/microcosm-build/src/microcosm/build/uk"
THIS_REPO = "https://github.com/PolicyEngine/uk-childcare-100k-threshold/blob/main/src/childcare_100k"


def _src(label, url):
    return {"label": label, "url": url}


LSR_ALTERNATIVE = ("Parents respond: partners move into work (OBR participation elasticities), and parents in work "
                   "change their hours as the price of an extra hour of childcare falls and as their family's "
                   "income rises (a childcare-price and an OBR income elasticity)")


def _rates_text(spec):
    """A child-level basis's rates in words: "42% at 9-11 months, 70% at 1, 84% at 2 and 91% at 3 and 4"."""
    r = spec["rates_by_dfe_age"]
    if r[0] == r[1] == r[2]:
        return f"{r[0]:.0%} under 3 and {r[3]:.0%} at 3 and 4"
    return f"{r[0]:.0%} at 9-11 months, {r[1]:.0%} at 1, {r[2]:.0%} at 2 and {r[3]:.0%} at 3 and 4"


def _basis_effect(bases, basis):
    """The change in the static total (£bn by year) from the headline take-up basis to ``basis``."""
    head = bases[HEADLINE_TAKE_UP_BASIS]["total"]
    return {y: round(bases[basis]["total"][y] - head[y], 3) for y in head}


def _contract_gap_text(gap):
    """Why DfE's rates give a lower cost than the contract's flat rate, as the split of the gap by DfE age."""
    m = gap["gap_m"]
    eff = gap["contract_effective_rate"]["0"]

    def signed(v):
        return f"{'+' if v >= 0 else '-'}£{abs(v)}m"

    return (f"Against DfE's rates, the contract's flat rate ({EXTENDED_TAKE_UP_RATE:.1%} of families) is above them at "
            f"9-11 months, where the dataset's usage draw makes it about {eff:.0%} in effect, and at age 1, about "
            f"level at 2 and below them at 3 and 4. So in {_fy(gap['year'])} its 30-hours cost is £{gap['gap_total_m']}m "
            f"higher: {signed(m['0'])} at age 0, {signed(m['1'])} at 1, {signed(m['2'])} at 2 and {signed(m['3-5'])} "
            "at 3 to 5 (DfE age).")


def modelling_assumptions(a, effects, labour_supply_offset, tfc, bases, gap):
    """The choices behind every figure, each as the code makes it, with the tested alternative's effect where there is one."""
    etfc = a["would_claim_tfc_pct"]
    return [
        {
            "id": "static",
            "title": "No change in work, pay or childcare",
            "ours": "No change in work, pay or pension contributions",
            "source_says": "CenTax allow for parents earning more and partners entering work (see the comparison on Methodology)",
            "source": _src("CenTax, Table 4.2", f"{CENTAX_REPORT_URL}#page=42"),
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
            "title": "Who takes up the 30 hours",
            "ours": f"DfE's take-up by age: {_rates_text(TAKE_UP_BASES['dfe'])}",
            "source_says": "DfE's January 2025 take-up of the working-parent hours, by age; CenTax use "
                           f"{_rates_text(TAKE_UP_BASES['centax'])}",
            "source": _src(TAKE_UP_BASES["dfe"]["source"], TAKE_UP_BASES["dfe"]["source_url"]),
            "modelled": "Nobody over £100,000 is eligible today, so the data cannot say how many newly eligible "
                        "families would take up the 30 hours. The dataset draws once whether each family would "
                        f"claim, at the take-up contract's flat rate ({EXTENDED_TAKE_UP_RATE:.1%}), and a few heavily "
                        "weighted families decide much of the cost on that draw. The headline instead averages over "
                        "take-up child by child: a pair of runs has every family claiming and every child using its "
                        "hours, and each newly entitled child's cost there is multiplied by DfE's take-up for its age "
                        "(registered over eligible children in January 2025; the rates are in the comparison table). "
                        f"{TAKE_UP_AGE_NOTE} "
                        "These rates already count whether a family applies and whether the child uses the hours, so "
                        "they replace the dataset's claim and under-2 usage draws rather than adding to them; the "
                        "hours a week a child who uses them takes are the dataset's draw. A child who takes up the new "
                        "hours gets no Tax-Free Childcare on the care they replace; one who does not keeps its top-up "
                        f"(each weighted by the take-up chance). {_contract_gap_text(gap)} {RELEASE_TAKE_UP_TEXT} "
                        "[Budget impact](?tab=budget#take-up-options) switches between DfE's rates, CenTax's two rates and the "
                        "flat rate.",
            "sources": [
                _src(TAKE_UP_BASES["dfe"]["source"], TAKE_UP_BASES["dfe"]["source_url"]),
                _src(TAKE_UP_BASES["centax"]["source"], TAKE_UP_BASES["centax"]["source_url"]),
                _src("The 30-hours rate in the release's take-up contract", EXTENDED_TAKE_UP_SOURCE_URL),
                _src("would_claim_extended_childcare",
                     f"{PEUK}/dfe/extended_childcare_entitlement/would_claim_extended_childcare.py"),
                _src("Expected mode (expectation.py)", f"{THIS_REPO}/expectation.py"),
                _src("How we apply the rates (aggregate.py)", f"{THIS_REPO}/aggregate.py"),
                _src("Expected-mode costing (#7)", "https://github.com/PolicyEngine/uk-childcare-100k-threshold/issues/7"),
                _src("The release's take-up by age (review of #12)", RELEASE_TAKE_UP_CHECK_URL),
            ],
            "alternative": f"CenTax's two rates: {_rates_text(TAKE_UP_BASES['centax'])}",
            "effect_bn": _basis_effect(bases, "centax"),
        },
        {
            "id": "take_up_contract",
            "title": "One take-up rate for every family",
            "ours": "Take-up by the child's age, child by child",
            "source_says": "The dataset's take-up contract has one rate for the working-parent hours",
            "source": _src("Microcosm take-up contract", EXTENDED_TAKE_UP_SOURCE_URL),
            "modelled": "The alternative is the expected mode before the take-up bases: the cost averaged over the "
                        f"dataset's draw at the contract's flat rate, {EXTENDED_TAKE_UP_RATE:.1%} of families, with "
                        "the dataset's draws of the hours used. A family that takes up the new hours gets no "
                        "Tax-Free Childcare on the care they replace; one that does not keeps its top-up (each "
                        "weighted by the rate). Each percentage point of that rate moves the 30 hours' cost by the "
                        "amount in [How we cost it](#take-up-method).",
            "sources": [
                _src("Microcosm take-up contract", EXTENDED_TAKE_UP_SOURCE_URL),
                _src("Expected mode (expectation.py)", f"{THIS_REPO}/expectation.py"),
            ],
            "alternative": f"The take-up contract's flat rate: {EXTENDED_TAKE_UP_RATE:.1%} of families, with the "
                           "dataset's under-2 usage draw",
            "effect_bn": _basis_effect(bases, "contract"),
        },
        {
            "id": "tfc_take_up",
            "title": "Who claims Tax-Free Childcare",
            "ours": f"{int(etfc['families_with_child_under_12'] + 0.5)}% of families carry a Tax-Free Childcare claim "
                    "flag, but only those reporting paid registered childcare get a top-up",
            "source_says": "Dataset draws, calibrated in Microcosm's take-up contract",
            "source": _src("Microcosm take-up contract", f"{MICROCOSM_UK}/take_up_contract.json"),
            "modelled": "The Tax-Free Childcare draw is a claim flag fitted to HMRC's top-up and account counts, not a "
                        "take-up rate: a family gets a top-up only on the paid registered childcare it reports, so use "
                        "is limited by reported spending (the table shows both). Nothing identifies take-up among "
                        "families over £100,000, who are not eligible today, so the alternative sets it to 70% of newly "
                        "eligible families, about today's use among all eligible families. The alternative's effect "
                        "and the leg before netting are measured on the dataset's single take-up draw of the 30 hours, "
                        "not on DfE's rates.",
            "sources": [
                _src("Microcosm take-up contract", f"{MICROCOSM_UK}/take_up_contract.json"),
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
# María Juaristi's comment of 23 October 2026 on #8: her bootstrap over FRS source households on a133f37a (which
# aggregate.bootstrap reproduces), the expected-mode costing, the age-profile sensitivity and the next release.
UNCERTAINTY_SOURCE_URL = "https://github.com/PolicyEngine/uk-childcare-100k-threshold/pull/8#issuecomment-6370235552"
# The 30 hours' change in 2027-28 with the newly entitled 1-to-4-year-olds on CenTax's gradient between under-3s and
# 3-to-4s (her figure; aggregate.age_profile_sensitivity computes the even spread).
CENTAX_GRADIENT_SENSITIVITY_BN = 0.13
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


def take_up_block(bases, recipients, expected, net_total, range_bn):
    """``budget.take_up``: each take-up basis's definition and source, gross and net costs, range and recipients.

    Totals by year only: no breakdown by age, region or family is published on these bases.
    """
    out = {"headline": HEADLINE_TAKE_UP_BASIS, "order": list(TAKE_UP_BASES), "age": TAKE_UP_AGE_NOTE, "bases": {}}
    for basis, spec in TAKE_UP_BASES.items():
        costs = bases[basis]
        block = {
            "label": spec["label"],
            "short_label": spec["short_label"],
            "description": spec["description"],
            "unit": spec["unit"],
            "source": spec["source"],
            "source_url": spec["source_url"],
            "gross_bn": {k: costs[k] for k in ("thirty_hours", "tax_free_childcare", "total")},
            "net_bn": {"total": net_total(costs["total"])},
            "range_bn": range_bn(costs["total"]),
            "recipients": recipients(expected, basis),
        }
        if spec["unit"] == "family":
            block["rate"] = spec["rate"]
            block["per_point_m"] = costs["thirty_hours_per_point_m"]
        else:
            block["rates_by_dfe_age"] = {str(a): r for a, r in spec["rates_by_dfe_age"].items()}
            block["rates_text"] = _rates_text(spec)
        out["bases"][basis] = block
    return out


TAKE_UP_AGE_NOTE = (
    "A child-level rate applies by the child's DfE age: its age on 31 December of the year (the year less its birth "
    "year), the age DfE's January census counts it by. DfE age 0 is the 9-11-month-olds funded from the spring term; "
    "a child born September to December who is funded for the summer term before it starts reception (aged 4 then) "
    "has DfE age 5 and takes the 3-and-4 rate. Each child takes up the hours independently of its siblings."
)


def build(metas):
    runs = agg.load(SCENARIOS)
    expected = agg.load_expected()
    # The single take-up draw (the central pair as the dataset draws it) and the expected cost on each take-up basis
    # (#7; config.TAKE_UP_BASES): DfE's rates by age, the headline; CenTax's two rates; the contract's flat rate.
    drawn = agg.budget_block(runs)
    bases = agg.basis_costs(runs, expected)
    head = bases[HEADLINE_TAKE_UP_BASIS]
    budget = {k: head[k] for k in ("thirty_hours", "tax_free_childcare", "total")}
    sens = agg.sensitivities(runs)

    # Nothing but the 30 hours and Tax-Free Childcare depends on the limits, so the net change differs from the gross
    # by the same amount on every basis.
    def net_total(total):
        return {k: round(total[k] + drawn["net_total"][k] - drawn["total"][k], 3) for k in total}

    # The range is a basis's total plus each sensitivity's effect (measured on the drawn pairs), to the last digit.
    def range_bn(total):
        return {
            "low": {k: round(v + sens["effects_bn"][agg.ROUTED_LOW][k], 3) for k, v in total.items()},
            "central": dict(total),
            "high": {k: round(v + sens["effects_bn"]["full_30_hour_usage"][k], 3) for k, v in total.items()},
        }

    budget["net_total"] = net_total(budget["total"])
    sens["range_bn"] = range_bn(budget["total"])
    take_up = take_up_block(bases, agg.basis_recipients, expected, net_total, range_bn)
    gap = agg.contract_gap_by_dfe_age(expected)
    take_up["contract_gap_by_dfe_age"] = gap
    uncertainty = agg.bootstrap(runs, expected)
    age_profile = agg.age_profile_sensitivity(runs)
    validation = baseline_validation(runs)
    assumptions = agg.assumptions(runs)
    limitations = list(LIMITATIONS)
    concentration = agg.concentration(runs)
    limitations[-1:] = (data_limitations(validation) + [concentration_limitation(concentration, LEAD_YEAR)]
                        + limitations[-1:])
    tfc = agg.tax_free_childcare_leg(runs)
    tfc["central"] = dict(budget["tax_free_childcare"])

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
            # The same costs on the dataset's single take-up draw; the breakdowns by family, income and region,
            # the sensitivities and the labour supply response are measured on it.
            "single_draw_bn": {k: drawn[k] for k in ("thirty_hours", "tax_free_childcare", "total")},
            # Who takes up the 30 hours among newly eligible children: each basis's costs, range and recipients
            # (totals by year only). gross_bn above is the headline basis's.
            "take_up": take_up,
            "uncertainty": {
                **uncertainty,
                "method": "Bootstrap over FRS source households: each draw resamples them with replacement, each "
                          "with all its Microcosm copies, the release weights fixed. Calibration is held fixed and "
                          "the FRS's clustering is ignored, so it is a floor on the sampling uncertainty.",
                "reproduces_url": UNCERTAINTY_SOURCE_URL,
            },
            "age_profile_sensitivity": {
                **age_profile,
                "centax_gradient_bn": CENTAX_GRADIENT_SENSITIVITY_BN,
                "source_url": UNCERTAINTY_SOURCE_URL,
            },
            "thirty_hours_components_bn": agg.basis_components(runs, expected, HEADLINE_TAKE_UP_BASIS),
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
                                                       lsr["total_offset_bn"]["central"], tfc, bases, gap),
        "labour_supply": {
            **lsr,
            "assumptions": {
                "participation_elasticities": "[OBR Table A1](https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf#page=8), by sex, partner's work, age of youngest child and "
                                              "earnings quintile, converted to the gain to work and applied to the "
                                              "employed share ([Adam and Phillips, Appendix E]"
                                              "(https://ifs.org.uk/sites/default/files/output_url_files/r75.pdf#page=132))",
                "price_elasticity_central": PRICE_ELASTICITY_CENTRAL,
                "price_elasticity_low": PRICE_ELASTICITY_LOW,
                "price_elasticity_high": PRICE_ELASTICITY_HIGH,
                "elasticity_scales": {k: round(v, 4) for k, v in ELASTICITY_SCALES.items()},
                "hours_price_elasticity": HOURS_PRICE_ELASTICITY,
                "income_elasticities": "[Table A2](https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf#page=9), by sex, whether in a couple and age of youngest child: from "
                                       "-0.185 (a woman in a couple, youngest child 0-2) to -0.037 (a lone "
                                       "mother, youngest 0-4); -0.05 for a man in a couple",
                "couples": "The OBR groups ([Tables A1 and A2](https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf#page=8)) apply to married and cohabiting couples alike. "
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
                "whom the OBR excludes from participation ([Table A4](https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf#page=9)) but not from hours ([Table A3](https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf#page=9)); "
                "those in work "
                "may change their hours."
            ),
            "not_modelled": "Bunching: parents who today keep their income at or just below "
                            "£100,000 and would earn more without the limit.",
            "notes": [
                "The dynamic cost is an illustrative scenario, not a forecast: its hours price elasticity is "
                "extrapolated, the OBR elasticities are not measured on parents over £100,000, and its range is "
                "not a confidence interval. Offsets are £bn a year; positive is money back to the Exchequer. The "
                "dynamic cost is the static total less the two offsets (moving into work and hours), at the same "
                "bound; the static total is the headline, on DfE's take-up by age, and the offsets are measured on "
                "the dataset's single take-up draw; the hours offset is its price effect (money back) plus its income "
                "effect (money out). On another take-up basis the dashboard subtracts the same offsets. "
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
                "underlying_source_url": f"{CENTAX_REPORT_URL}#page=42",
                "underlying_static_bn": CENTAX_STATIC_BN[BENCHMARK_YEAR],
                "underlying_static_by_year_bn": {str(k): v for k, v in CENTAX_STATIC_BN.items()},
                "underlying_static_before_bunching_by_year_bn": {
                    str(k): v for k, v in CENTAX_STATIC_BEFORE_BUNCHING_BN.items()},
                "underlying_net_bn": 0.64,
                "difference_from_underlying_static_bn": round(thirty - CENTAX_STATIC_BN[BENCHMARK_YEAR], 3),
            }
        ],
        "limitations": [limitation(title, text) for title, text in limitations],
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
        metas.update({f"{PRIMARY_DATASET}/{s}": expectation.load_meta(s) for s in expectation.JOBS})
    else:
        metas = run_all(rerun=a.rerun)
    results = build(metas)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUTPUT} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
