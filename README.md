# Removing the £100,000 childcare income limit

PolicyEngine UK analysis of the Conservative proposal (October 2026) to remove the £100,000 adjusted-net-income limit on:
- the **30 funded hours** for working parents of children aged 9 months to 4 years (England);
- **Tax-Free Childcare** (UK-wide).

The universal 15 hours for 3- and 4-year-olds is unaffected.

## Data and model

- **Data:** Microcosm UK 2024-25, the certified national release (`microcosm-uk-2024-25-national`, published 4 October 2026), pinned by this repository at commit `f9d1922c` with sha256 `aa31bdf6…` and verified on download. It is the only dataset.
- **Model:** policyengine.py 6.2.1 (policyengine-uk 2.102.3) runs every simulation. Its bundle does not yet register the certified release, so the population runs pass the verified file to `managed_microsimulation()` with `allow_unmanaged=True`; they switch to the managed dataset when policyengine.py registers it.
- **Weighting:** microdf throughout; no weights are applied by hand.
- **No fallbacks:** a missing token, a sha256 mismatch, a stale cached run or a missing provenance field stops the build.

## Results

Static gross cost, £bn a year (positive = extra government spending), led by 2027-28, the first full year a change could apply. 2026-27 is shown as illustrative: it is half over.

| | 2026-27 | 2027-28 | 2028-29 | 2029-30 |
|---|---|---|---|---|
| **Total** | 0.56 | 0.59 | 0.65 | 0.68 |
| 30 funded hours | 0.41 | 0.43 | 0.48 | 0.51 |
| Tax-Free Childcare | 0.15 | 0.16 | 0.17 | 0.17 |
| Range (low to high) | 0.54-1.16 | 0.58-1.24 | 0.64-1.37 | 0.65-1.43 |

- **Who gains, 2027-28:** 278,000 families (338,000 children), on average £2,133 a year; 90,000 through the 30 hours and 228,000 through Tax-Free Childcare (families can gain from both). No family loses.
- **Four local corrections to policyengine-uk 2.102.3** (`src/childcare_100k/corrections.py`, every run and the household calculator): exactly £100,000 qualifies for the 30 hours; a partner on carer's allowance, ESA or another specified benefit need not pass the minimum earnings test (SI 2022/1134 reg 14(4)/15(4)); the universal and targeted 15 hours are kept when a family qualifies for the extended hours; and from 2029-30 the income tests ignore pension salary sacrifice that the model adds back to pay under the new £2,000 National Insurance cap. The first three add £0.02bn a year to the cost; the last lowers 2029-30 by £0.02bn. See [docs/METHOD.md](docs/METHOD.md#model-corrections).
- **If parents change how much they work** (OBR participation elasticities applied to the employed share; for parents in work, an assumed childcare-price elasticity of hours of −0.042, extrapolated from Brewer et al., applied to the change in the price of an extra hour of paid childcare, and the OBR income elasticities applied to the rise in household net income), the 2029-30 cost falls from £0.68bn to **£0.57bn** (£0.46bn-£0.64bn, an illustrative range, not a confidence interval): about 1,100 partners moving into work add £0.005bn, because their families then receive the support, and parents' hours bring back a net £0.11bn: £0.15bn from the lower price of an extra hour of childcare (Tax-Free Childcare's top-up; the funded hours are a fixed amount and change that price only where they cover all the paid care a family buys) less £0.035bn as better-off families work slightly less. Bunching at the limit is not modelled. See [docs/METHOD.md](docs/METHOD.md#behaviour).
- **The net cost equals the gross cost** (to within £1m of rounding): no other tax or benefit in the model depends on these limits.
- **Realised, not expected, income.** The model tests each parent's realised annual adjusted net income; the law tests the income a parent expects when applying. CenTax find that a third of parents who ended the year on £100,000-£120,000 still received some free childcare, which the model would count as a reform cost; parents who expected to exceed £100,000 but ended below it pull the other way. The net direction is unknown and is not in the range.
- **Against the £0.7bn.** The Conservatives put the plan's cost at about £700m a year (PA, BBC); City AM says it is based on CenTax's September 2026 report, with a small addition for Tax-Free Childcare. CenTax covers the free childcare hours only: a static £980m in 2030 (tax year 2029-30), or £640m net after £340m of extra tax: £210m from parents who no longer keep their income below £100,000 and £130m of tax and National Insurance from partners who enter work. It does not cover Tax-Free Childcare. The like-for-like comparison is our **30-hours leg** against CenTax's static £0.98bn. See [docs/METHOD.md](docs/METHOD.md#the-07bn-benchmark).

### The range

| Adjustment | Direction | Why |
|---|---|---|
| Every family uses all 30 extended hours | + | The data draw fewer hours on average |
| Add 9-11-month-olds, from the term after they turn 9 months | + | The model's whole-year ages give age 0 no hours |
| Deduct pension contributions from adjusted net income, and route 58% of childcare spending through TFC accounts (one joint run) | − | The model's measure leaves pension contributions in, unlike the law, and assumes all spending goes through the account |

In 2029-30 full 30-hour usage adds £0.70bn, the under-1s £0.06bn, and the joint pension and routing adjustment removes £0.03bn. See [docs/METHOD.md](docs/METHOD.md) for every model-versus-law difference and [data/results.json](data/results.json) for the full output ([schema](docs/RESULTS_SCHEMA.md)).

### Baseline validation

Microcosm against HMRC (people with income of £100,000 or more; Tax-Free Childcare top-ups, families and children), DfE (working-parent entitlement caseloads; £9.9bn free-entitlements spending in 2026-27) and the model's funding rates against DfE's:

| | Year | Microcosm | Official |
|---|---|---|---|
| People with income of £100,000 or more | 2025-26 | 1.885m | 1.950m (HMRC) |
| People with income of £100,000 or more | 2026-27 | 2.037m | 2.063m (HMRC) |
| Tax-Free Childcare government top-up | 2025-26 | £0.605bn | £0.600bn (HMRC) |
| Families with a used TFC account | 2025-26 | 870k | 868k (HMRC) |
| Children with a used TFC account | 2025-26 | 1,161k | 1,152k (HMRC) |
| Under-3s using the working-parent entitlement | 2025-26 | 422k | 502k (DfE) |
| 3- and 4-year-olds using it (hours beyond the universal 15) | 2025-26 | 352k | 389k (DfE) |
| Free-entitlements spending, central | 2026-27 | £6.04bn | £9.9bn (DfE) |
| Same, every family using 30 extended hours | 2026-27 | £10.0bn | £9.9bn (DfE) |

The certified release matches HMRC's high-earner count and Tax-Free Childcare spending closely. DfE's £9.9bn falls between the central run and full 30-hour usage (just below the latter), but it is an illustrative total based partly on forecasts, and bracketing the aggregate baseline does not bound the incremental cost for newly eligible families above £100,000, whose take-up and hours may differ. It is context, not a bound.

## Reproduce

Python 3.13 and [uv](https://docs.astral.sh/uv/). The release is in a private Hugging Face repository; set `HF_TOKEN` (or `HUGGING_FACE_TOKEN`) with read access to `policyengine/populace-uk-private`.

```bash
uv venv && uv pip install -e ".[dev]"
export HF_TOKEN=...
.venv/bin/childcare-100k-build     # downloads and verifies the release, runs the population jobs, writes data/results.json
.venv/bin/pytest
```

`--aggregate-only` rebuilds the results file from cached runs, and refuses any cached run whose provenance (dataset sha256, policyengine.py and policyengine-uk versions, code hash) does not match.
