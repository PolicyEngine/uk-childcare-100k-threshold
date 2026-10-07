# Method

## The policy

The Conservative pledge (announced 4 October 2026, "a future Conservative government", with no start date) removes the £100,000 income limit on:

- the **30 funded hours for working parents** in England, children aged 9 months to 4 years. Today each parent (and partner) must not expect adjusted net income to exceed £100,000 in the tax year: Childcare (Free of Charge for Working Parents) (England) Regulations 2022 (SI 2022/1134), [reg 14(3)(c)(i)](https://www.legislation.gov.uk/uksi/2022/1134/regulation/14) for the parent and [reg 15(3)(b)(i)](https://www.legislation.gov.uk/uksi/2022/1134/regulation/15) for the partner;
- **Tax-Free Childcare** (UK-wide): the same test for the person and their partner, Childcare Payments (Eligibility) Regulations 2015 (SI 2015/448), [reg 15(1)](https://www.legislation.gov.uk/uksi/2015/448/regulation/15), with adjusted net income as in Income Tax Act 2007 s58.

The universal 15 hours for 3- and 4-year-olds has no income test and is unchanged.

## Data

- **Microcosm UK 2024-25, the certified national release** is the only dataset. Release `microcosm-uk-2024-25-national`, published 4 October 2026: the file `microcosm_uk_2024_25.h5` in `policyengine/populace-uk-private`, at the commit of the release's immutable cut tag `microcosm-uk-2024-25-national-20261002T230158Z-5c6b3f68` (`f9d1922cddab6b54a0dd37794a9bac74e3780c88`), sha256 `aa31bdf67c977927ea2b325567d1cf7a79d94381239bc79918a0a0fc9c9588af`. The release was built with policyengine-uk 2.100.0; nothing between 2.100.0 and 2.102.3 changes the childcare, Tax-Free Childcare or adjusted-net-income formulas.
- **This repository pins and verifies the file itself**, as PolicyEngine/uk-energy-reforms does: it downloads the file at that commit from Hugging Face (`HF_TOKEN` or `HUGGING_FACE_TOKEN` is required), checks the sha256, and stops on any mismatch or missing token. There is no fallback dataset.
- The Enhanced FRS and the earlier `populace_uk_2023` build are not used.

## Model

- **policyengine.py 6.2.1**, whose release bundle certifies **policyengine-uk 2.102.3**, runs every simulation: the population runs through `managed_microsimulation()` and the cliff example through `calculate_household()`.
- The 6.2.1 bundle does not yet register the certified Microcosm release, so the population runs pass the verified file with `allow_unmanaged=True`. The bundle's own dataset certification is therefore replaced by this repository's revision and sha256 pin, and `meta` records both. When a policyengine.py release registers `microcosm_uk_2024_25`, the runs switch to the managed dataset.
- 2.102.3 computes the Tax-Free Childcare top-up as 20% of gross spending, as in law (policyengine-uk 2.90.2, in policyengine.py 5.3.0, applied 25%).

## Weighting and outputs

- Every weighted total, mean, share and decile uses **microdf**: simulation outputs stay as weighted `MicroSeries` / `MicroDataFrame` objects, and person-to-family and family-to-household mappings use the model's own entity mapping (`map_to`). No weights are applied by hand.
- Record-level outputs stay in the gitignored `.cache/runs`. Each cached run carries a provenance key (dataset revision and sha256, policyengine.py and policyengine-uk versions, and a hash of this repository's engine and scenario code); a cached run whose key does not match the current one is refused, never reused.
- Only weighted aggregates reach `data/results.json`. A breakdown cell resting on fewer than ten gaining records, or fewer than ten records whose value changes, is suppressed; if that leaves one suppressed cell in a breakdown, a second cell is suppressed with it, and if no second cell can be suppressed the whole breakdown is withheld. Suppressed cells are published as `null` with `"suppressed": true`, never as zero.
- Nothing is defaulted: a missing provenance field, an unknown git revision or an empty cell stops the build or is published as suppressed.

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

## Years

Each fiscal year 2026-27 to 2029-30 is costed in full, because the proposal gives no start date. 2026-27 is already half over, so the dashboard leads with **2027-28**, the first full year a change could apply; 2026-27 stays in the tables as illustrative.

## Where the model and the law differ

| # | Issue | Direction for the cost | Handling |
|---|---|---|---|
| 1 | **Hours used.** Extended hours are capped by `maximum_extended_childcare_hours_usage`, an input the data draw (0-30 a week); universal hours use `max_free_entitlement_hours_used`, which defaults to 30. When a 3- or 4-year-old's family becomes eligible for the extended entitlement, its universal 570 hours a year are replaced by its drawn extended hours, so the child gains little or, with a draw under 15, loses hours (`recipients.families_losing`). | Understates | High end: usage set to the full 30 hours in baseline and reform (`full_30_hour_usage`). |
| 2 | **Under-1s.** Ages are whole years and age 0 gets no hours, so 9-11-month-olds never qualify. | Understates | High end adds them outside the model (`under_ones`): age-0 children in newly eligible families x 30 hours x 38 weeks x the model's under-2 rate x the share of the year they are eligible. Funding starts in the term after a child turns 9 months, so a child turning 9 months during the year is funded only from the following term; the share reflects that, which roughly halves the earlier "a quarter of age-0 children" estimate. Newly eligible families have already passed the model's take-up draw (`would_claim_extended_childcare`). |
| 3 | **Adjusted net income ignores pension contributions and Gift Aid.** policyengine-uk's `adjusted_net_income` sums gross taxable income; Income Tax Act 2007 s58 deducts relief-at-source pension contributions and Gift Aid, and net-pay contributions reduce taxable earnings. Parents who stay under the limit through pension contributions appear above it in the model. | Overstates | Low end (`ani_net_of_pension_contributions`): a family in which no adult's adjusted net income less `pension_contributions_relief` exceeds £100,000 already qualifies in law, so its modelled gain is removed. A correction on the model's realised-income measure, given the data's contributions; it does not address the expected-income test (row 9). |
| 4 | **Strict inequality for the 30 hours.** The model tests `ANI < £100,000`; the 2022 Regulations exclude a parent only if ANI is expected to *exceed* £100,000, so exactly £100,000 qualifies. Tax-Free Childcare uses `<=`, correctly. The 30-hours parameter's reference also cites the 2015 TFC Regulations rather than SI 2022/1134. | Negligible | Reported; visible in the cliff example at £100,000. |
| 5 | **Tax-Free Childcare routed share.** The model assumes all childcare spending goes through the account (`tax_free_childcare_spend_routed_share` = 1). | Overstates | Low end (`tfc_routed_share`): 0.58 in baseline and reform. |
| 6 | **Fixed childcare spending.** A family gaining funded hours keeps paying for the same childcare, so its TFC top-up is not reduced. | Overstates slightly | Reported. |
| 7 | **Minimum income test applied to every adult.** The model requires every adult in the family to pass the minimum income test for the 30 hours, even where the work condition is met through a partner's disability or caring; the law exempts such a partner. | Not affected by the reform | Reported only. |
| 8 | **Reception-age 4-year-olds.** The model ends funded hours at compulsory school age (5), so 4-year-olds in reception still receive funded hours; in law the entitlement ends when a child starts school. | Overstates the 3-4-year-old leg (most in the high end) | Reported. |
| 9 | **Expected, not realised, income.** The law tests the adjusted net income a parent *expects* for the tax year when applying or reconfirming (SI 2022/1134 reg 14(3)(c)(i) and 15(3)(b)(i); SI 2015/448 reg 15(1)); the model tests realised annual income. A parent who expected to stay under £100,000 but ended the year above it can already receive support, which the model counts as a reform cost; a parent who expected to exceed £100,000 but ended below it is modelled as eligible today. CenTax find that a third (33%) of parents whose year-end income was £100,000-£120,000 claimed and received some free childcare ([Removing the childcare cliff-edge](https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf), September 2026, pp. 5-6 and 59-60). | Unknown | Reported; not in the range. The first effect lowers the true cost, the second raises it, and the data cannot separate them. |
| 10 | **Tax-Free Childcare alongside Universal Credit.** In law a family cannot use Tax-Free Childcare while it claims Universal Credit; the model does not make the two mutually exclusive. | Baseline only (families gaining from the reform are above £100,000 and not on UC) | Reported; it raises the modelled baseline TFC spend. |
| 11 | **Funded-hours rates.** The model's hourly funding rates for 2026-27 are 1-6% below DfE's published 2026-27 rates (for example £6.23 against £6.61 an hour for 3- and 4-year-olds). | Understates slightly | Reported. |

## The range

The low and high ends add the sensitivities above to the central estimate. The high end adds full 30-hour usage and the under-1s. The low end removes the pension-contribution and Tax-Free Childcare routing effects **from one joint run**, so a family affected by both is counted once (adding the two separately would subtract part of the same gain twice).

| £bn | 2026-27 | 2027-28 | 2028-29 | 2029-30 |
|---|---|---|---|---|
| Full 30-hour usage | +0.57 | +0.62 | +0.69 | +0.72 |
| Under-1s (from the term after 9 months) | +0.05 | +0.05 | +0.05 | +0.06 |
| Pension contributions and TFC routing, joint | -0.01 | -0.02 | -0.02 | -0.02 |
| **Low** | 0.52 | 0.56 | 0.62 | 0.63 |
| **Central** | 0.54 | 0.57 | 0.63 | 0.66 |
| **High** | 1.16 | 1.24 | 1.37 | 1.43 |

The routing adjustment is small because the release already routes 59.3% of childcare spending through Tax-Free Childcare accounts (`tax_free_childcare_spend_routed_share` = 0.593 for every record), close to the 58% the low end assumes. An earlier version of this analysis showed a step in this adjustment in 2029-30 (−£0.044bn) and described it as a policy effect; it came from the model counting salary sacrifice returned to pay under the 2029 National Insurance cap in adjusted net income, which the correction below removes from the income tests. With the correction the joint adjustment is −£0.024bn in 2029-30.


## Salary sacrifice above the 2029 National Insurance cap (model correction)

From 6 April 2029, pension contributions made through salary sacrifice above £2,000 a year are subject to Class 1 National Insurance. HMRC's [policy paper](https://www.gov.uk/government/publications/salary-sacrifice-reform-for-pension-contributions-effective-from-6-april-2029/salary-sacrifice-reform-for-pension-contributions) says the measure changes National Insurance only and leaves salary sacrifice's effect on adjusted net income unchanged, naming Tax-Free Childcare among the schemes unaffected.

policyengine-uk 2.102.3 models the cap by adding the excess (`salary_sacrifice_returned_to_income`) to `employment_income`, so it also raises `adjusted_net_income`. For example, a parent on £97,000 after £10,000 of sacrifice reads £104,844.80 in 2029-30 and fails both childcare income tests.

`src/childcare_100k/corrections.py` corrects this in every run, baseline and reform alike:
- **What changes:** both income tests, `extended_childcare_entitlement_meets_income_requirements` and `tax_free_childcare_meets_income_requirements`, compare adjusted net income *less* the returned salary sacrifice with £100,000.
- **What doesn't:** `adjusted_net_income`, income tax and National Insurance are left as the model computes them. Correcting ANI itself would deduct the amount twice, because the model also gives it as pension relief.
- **Guard:** the replaced formulas are fingerprinted against policyengine-uk 2.102.3, so a change upstream stops the build instead of being silently overwritten, and the engine checks the correction reached each simulation.
- **Before 2029-30:** the correction does nothing.

It stays until policyengine-uk is fixed upstream. It lowers the 2029-30 central cost from £0.675bn to £0.655bn (30 hours £0.489bn → £0.482bn; Tax-Free Childcare £0.186bn → £0.173bn) and the high end from £1.46bn to £1.43bn; 2026-27 to 2028-29 are unchanged.

## Behaviour

Static only. No labour-supply response is modelled: parents who would earn more without the cliff, and those who keep income below £100,000 now, are held where they are. The Conservatives' claimed growth effects are not scored.

## Take-up

Take-up holds Microcosm's existing `would_claim_extended_childcare` and `would_claim_tfc` draws fixed; it is not modelled afresh for newly eligible families. The draw rates differ by income; `assumptions` in the results gives each rate overall and where a parent is over £100,000. A Tax-Free Childcare top-up also needs recorded childcare spending.

## Baseline validation

`baseline_validation` sets the unreformed model against HMRC's income tax liabilities statistics (people with income of £100,000 or more: 1.950m in 2025-26, 2.063m in 2026-27, July 2026 Table 2.5), HMRC's Tax-Free Childcare statistics (June 2026: £599.8m of top-ups to 868k families in 2025-26), DfE's January 2026 early years census and DfE's 2026-27 early years funding technical note (£9.9bn on the free entitlements). On the certified release:

- people with income of £100,000 or more: 1.885m in 2025-26 against HMRC's 1.950m, and 2.037m in 2026-27 against 2.063m;
- Tax-Free Childcare: £0.605bn of top-ups against £0.600bn, 870k families against 868k, 1,161k children against 1,152k;
- working-parent entitlement: 428k under-3s against DfE's 502k (the model cannot include 9-11-month-olds), and 402k 3- and 4-year-olds against 389k (row 8);
- free-entitlements spending in 2026-27: £5.81bn in the central run and £9.71bn with full 30-hour use, against DfE's £9.9bn.

## The £0.7bn benchmark

The Conservatives put the cost at about £700m a year when they announced the pledge (PA: "The Conservatives estimate the policy would cost £700 million a year"; BBC), funded by cutting staff at arm's-length public bodies (about £1.6bn by the end of the decade). The party's web announcement covers both the free hours and Tax-Free Childcare ("abolish the £100,000 childcare cliff edge for both free childcare hours and Tax-Free Childcare") and gives no figure or method. City AM says the costing "is based on a recent report by the Centre for the Analysis of Taxation" and that removing the Tax-Free Childcare limit as well "pushed up the costs slightly". CenTax label tax years by their later year (report p.2), so their "2030" is 2029-30, the year we compare. CenTax's report ([*Removing the childcare cliff-edge: impacts and cost of reform*](https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf), September 2026, Table 4.2) covers the **free childcare hours only**: a **static** cost of £980m in 2030, and a **net** cost of £640m after £340m of extra revenue: £210m of tax from parents who no longer keep their income below £100,000 (the intensive margin) and £130m of tax and National Insurance from partners who enter work (the extensive margin; Table 4.2 and the sentence after it). It does not cover Tax-Free Childcare.

The like-for-like comparison is therefore **our 30-hours leg against CenTax's static £0.98bn** (both static, both the free hours only). Our 30-hours leg is £0.48bn in 2029-30, half CenTax's static £0.98bn; with full 30-hour usage it rises to roughly £1.2bn. Much of the gap is free-hours usage: the central run draws a mean of about 15 extended hours a week and spends £5.81bn on all free hours against DfE's £9.9bn. The £0.7bn is therefore close to CenTax's net free-hours figure, £0.64bn, plus a small Tax-Free Childcare addition. Our total covers both schemes on the same static basis as our 30-hours leg.

## Cliff example

One illustrative family, computed with policyengine.py's `calculate_household()` for 2027-28: a couple in the South East with children aged 2 and 3, £20,000 a year of their own childcare spending, one parent on £40,000. Household net income after that spending is £101,619 when the other parent earns £99,000, £88,331 at exactly £100,000 (the model's strict `<` already removes the 30 hours), and £84,331 at £100,001; with the limits removed it is £102,200 at £100,001, a cliff of about £17,900.

## Reproduce

```bash
uv venv && uv pip install -e ".[dev]"
export HF_TOKEN=...                   # read access to policyengine/populace-uk-private
.venv/bin/childcare-100k-build        # downloads and verifies the release, runs the population jobs, writes data/results.json
.venv/bin/pytest
```

`--aggregate-only` rebuilds the results file from cached runs, and refuses any cached run whose provenance key does not match.
