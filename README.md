# Removing the £100,000 childcare income limit

PolicyEngine UK analysis of the Conservative proposal (October 2026) to remove the £100,000 adjusted-net-income limit on:
- the **30 funded hours** for working parents of children aged 9 months to 4 years (England);
- **Tax-Free Childcare** (UK-wide).

The universal 15 hours for 3- and 4-year-olds is unaffected.

## Data and model

- **Data:** Microcosm UK 2024-25, the national release cut on 19 October 2026 (`microcosm-uk-2024-25-national-20261019T083323Z-6cba5d71`), pinned by this repository at commit `bb225848` with sha256 `810ba980…` and verified before every run. It is the only dataset. **It is not a certified release:** it is the first national release with [PolicyEngine/microcosm#1126](https://github.com/PolicyEngine/microcosm/issues/1126), which draws each family's weekly extended hours to DfE's 28.5-hour mean (earlier releases drew about 15), and the latest certified release (14 October 2026) predates that fix. Results on main should move to a certified release that contains #1126 once one exists.
- **Model:** policyengine.py 6.2.1 (policyengine-uk 2.102.3) runs every simulation. The release was built with policyengine-uk 2.132.6; policyengine.py 6.2.1's bundle does not register it, so the population runs pass the verified file to `managed_microsimulation()` with `allow_unmanaged=True`.
- **Weighting:** microdf throughout; no weights are applied by hand.
- **No fallbacks:** a missing token, a sha256 mismatch, a stale cached run or a missing provenance field stops the build.

## Results

Static gross cost, £bn a year (positive = extra government spending), led by 2027-28, the first full year a change could apply. 2026-27 is shown as illustrative: it is half over.

| | 2026-27 | 2027-28 | 2028-29 | 2029-30 |
|---|---|---|---|---|
| **Total** | 1.16 | 1.23 | 1.30 | 1.46 |
| 30 funded hours | 0.95 | 1.01 | 1.06 | 1.22 |
| Tax-Free Childcare | 0.21 | 0.22 | 0.23 | 0.25 |
| Range (low to high) | 1.10-1.24 | 1.18-1.31 | 1.25-1.38 | 1.30-1.56 |

- **Who gains, 2027-28:** 282,000 families (391,000 children), on average £4,358 a year; 120,000 through the 30 hours and 250,000 through Tax-Free Childcare (families can gain from both). No family loses.
- **Five local corrections to policyengine-uk 2.102.3** (`src/childcare_100k/corrections.py`, every run and the household calculator): exactly £100,000 qualifies for the 30 hours; a partner on carer's allowance, ESA or another specified benefit need not pass the minimum earnings test (SI 2022/1134 reg 14(4)/15(4)); the universal and targeted 15 hours are kept when a family qualifies for the extended hours; from 2029-30 the income tests ignore pension salary sacrifice that the model adds back to pay under the new £2,000 National Insurance cap; and Tax-Free Childcare regards a partner on a caring or incapacity benefit as in work (SI 2015/448 reg 13). Their effects on the cost were measured on the 2 October 2026 release and are in [docs/METHOD.md](docs/METHOD.md#model-corrections); they have not been re-measured on this one.
- **If parents change how much they work** (OBR participation elasticities applied to the employed share; for parents in work, an assumed childcare-price elasticity of hours of −0.042, extrapolated from Brewer et al., applied to the change in the price of an extra hour of paid childcare, and the OBR income elasticities, for married and cohabiting couples alike, applied to the family's gain in cash and in paid childcare the funded hours replace, net of the Tax-Free Childcare and Universal Credit childcare element on that care), the cost falls to **£1.03bn in 2027-28 and £1.26bn in 2029-30** in an illustrative scenario (2029-30: £1.04bn-£1.40bn, an illustrative range, not a confidence interval). In 2029-30 about 2,400 partners moving into work add £0.017bn, because their families then receive the support, and parents' hours bring back a net £0.225bn: £0.278bn from the lower price of an extra hour of childcare (net of all childcare-linked support, in practice Tax-Free Childcare's top-up; the funded hours are a fixed amount and change that price only where they are worth more than all the paid care a family buys) less £0.053bn as better-off families work slightly less. Bunching at the limit is not modelled. See [docs/METHOD.md](docs/METHOD.md#behaviour).
- **The net cost equals the gross cost** (to within £1m of rounding): no other tax or benefit in the model depends on these limits.
- **Realised, not expected, income.** The model tests each parent's realised annual adjusted net income; the law tests the income a parent expects when applying. CenTax find that a third of parents who ended the year on £100,000-£120,000 still received some free childcare, which the model would count as a reform cost; parents who expected to exceed £100,000 but ended below it pull the other way. The net direction is unknown and is not in the range.
- **A few records carry much of the cost.** About 2,000 gaining survey records make up the static cost; the ten largest carry about a third of it, so single heavily weighted records move it in steps (the 2029-30 low end is one).
- **Against CenTax and the £0.7bn.** The Conservatives put the plan's cost at about £700m a year (PA, BBC); City AM says it is based on CenTax's September 2026 report, with a small addition for Tax-Free Childcare. CenTax ([Table 4.2](https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf)) covers the free childcare hours only: a static £800m in 2028 and £980m in 2030 (tax years 2027-28 and 2029-30), or £520m and £640m net of extra tax (in 2030, £210m from parents who no longer keep their income below £100,000 and £130m of tax and National Insurance from partners who enter work). The like-for-like comparison is our **30-hours leg against CenTax's static figures: about 25% above them** in both years. Our dynamic cost is about twice CenTax's net, because it has no counterpart to their £210m from parents no longer keeping their income below £100,000 and our partners moving into work cost money rather than bring it back. See [docs/METHOD.md](docs/METHOD.md#the-07bn-benchmark).

### The range

| Adjustment | Direction | Why |
|---|---|---|
| Every family uses all 30 extended hours | + | The data draw slightly fewer (about 28 on average) |
| Add 9-11-month-olds, from the term after they turn 9 months | + | The model's whole-year ages give age 0 no hours |
| Deduct pension contributions from adjusted net income, and route 58% of childcare spending through TFC accounts (one joint run) | − | The model's measure leaves pension contributions in, unlike the law, and the data route 59.3% |

In 2029-30 full 30-hour usage adds £0.05bn, the under-1s £0.04bn, and the joint pension and routing adjustment removes £0.16bn (£0.05bn-£0.06bn in earlier years; about half of the 2029-30 step is one heavily weighted family that first gains from the reform that year but is under £100,000 once pension contributions are deducted). Since microcosm#1126, full usage no longer dominates the high end. See [docs/METHOD.md](docs/METHOD.md) for every model-versus-law difference and [data/results.json](data/results.json) for the full output ([schema](docs/RESULTS_SCHEMA.md)).

### Baseline validation

Microcosm against HMRC (people with income of £100,000 or more; Tax-Free Childcare top-ups, families and children), DfE (working-parent entitlement caseloads; free-entitlements funding) and the model's funding rates against DfE's:

| | Year | Microcosm | Official |
|---|---|---|---|
| People with income of £100,000 or more | 2025-26 | 1.896m | 1.950m (HMRC) |
| People with income of £100,000 or more | 2026-27 | 2.018m | 2.063m (HMRC) |
| Tax-Free Childcare government top-up | 2025-26 | £0.600bn | £0.600bn (HMRC) |
| Families with a used TFC account | 2025-26 | 888k | 868k (HMRC) |
| Children with a used TFC account | 2025-26 | 1,150k | 1,152k (HMRC) |
| Under-3s using the working-parent entitlement | 2025-26 | 366k | 502k (DfE) |
| 3- and 4-year-olds using it (hours beyond the universal 15) | 2025-26 | 397k | 389k (DfE) |
| Free-entitlements spending, central | 2025-26 | £6.63bn | £8.2bn (DfE) |
| Same, every family using 30 extended hours | 2025-26 | £6.79bn | £8.2bn (DfE) |
| Free-entitlements spending, central | 2026-27 | £8.80bn | £9.9bn (DfE) |
| Same, every family using 30 extended hours | 2026-27 | £9.23bn | £9.9bn (DfE) |

DfE's totals are the sums of the illustrative totals by age in its early years national funding formulae technical notes ([2026-27](https://www.gov.uk/government/publications/early-years-funding-2026-to-2027/2026-to-2027-early-years-national-funding-formulae-technical-note), section 3.3: £4.2bn for 3- and 4-year-olds, £2.7bn for 2-year-olds, £3.0bn for under-2s; [2025-26](https://www.gov.uk/government/publications/early-years-funding-2025-to-2026/2025-to-2026-early-years-national-funding-formulae-technical-note), section 3.2: £3.8bn, £2.1bn and £2.3bn); neither note states a combined figure, and both call their totals illustrative. The release still matches HMRC's high-earner count and Tax-Free Childcare closely. Funded-hours spending is much closer to DfE than on the 2 October release (£6.06bn in 2026-27) but still about 11% below in 2026-27 and 19% below in 2025-26; with hours now drawn near DfE's mean, full 30-hour usage closes little of it. The remaining gap is mainly the model's lower funding rates, the missing 9-11-month-olds and fewer under-3s on the working-parent entitlement (fewer than on the 2 October release). Bracketing the aggregate baseline would not bound the incremental cost for newly eligible families above £100,000 in any case: it is context, not a bound.

## Reproduce

Python 3.13 and [uv](https://docs.astral.sh/uv/). The release is in a private Hugging Face repository; set `HF_TOKEN` (or `HUGGING_FACE_TOKEN`) with read access to `policyengine/populace-uk-private`, or, if the pinned revision is already in your Hugging Face cache, set `HF_HUB_OFFLINE=1` instead and no token is used. The sha256 check applies either way.

```bash
uv sync --frozen --extra dev
export HF_TOKEN=...                # or: export HF_HUB_OFFLINE=1
.venv/bin/childcare-100k-build     # downloads and verifies the release, runs the population jobs, writes data/results.json
.venv/bin/pytest
```

`--aggregate-only` rebuilds the results file from cached runs, and refuses any cached run whose provenance (dataset sha256, policyengine.py and policyengine-uk versions, code hash) does not match.
