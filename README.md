# Removing the £100,000 childcare income limit

PolicyEngine UK analysis of the Conservative proposal (October 2026) to remove the £100,000 adjusted-net-income limit on:
- the **30 funded hours** for working parents of children aged 9 months to 4 years (England);
- **Tax-Free Childcare** (UK-wide).

The universal 15 hours for 3- and 4-year-olds is unaffected.

## Data and model

- **Data:** Microcosm UK 2024-25, the national release cut on 23 October 2026 (`microcosm-uk-2024-25-national-20261023T075039Z-a133f37a`, from PolicyEngine/microcosm#1338 at 829c1bc26), pinned by this repository at commit `c3a751d9` with sha256 `64f83900…` and verified before every run. It is the only dataset. The release has its own signed certification; no policyengine.py bundle registers it yet, so the population runs pass the verified file to `managed_microsimulation()` with `allow_unmanaged=True`.
- **Model:** policyengine-uk 2.147.2 (with policyengine-core 3.33.3), the version the release manifest pins, pinned in `pyproject.toml`, run through policyengine.py 6.10.0 (whose own bundle carries 2.132.6, so it is installed without its `[uk]` extra).
- **Weighting:** microdf throughout; no weights are applied by hand.
- **No fallbacks:** a missing token, a sha256 mismatch, a stale cached run or a missing provenance field stops the build.

## Results

Static gross cost, £bn a year (positive = extra government spending), led by 2027-28, the first full year a change could apply. 2026-27 is shown as illustrative: it is half over. The central figures average over who claims the 30 hours (expected mode, below).

| | 2026-27 | 2027-28 | 2028-29 | 2029-30 |
|---|---|---|---|---|
| **Total** | 1.00 | 1.07 | 1.13 | 1.23 |
| 30 funded hours | 0.87 | 0.93 | 0.98 | 1.07 |
| Tax-Free Childcare | 0.14 | 0.14 | 0.15 | 0.16 |
| Range (low to high) | 1.00-1.06 | 1.07-1.13 | 1.13-1.19 | 1.22-1.29 |
| 30 hours: bootstrap SD (5th-95th percentile) | | 0.14 (0.70-1.18) | | 0.15 (0.83-1.33) |
| Total: bootstrap SD (5th-95th percentile) | | 0.16 (0.82-1.35) | | 0.17 (0.96-1.53) |
| 30 hours on the dataset's single take-up draw | 0.92 | 0.98 | 1.04 | 1.12 |
| Tax-Free Childcare if 70% of newly eligible families claim | 0.09 | 0.10 | 0.11 | 0.11 |

- **One line.** policyengine-uk 2.147.2 now does what the earlier CenTax-basis toggles did: it takes adjusted net income after pension contributions, values hours at DfE's funding rates, ends funded hours when a child starts reception and starts them in the term after a child turns 9 months, from the date of birth. So there is no separate line on CenTax's basis.
- **Tax-Free Childcare on the new hours.** In the reform each child's childcare spending is reduced by the value of its new funded hours before Tax-Free Childcare is worked out, so the top-up is not paid on care the hours replace (£0.19bn and £0.21bn in 2027-28 and 2029-30 before this). The 70% line sets take-up among newly eligible families with paid registered childcare to 70%, about today's use among all eligible families; it is not in the range.
- **Expected mode.** The dataset draws once whether each family would claim the 30 hours, at the take-up contract's rate of 83.6%. The few heavily weighted newly eligible families drew a claim more often than that (88% weighted, against 83% unweighted), so the single draw is about £0.05bn above the expectation. The central figure is each newly eligible family's cost if it claims, times the rate ([#7](https://github.com/PolicyEngine/uk-childcare-100k-threshold/issues/7); `src/childcare_100k/expectation.py`). Each percentage point of the rate moves the 30 hours by about £11m in 2027-28 and £13m in 2029-30. The breakdowns, the range's adjustments and the labour supply offsets are measured on the single draw.
- **Sampling uncertainty.** A bootstrap over FRS source households (each with all its Microcosm copies, weights fixed, 2,000 draws) gives the SDs above. It holds the calibration fixed and ignores the FRS's clustering, so it is a floor. The 30-hours cost rests on about 170 FRS households in 2027-28, an effective number of about 40. CenTax's £0.80bn and £0.98bn lie inside the ranges. On the single draw it reproduces the [Microcosm team's bootstrap](https://github.com/PolicyEngine/uk-childcare-100k-threshold/pull/8#issuecomment-6370235552) (SD £0.16bn and £0.17bn).
- **Age profile, one-sided.** The release has few 1-year-olds in families over £100,000 (5%, against 9-13% at the other ages under 5), and no source independent of the FRS crosses income with child age. Spreading the newly entitled 1-to-4-year-olds evenly across ages raises the 2027-28 30-hours cost by about £0.16bn; on CenTax's gradient between under-3s and 3-to-4s, by about £0.13bn (the Microcosm team's figure).
- **Next release.** The next national release will be built on PolicyEngine/microcosm#1347, with the age-date fix (a12885f9) and #1344. On the Microcosm team's preview build the 30 hours move by about -£0.02bn; the figures will be rerun on it.
- **Who gains, 2027-28:** 251,000 families (337,000 children), on average £4,482 a year; 144,000 through the 30 hours and 170,000 through Tax-Free Childcare (families can gain from both). No family loses.
- **One local correction to policyengine-uk 2.147.2** (`src/childcare_100k/corrections.py`, every run and the household calculator): Tax-Free Childcare's final income test applies to the claimant and partner rather than to members flagged as parents. The other corrections and toggles are now upstream and were removed ([docs/METHOD.md](docs/METHOD.md#model-corrections)).
- **If parents change how much they work** (OBR participation elasticities applied to the employed share; for parents in work, an assumed childcare-price elasticity of hours of −0.042, extrapolated from Brewer et al., applied to the change in the price of an extra hour of paid childcare, and the OBR income elasticities, for married and cohabiting couples alike, applied to the family's gain in cash and in paid childcare the funded hours replace), the cost falls to **£0.92bn in 2027-28 and £1.06bn in 2029-30** in an illustrative scenario (2029-30: £0.90bn-£1.17bn, an illustrative range, not a confidence interval). In 2029-30 about 2,200 partners moving into work add £0.016bn, because their families then receive the support, and parents' hours bring back a net £0.179bn. Bunching at the limit is not modelled. See [docs/METHOD.md](docs/METHOD.md#behaviour).
- **The net cost equals the gross cost** (to within £1m of rounding): no other tax or benefit in the model depends on these limits.
- **Realised, not expected, income.** The model tests each parent's realised annual adjusted net income; the law tests the income a parent expects when applying. CenTax find that a third of parents who ended the year on £100,000-£120,000 still received some free childcare, which the model would count as a reform cost; parents who expected to exceed £100,000 but ended below it pull the other way. The net direction is unknown and is not in the range.
- **Against CenTax and the £0.7bn.** The Conservatives put the plan's cost at about £700m a year (PA, BBC); City AM says it is based on CenTax's September 2026 report, with a small addition for Tax-Free Childcare. CenTax ([Table 4.2](https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf)) covers the free childcare hours only: a static £800m in 2028 and £980m in 2030 (tax years 2027-28 and 2029-30; £860m and £1,070m before their deduction for parents bunching under £100,000), or £520m and £640m net of extra tax. Our 30-hours leg is **£0.93bn and £1.07bn**, 16% and 9% above their figures after the bunching deduction (8% above and level with them before it), well within the bootstrap ranges. See [docs/METHOD.md](docs/METHOD.md#the-07bn-benchmark).

### The range

| Adjustment | Direction | Why |
|---|---|---|
| Every family uses all 30 extended hours | + | The data draw slightly fewer (about 28 on average) |
| Route 58% of childcare spending through TFC accounts | − | The data route 59.3% |

In 2029-30 full 30-hour usage adds £0.07bn and the routing adjustment removes under £0.01bn. See [docs/METHOD.md](docs/METHOD.md) for every model-versus-law difference and [data/results.json](data/results.json) for the full output ([schema](docs/RESULTS_SCHEMA.md)).

### Baseline validation

Microcosm against HMRC (people with income of £100,000 or more; Tax-Free Childcare top-ups, families and children), DfE (working-parent entitlement caseloads; free-entitlements funding) and the model's funding rates against DfE's:

| | Year | Microcosm | Official |
|---|---|---|---|
| People with income of £100,000 or more | 2025-26 | 1.894m | 1.950m (HMRC) |
| People with income of £100,000 or more | 2026-27 | 2.030m | 2.063m (HMRC) |
| Tax-Free Childcare government top-up | 2025-26 | £0.601bn | £0.600bn (HMRC) |
| Families with a used TFC account | 2025-26 | 888k | 868k (HMRC) |
| Children with a used TFC account | 2025-26 | 1,154k | 1,152k (HMRC) |
| Under-3s on the working-parent entitlement, spring term | 2025-26 | 482k | 467k (DfE, January 2025, incl. 29k aged 9-11 months) |
| 3- and 4-year-olds on it, spring term | 2025-26 | 380k | 379k (DfE, January 2025) |
| Free-entitlements spending, central | 2025-26 | £7.16bn | £8.2bn (DfE) |
| Free-entitlements spending, central | 2026-27 | £10.27bn | £9.9bn (DfE) |
| Same, every family using 30 extended hours | 2026-27 | £10.67bn | £9.9bn (DfE) |

DfE's totals are the sums of the illustrative totals by age in its early years national funding formulae technical notes ([2026-27](https://www.gov.uk/government/publications/early-years-funding-2026-to-2027/2026-to-2027-early-years-national-funding-formulae-technical-note), section 3.3: £4.2bn for 3- and 4-year-olds, £2.7bn for 2-year-olds, £3.0bn for under-2s; [2025-26](https://www.gov.uk/government/publications/early-years-funding-2025-to-2026/2025-to-2026-early-years-national-funding-formulae-technical-note), section 3.2: £3.8bn, £2.1bn and £2.3bn); neither note states a combined figure, and both call their totals illustrative. The working-parent counts are children funded in the January term by their age on 31 December, as the release's calibration rows count them, against the January 2025 census those rows bind (the model's 2025-26 spring term is January 2026, when DfE counted 501,700 under 3 and 388,700 aged 3 and 4). By age, the under-3s are 29k, 196k and 258k against DfE's 29k, 195k and 242k: 2-year-olds are 6% above. Funded-hours spending is 4% above DfE's illustrative total in 2026-27 and 13% below it in 2025-26, almost all in the under-3s (£3.2bn against DfE's £4.4bn), whose hours rose from 15 to 30 a week in September 2025. Matching the aggregate baseline would not bound the incremental cost for newly eligible families above £100,000 in any case: it is context, not a bound.

## Reproduce

Python 3.13 or 3.14 and [uv](https://docs.astral.sh/uv/); `.python-version` selects 3.14, because some locked dependencies (h5py among them) publish no wheels for 3.15 yet. The release is in a private Hugging Face repository; set `HF_TOKEN` (or `HUGGING_FACE_TOKEN`) with read access to `policyengine/populace-uk-private`, or, if the pinned revision is already in your Hugging Face cache, set `HF_HUB_OFFLINE=1` instead and no token is used. The sha256 check applies either way.

```bash
uv sync --frozen --extra dev
export HF_TOKEN=...                # or: export HF_HUB_OFFLINE=1
.venv/bin/childcare-100k-build     # downloads and verifies the release, runs the population jobs, writes data/results.json
.venv/bin/pytest
```

`--aggregate-only` rebuilds the results file from cached runs, and refuses any cached run whose provenance (dataset sha256, policyengine.py and policyengine-uk versions, code hash) does not match.
