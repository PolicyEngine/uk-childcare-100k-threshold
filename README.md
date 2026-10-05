# Removing the £100,000 childcare income limit

PolicyEngine UK analysis of the Conservative proposal (October 2026) to remove the £100,000 adjusted-net-income limit on:
- the **30 funded hours** for working parents of children aged 9 months to 4 years (England);
- **Tax-Free Childcare** (UK-wide).

The universal 15 hours for 3- and 4-year-olds is unaffected.

## Results

Static gross cost, £bn a year (positive = extra government spending). Microcosm (`populace_uk_2023`) is the primary dataset; the Enhanced FRS 2024-25 is the cross-check. policyengine.py 6.2.1 / policyengine-uk 2.102.3.

| | 2026-27 | 2027-28 | 2028-29 | 2029-30 |
|---|---|---|---|---|
| **Microcosm: total** | **0.87** | **0.95** | **1.03** | **1.14** |
| 30 funded hours | 0.63 | 0.69 | 0.75 | 0.84 |
| Tax-Free Childcare | 0.24 | 0.26 | 0.28 | 0.30 |
| Range (low to high) | 0.75-1.62 | 0.78-1.77 | 0.91-1.95 | 0.97-2.15 |
| **Enhanced FRS: total** | **0.48** | **0.54** | **0.56** | **0.62** |
| 30 funded hours | 0.34 | 0.38 | 0.40 | 0.44 |
| Tax-Free Childcare | 0.14 | 0.16 | 0.16 | 0.18 |
| Range (low to high) | 0.43-0.98 | 0.45-1.10 | 0.47-1.15 | 0.48-1.26 |

- **The two datasets differ mainly in how many high earners they hold.** Microcosm has about 2.9 million people with income of £100,000 or more in 2025-26 against HMRC's projected 2.0 million; the Enhanced FRS has 1.7 million. Microcosm's Tax-Free Childcare take-up draw is also higher for families above £100,000 (72%) than overall (56%). So Microcosm probably overstates the cost and the Enhanced FRS slightly understates it.
- **Against the Conservatives' £0.7bn** (the party's figure as reported by City AM; no year or method given): the Enhanced FRS central estimate is a little below it (£0.48-0.62bn), Microcosm's is above it (£0.87-1.14bn). If the £0.7bn is a first-year cost, the nearer comparison is 2026-27.
- The net cost equals the gross cost: no other tax or benefit in the model depends on these limits.
- Removing each limit alone gives the same two legs (0.63 and 0.24 in 2026-27): the schemes do not interact in the model.
- In 2029-30 about 275,000 families gain (Microcosm; 176,000 on the Enhanced FRS), by about £4,200 a year on average. Almost all are in England, and gains are confined to the top four income deciles, mostly the top two.
- Within the 30-hours leg, extended-hours spending rises by £0.96bn in 2029-30 and universal-hours spending falls by £0.12bn, as 3- and 4-year-olds move from the universal 15 hours to the extended hours.

### The range

| Adjustment (2029-30, Microcosm) | £bn | Why |
|---|---|---|
| Every family uses all 30 extended hours | +0.88 | The data draw about 15 hours a week on average |
| Add 9-11-month-olds | +0.13 | The model's whole-year ages give age 0 no hours |
| Deduct pension contributions from adjusted net income | -0.12 | The model's measure leaves them in, unlike the law |
| Route 58% of childcare spending through TFC accounts | -0.06 | The model assumes all of it |

The central run's free-hours spending (£6.9bn in 2026-27) is below DfE's £9.9bn; the 30-hour run (£11.4bn) is above it. See [docs/METHOD.md](docs/METHOD.md) for every model-versus-law difference and [data/results.json](data/results.json) for the full output ([schema](docs/RESULTS_SCHEMA.md)).

### Baseline validation (2025-26 unless stated)

| | Microcosm | Enhanced FRS | Official |
|---|---|---|---|
| TFC government top-up (£bn) | 0.51 | 1.04 | 0.60 (HMRC) |
| Children with a used TFC account | 689k | 1,108k | 1,152k (HMRC) |
| Families with a used TFC account | 580k | 905k | 868k (HMRC) |
| Under-3s on the working-parent entitlement | 530k | 579k | 502k (DfE, Jan 2026) |
| 3-4-year-olds on the working-parent entitlement | 381k | 428k | 389k (DfE, Jan 2026) |
| People with income of £100,000 or more | 2,869k | 1,702k | 1,955k (HMRC, projected) |
| Free entitlements spending, 2026-27 (£bn) | 6.91 | 7.00 | 9.9 (DfE) |

## Reproduce

Python 3.13 and [uv](https://docs.astral.sh/uv/). The two datasets are licensed and not in this repository; their sha256 must match the policyengine.py 6.2.1 bundle (`f17306cc…` and `e433e532…`).

```bash
uv venv && uv pip install -e ".[dev]"
mkdir -p .cache/worker/data
cp /path/to/populace_uk_2023.h5 /path/to/enhanced_frs_2024_25.h5 .cache/worker/data/
.venv/bin/childcare-100k-build     # 16 population jobs, one at a time, then data/results.json
.venv/bin/pytest
```

Microcosm jobs take about 1.5 minutes and 19 GB of memory each; the full build takes about 13 minutes. `--aggregate-only` rebuilds the results file from cached runs.
