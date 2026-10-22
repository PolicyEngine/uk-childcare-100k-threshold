# Removing the £100,000 childcare income limit

PolicyEngine UK analysis of the Conservative proposal (October 2026) to remove the £100,000 adjusted-net-income limit on:
- the **30 funded hours** for working parents of children aged 9 months to 4 years (England);
- **Tax-Free Childcare** (UK-wide).

The universal 15 hours for 3- and 4-year-olds is unaffected.

## Data and model

- **Data:** Microcosm UK 2024-25, the national release cut on 21 October 2026 (`microcosm-uk-2024-25-national-20261021T195620Z-a858c100`, PolicyEngine/microcosm#1338), pinned by this repository at commit `415b034b` with sha256 `e1f027b9…` and verified before every run. It is the only dataset. The release has its own signed certification; no policyengine.py bundle registers it yet, so the population runs pass the verified file to `managed_microsimulation()` with `allow_unmanaged=True`.
- **Model:** policyengine-uk 2.134.4, the version the release manifest pins, pinned in `pyproject.toml`, run through policyengine.py 6.10.0 (whose own bundle carries 2.132.6, so it is installed without its `[uk]` extra).
- **Weighting:** microdf throughout; no weights are applied by hand.
- **No fallbacks:** a missing token, a sha256 mismatch, a stale cached run or a missing provenance field stops the build.

## Results

Static gross cost, £bn a year (positive = extra government spending), led by 2027-28, the first full year a change could apply. 2026-27 is shown as illustrative: it is half over.

| | 2026-27 | 2027-28 | 2028-29 | 2029-30 |
|---|---|---|---|---|
| **Total** | 1.09 | 1.17 | 1.22 | 1.36 |
| 30 funded hours | 0.90 | 0.96 | 1.01 | 1.12 |
| Tax-Free Childcare | 0.20 | 0.21 | 0.22 | 0.24 |
| Range (low to high) | 1.05-1.18 | 1.10-1.26 | 1.17-1.31 | 1.21-1.47 |
| 30 funded hours on CenTax's basis | 0.83 | 0.87 | 0.93 | 0.96 |

- **Sampling noise.** A bootstrap over FRS source households by the Microcosm team gives a standard deviation of about £0.13bn in 2027-28 and £0.18bn in 2029-30 on the 30-hours leg ([#8](https://github.com/PolicyEngine/uk-childcare-100k-threshold/pull/8#issuecomment-6327525773)). The static cost rests on about 2,000 gaining survey records, with a Kish effective sample size of about 175; the ten largest carry 27% of it.
- **CenTax's basis** removes funded hours from 4-year-olds in reception, values hours at DfE's published funding rates, tests adjusted net income after pension contributions and adds 9-11-month-olds (`budget.centax_basis_bn`). The first three are toggles in `src/childcare_100k/corrections.py`; the under-1s are added outside the model.
- **Who gains, 2027-28:** 271,000 families (360,000 children), on average £4,323 a year; 136,000 through the 30 hours and 226,000 through Tax-Free Childcare (families can gain from both). No family loses.
- **Two local corrections to policyengine-uk 2.134.4** (`src/childcare_100k/corrections.py`, every run and the household calculator): from 2029-30 the income tests ignore pension salary sacrifice that the model adds back to pay under the new £2,000 National Insurance cap, and Tax-Free Childcare's final income test applies to the claimant and partner rather than to members flagged as parents. Five earlier corrections are now handled upstream and were removed ([docs/METHOD.md](docs/METHOD.md#model-corrections)).
- **If parents change how much they work** (OBR participation elasticities applied to the employed share; for parents in work, an assumed childcare-price elasticity of hours of −0.042, extrapolated from Brewer et al., applied to the change in the price of an extra hour of paid childcare, and the OBR income elasticities, for married and cohabiting couples alike, applied to the family's gain in cash and in paid childcare the funded hours replace), the cost falls to **£1.04bn in 2027-28 and £1.22bn in 2029-30** in an illustrative scenario (2029-30: £1.07bn-£1.31bn, an illustrative range, not a confidence interval). In 2029-30 about 2,300 partners moving into work add £0.019bn, because their families then receive the support, and parents' hours bring back a net £0.163bn. Bunching at the limit is not modelled. See [docs/METHOD.md](docs/METHOD.md#behaviour).
- **The net cost equals the gross cost** (to within £1m of rounding): no other tax or benefit in the model depends on these limits.
- **Realised, not expected, income.** The model tests each parent's realised annual adjusted net income; the law tests the income a parent expects when applying. CenTax find that a third of parents who ended the year on £100,000-£120,000 still received some free childcare, which the model would count as a reform cost; parents who expected to exceed £100,000 but ended below it pull the other way. The net direction is unknown and is not in the range.
- **Against CenTax and the £0.7bn.** The Conservatives put the plan's cost at about £700m a year (PA, BBC); City AM says it is based on CenTax's September 2026 report, with a small addition for Tax-Free Childcare. CenTax ([Table 4.2](https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf)) covers the free childcare hours only: a static £800m in 2028 and £980m in 2030 (tax years 2027-28 and 2029-30; £860m and £1,070m before their deduction for parents bunching under £100,000), or £520m and £640m net of extra tax. Our 30-hours leg is £0.96bn and £1.12bn as shipped, and **£0.87bn and £0.96bn on CenTax's basis**, within one bootstrap standard deviation of their figures. See [docs/METHOD.md](docs/METHOD.md#the-07bn-benchmark).

### The range

| Adjustment | Direction | Why |
|---|---|---|
| Every family uses all 30 extended hours | + | The data draw slightly fewer (about 28 on average) |
| Add 9-11-month-olds, from the term after they turn 9 months | + | The model's whole-year ages give age 0 no hours |
| Deduct pension contributions from adjusted net income, and route 58% of childcare spending through TFC accounts (one joint run) | − | The model's measure leaves pension contributions in, unlike the law, and the data route 59.3% |

In 2029-30 full 30-hour usage adds £0.08bn, the under-1s £0.03bn, and the joint pension and routing adjustment removes £0.15bn (£0.04bn-£0.07bn in earlier years). See [docs/METHOD.md](docs/METHOD.md) for every model-versus-law difference and [data/results.json](data/results.json) for the full output ([schema](docs/RESULTS_SCHEMA.md)).

### Baseline validation

Microcosm against HMRC (people with income of £100,000 or more; Tax-Free Childcare top-ups, families and children), DfE (working-parent entitlement caseloads; free-entitlements funding) and the model's funding rates against DfE's:

| | Year | Microcosm | Official |
|---|---|---|---|
| People with income of £100,000 or more | 2025-26 | 1.889m | 1.950m (HMRC) |
| People with income of £100,000 or more | 2026-27 | 2.009m | 2.063m (HMRC) |
| Tax-Free Childcare government top-up | 2025-26 | £0.600bn | £0.600bn (HMRC) |
| Families with a used TFC account | 2025-26 | 893k | 868k (HMRC) |
| Children with a used TFC account | 2025-26 | 1,153k | 1,152k (HMRC) |
| Under-3s using the working-parent entitlement | 2025-26 | 438k | 502k (DfE, incl. 31k aged 9-11 months) |
| 3- and 4-year-olds using it (hours beyond the universal 15) | 2025-26 | 515k | 389k (DfE) |
| Same, reception excluded | 2025-26 | 379k | 389k (DfE) |
| Free-entitlements spending, central | 2025-26 | £8.07bn | £8.2bn (DfE) |
| Free-entitlements spending, central | 2026-27 | £10.72bn | £9.9bn (DfE) |
| Same, every family using 30 extended hours | 2026-27 | £11.14bn | £9.9bn (DfE) |
| Same, on CenTax's basis (no reception, DfE rates) | 2026-27 | £9.69bn | £9.9bn (DfE) |

DfE's totals are the sums of the illustrative totals by age in its early years national funding formulae technical notes ([2026-27](https://www.gov.uk/government/publications/early-years-funding-2026-to-2027/2026-to-2027-early-years-national-funding-formulae-technical-note), section 3.3: £4.2bn for 3- and 4-year-olds, £2.7bn for 2-year-olds, £3.0bn for under-2s; [2025-26](https://www.gov.uk/government/publications/early-years-funding-2025-to-2026/2025-to-2026-early-years-national-funding-formulae-technical-note), section 3.2: £3.8bn, £2.1bn and £2.3bn); neither note states a combined figure, and both call their totals illustrative. The shipped baseline funds about 350,000 4-year-olds the data record in reception, which DfE does not count; without them the 3- and 4-year-olds match DfE, and funded-hours spending on CenTax's basis is within 2% of DfE's 2026-27 total. Matching the aggregate baseline would not bound the incremental cost for newly eligible families above £100,000 in any case: it is context, not a bound.

## Reproduce

Python 3.13 and [uv](https://docs.astral.sh/uv/). The release is in a private Hugging Face repository; set `HF_TOKEN` (or `HUGGING_FACE_TOKEN`) with read access to `policyengine/populace-uk-private`, or, if the pinned revision is already in your Hugging Face cache, set `HF_HUB_OFFLINE=1` instead and no token is used. The sha256 check applies either way.

```bash
uv sync --frozen --extra dev
export HF_TOKEN=...                # or: export HF_HUB_OFFLINE=1
.venv/bin/childcare-100k-build     # downloads and verifies the release, runs the population jobs, writes data/results.json
.venv/bin/pytest
```

`--aggregate-only` rebuilds the results file from cached runs, and refuses any cached run whose provenance (dataset sha256, policyengine.py and policyengine-uk versions, code hash) does not match.
