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

The headline costs are **static**: nobody changes how much they work. A labour supply response is costed alongside them (`labour_supply` in the results; `src/childcare_100k/labour_supply.py` and `hours_response.py`, ported from [PolicyEngine/free-childcare-reform](https://github.com/PolicyEngine/free-childcare-reform)) and gives a **dynamic cost** = static total − the money it brings back. It runs as its own cached job (`labour_supply`) on the central baseline and reform simulations, with the same provenance key as every other run, because the gain to work needs live simulations.

**Who responds.** Adults (the first two in each family; not self-employed, students or aged 60 and over, the OBR's exclusions) in a family whose **youngest child is under 12** and in which **at least one adult's income, as the limits test it** (adjusted net income less salary sacrifice returned to pay), **is over £100,000** in the baseline. Under 12 because Tax-Free Childcare runs to 11 and contains the 30 hours' 9 months-4 years band; following Brewer et al., it is the parent whose *youngest* child is in the band that the support frees to work. Over £100,000 because that is the only place the reform changes anything: mechanically, the partner of a parent over the limit, who today gains no childcare support by working and under the reform brings the family the 30 hours and Tax-Free Childcare by doing so. The job checks that the reform leaves everyone else's gain to work unchanged (it does, in every year), and about 1.2-1.3 million adults are in the population.

**Moving into work (extensive margin).** OBR participation elasticities (Table A1: by sex, partner's work, age of youngest child and earnings quintile; policyengine-uk's `calculate_participation_elasticities`), converted to an elasticity with respect to the gain to work by (1 − replacement rate) as in the OBR's Appendix E, times the proportional change in each adult's gain to work. The gain to work is in-work less out-of-work household net income, each recomputed by the model, **net of the childcare a parent pays to work**: a non-worker is given the mean childcare spend of working parents whose youngest child is the same age, pro-rated to 18.8 hours a week, less the Tax-Free Childcare the scenario would pay on it (from the model's own in-work eligibility); the 30 hours reach them through the model. Entrants work 18.8 hours at the median hourly wage of workers of their sex and age band (policyengine-uk's `impute_wages_for_nonworkers`). Responses are expected values, not random draws. The Exchequer gains an entrant's earnings less the rise in their household's net income (tax and National Insurance paid, less the childcare support the family now receives) and less the Tax-Free Childcare top-up on their new childcare.

**Hours (intensive margin).** A childcare-price elasticity of hours of −0.042 (Brewer, Cattan, Crawford and Rabe, IFS WP20/09: +0.600 weekly hours on a mean of 14.319 for full-time eligibility, taken against a 100% price fall), for responding adults **at or below £100,000** who work and pay for childcare and whose out-of-pocket cost falls. Out-of-pocket cost is childcare spending less Tax-Free Childcare; under the reform, newly funded hours displace paid care at 90.5% of their value (1 − 54/570, IFS BN189), capped at the family's spending, and Tax-Free Childcare applies to what is left. The model recomputes tax and benefits on the extra earnings. It is a total-hours estimate (mothers, with zeros for non-workers), so it overlaps slightly with the extensive margin.

**Range.** Low and high scale every elasticity by 1/3 and 2: childcare-price elasticities of maternal employment of −0.05 and −0.30 against a central −0.15 (Akgündüz and Plantenga's meta-analysis, read for the UK).

| £bn a year, positive = money back | 2026-27 | 2027-28 | 2028-29 | 2029-30 |
|---|---|---|---|---|
| Moving into work, central (low to high) | -0.003 (-0.001 to -0.006) | -0.003 (-0.001 to -0.006) | -0.003 (-0.001 to -0.006) | -0.003 (-0.001 to -0.006) |
| Hours, central (low to high) | 0.027 (0.009 to 0.055) | 0.029 (0.010 to 0.059) | 0.031 (0.010 to 0.063) | 0.033 (0.011 to 0.066) |
| **Dynamic cost**, central (high to low elasticities) | 0.515 (0.490 to 0.531) | 0.547 (0.520 to 0.564) | 0.602 (0.573 to 0.621) | 0.625 (0.595 to 0.645) |
| Entrants, central | 600 | 600 | 600 | 600 |

**Why so few move into work.** About 105,000 non-working adults are in the population. The reform raises their gain to work by about 12% on average, and the OBR elasticity, about 0.37 with respect to in-work income, falls to about 0.04 with respect to the gain to work once multiplied by (1 − replacement rate): with a partner on over £100,000, the household's income out of work is about 90% of its income in work. That gives about 600 entrants. And they bring in almost nothing: the tax and National Insurance on 18.8 hours is roughly matched by the 30 hours and Tax-Free Childcare their family now receives, so the extensive offset is slightly negative. A handful of parents already in work have a slightly lower gain to work under the reform, where a 3- or 4-year-old's universal 15 hours are replaced by fewer extended hours (row 1 of the table above); they round to no leavers.

**Not modelled.** The parent over £100,000 is kept out of the dynamic cost. Parents who today keep their income below the limit and would earn more without it (bunching: CenTax's +£210m intensive margin in 2029-30) are not modelled. Their hours response to cheaper childcare is published as a sensitivity (`intensive_over_limit`), not added: at the same −0.042 it would bring back £0.21bn in 2029-30 (£0.07bn to £0.41bn), because their earnings are large and taxed at up to 62% in the personal allowance taper, but the elasticity is measured on mothers and that group's response to the limit itself is not modelled.

**Against CenTax.** CenTax (Table 4.2, 2030 = 2029-30, free hours only) find +£130m from partners entering work and +£210m from parents no longer keeping income below £100,000. Our extensive margin covers both schemes and brings back −£0.003bn: CenTax's partner response implies far more entrants than the OBR's elasticities give for second earners in high-income households, and it is not clear that CenTax net off the childcare support entrants' families then receive. Their £210m has no counterpart here. Neither figure is a target.

The household calculator and the breakdowns by income, family type and region are static.

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
