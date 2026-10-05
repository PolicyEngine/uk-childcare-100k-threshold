# Method

## The policy

The Conservative proposal (3-4 October 2026) removes the £100,000 income limit on:

- the **30 funded hours for working parents** in England, children aged 9 months to 4 years. Today each parent (and partner) must not expect adjusted net income to exceed £100,000 in the tax year: Childcare (Free of Charge for Working Parents) (England) Regulations 2022 (SI 2022/1134), [reg 14(3)(c)(i)](https://www.legislation.gov.uk/uksi/2022/1134/regulation/14) for the parent and [reg 15(3)(b)(i)](https://www.legislation.gov.uk/uksi/2022/1134/regulation/15) for the partner;
- **Tax-Free Childcare** (UK-wide): the same test for the person and their partner, Childcare Payments (Eligibility) Regulations 2015 (SI 2015/448), [reg 15(1)](https://www.legislation.gov.uk/uksi/2015/448/regulation/15), with adjusted net income as in Income Tax Act 2007 s58.

The universal 15 hours for 3- and 4-year-olds has no income test and is unchanged.

## Software and data

- **policyengine.py 6.2.1**, the newest release on 5 October 2026. It installs cleanly, its release bundle certifies **policyengine-uk 2.102.3**, and it lists both datasets with the same sha256 as the local files (the 5.3.0 bundle does too, but carries policyengine-uk 2.90.2, which overstated Tax-Free Childcare top-ups by a quarter: it applied the 25% deposit-side rate to gross spending. 2.102.3 applies 20% of gross spending, as in law).
- The **Enhanced FRS 2024-25** (`enhanced_frs_2024_25`, policyengine-uk-data 1.56.16, sha256 `e433e532…`) is the primary dataset; **Microcosm** (`populace_uk_2023`, revision `populace-uk-2023-dd68c73-4aa4b14-20260619T023711Z`, sha256 `f17306cc…`) is the cross-check.
- **Why the Enhanced FRS is the headline.** The cost turns on how many parents earn over £100,000. In 2025-26 the Enhanced FRS holds 1.70 million people with income of £100,000 or more, against HMRC's projected 1.96 million; Microcosm holds 2.87 million, 47% too many. Microcosm's Tax-Free Childcare take-up draw is also higher above £100,000 (72%) than overall (56%). So the Microcosm cost (£1.14bn in 2029-30) is higher than the Enhanced FRS headline (£0.62bn), and probably too high. The Enhanced FRS is not perfect either: it slightly undercounts high earners and its Tax-Free Childcare spend is 1.7 times HMRC's, while its caseload is right.
- **The central figure likely sits low on funded hours.** The central baseline spends £7.0bn on free hours in 2026-27 against DfE's £9.9bn, while every family using all 30 extended hours gives £11.7bn. The truth on that leg lies between the central and high ends.
- Datasets load through `managed_microsimulation()`, which enforces the bundle: each job runs with its working directory at `.cache/worker`, holding copies of the two `.h5` files in `./data`, so the loader verifies the sha256 and downloads nothing. Each (dataset, scenario) runs in its own process, one at a time (Microcosm peaks at about 17 GB).
- Record-level arrays stay in the gitignored `.cache/runs`; only weighted aggregates reach `data/results.json`, with breakdown cells resting on fewer than ten gaining records suppressed.

## The reform in the model

Two parameters are set to infinity for each fiscal year 2026-27 to 2029-30 and nothing else changes (a test walks the whole parameter tree to check):

| Parameter | How the model applies it |
|---|---|
| `gov.dfe.extended_childcare_entitlement.income.limit` | `extended_childcare_entitlement_meets_income_requirements`: each adult in the family must have `adjusted_net_income < limit` (and quarterly earnings above 16 hours at the minimum wage). The family must be in England and meet the work condition. |
| `gov.hmrc.tax_free_childcare.income.income_limit` | `tax_free_childcare_meets_income_requirements`: each parent must have `adjusted_net_income <= limit` (and expected earnings over 13 weeks above 16 hours at the minimum wage). |

Costs are the change in weighted spending:

- **30 hours** = change in `extended_childcare_entitlement` + `universal_childcare_entitlement` + `targeted_childcare_entitlement`. The model switches the universal 15 hours off for a family once it is eligible for the extended entitlement, so the extended hours *replace* the universal hours for 3- and 4-year-olds; counting the change in extended spending alone would double count.
- **Tax-Free Childcare** = change in `tax_free_childcare` (20% of the family's childcare spending, capped at £2,000 a child, £4,000 if disabled).
- **Net** = minus the change in `gov_balance`. It equals gross: no other tax or benefit in the model depends on these limits.

## Where the model and the law differ

| # | Issue | Direction for the cost | Handling |
|---|---|---|---|
| 1 | **Hours used.** Extended hours are capped by `maximum_extended_childcare_hours_usage`, an input the data draw at about 15 hours a week on average (0-30); universal hours use `max_free_entitlement_hours_used`, which defaults to 30. When a 3- or 4-year-old's family becomes eligible for the extended entitlement, its universal 570 hours a year are replaced by its drawn extended hours, so the child gains little or, with a draw under 15, loses hours (`recipients.families_losing`). | Understates | High end: usage set to the full 30 hours in baseline and reform (`full_30_hour_usage`). The central baseline spends below DfE's 2026-27 total and the 30-hour run above it (see validation). |
| 2 | **Under-1s.** Ages are whole years and age 0 gets no hours, so 9-11-month-olds never qualify. | Understates | High end adds them outside the model (`under_ones`): a quarter of age-0 children in newly eligible families x 30 hours x 38 weeks x the model's under-2 rate. Newly eligible families have already passed the model's take-up draw (`would_claim_extended_childcare`, about 78-79%). |
| 3 | **Adjusted net income ignores pension contributions and Gift Aid.** policyengine-uk's `adjusted_net_income` sums gross taxable income; Income Tax Act 2007 s58 deducts relief-at-source pension contributions and Gift Aid, and net-pay contributions reduce taxable earnings. Parents who stay under the limit through pension contributions appear above it in the model. | Overstates | Low end (`ani_net_of_pension_contributions`): a family in which no adult's adjusted net income less `pension_contributions_relief` exceeds £100,000 already qualifies in law, so its modelled gain is removed. Exact for a static model, given the data's contributions. |
| 4 | **Strict inequality for the 30 hours.** The model tests `ANI < £100,000`; the 2022 Regulations exclude a parent only if ANI is expected to *exceed* £100,000, so exactly £100,000 qualifies. Tax-Free Childcare uses `<=`, correctly. The 30-hours parameter's reference also cites the 2015 TFC Regulations rather than SI 2022/1134. | Negligible | Reported; visible in the cliff example at £100,000. |
| 5 | **Tax-Free Childcare routed share.** The bundled datasets predate the routed-share calibration in later policyengine-uk-data builds, so the model assumes all childcare spending goes through the account (`tax_free_childcare_spend_routed_share` = 1). | Overstates | Low end (`tfc_routed_share`): 0.58 in baseline and reform. |
| 6 | **Fixed childcare spending.** A family gaining funded hours keeps paying for the same childcare, so its TFC top-up is not reduced. | Overstates slightly | Reported. |
| 7 | **Minimum income test applied to every adult.** The model requires every adult in the family to pass the minimum income test for the 30 hours, even where the work condition is met through a partner's disability or caring; the law exempts such a partner. | Not affected by the reform | Reported only. |

policyengine-uk 2.90.2's Tax-Free Childcare formula (`expenses x r/(1-r)`, 25%) is not an issue here: 2.102.3 computes 20% of gross spending.

## Behaviour

Static only. No labour-supply response is modelled: parents who would earn more without the cliff, and those who keep income below £100,000 now, are held where they are. The Conservatives' claimed growth effects are not scored.

## Take-up

Take-up comes from the datasets' `would_claim_extended_childcare` and `would_claim_tfc` draws, which are the same for families above and below £100,000 (`assumptions` in the results). A Tax-Free Childcare top-up also needs recorded childcare spending.

## Baseline validation

`baseline_validation` sets the unreformed model in 2025-26 (spending: 2026-27) against HMRC Tax-Free Childcare statistics (June 2026), DfE's January 2026 early years census, DfE's 2026-27 early years funding technical note and HMRC's income tax liabilities statistics. No other organisation's estimate of this policy was used: the only external cost is the Conservatives' own £0.7bn, used as a benchmark.

## Reproduce

```bash
uv venv && uv pip install -e ".[dev]"
mkdir -p .cache/worker/data
cp /path/to/populace_uk_2023.h5 /path/to/enhanced_frs_2024_25.h5 .cache/worker/data/   # sha256 must match the bundle
.venv/bin/childcare-100k-build        # 16 population jobs, then data/results.json
.venv/bin/pytest
```
