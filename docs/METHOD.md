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
| `gov.dfe.extended_childcare_entitlement.income.limit` | `extended_childcare_entitlement_meets_income_requirements`: each adult in the family must have adjusted net income `<= limit` (the model's `<`, corrected) and quarterly earnings above 16 hours at the minimum wage, unless the adult is on a specified benefit (reg 14(4)/15(4), corrected). The family must be in England and meet the work condition. |
| `gov.hmrc.tax_free_childcare.income.income_limit` | `tax_free_childcare_meets_income_requirements`: each parent must have `adjusted_net_income <= limit` (and expected earnings over 13 weeks above 16 hours at the minimum wage). |

Costs are the change in weighted spending:

- **30 hours** = change in `extended_childcare_entitlement` + `universal_childcare_entitlement` + `targeted_childcare_entitlement`. policyengine-uk switches the universal and targeted 15 hours off once a family is eligible for the extended entitlement; the correction below keeps them, as the law does, and counts as extended only each child's funded hours above them. The universal and targeted changes are therefore zero, and all three are summed so nothing is missed.
- **Tax-Free Childcare** = change in `tax_free_childcare` (20% of the family's childcare spending, capped at £2,000 a child, £4,000 if disabled).
- **Net** = minus the change in `gov_balance`. It equals gross (unrounded, to the pound, in every year): no other tax or benefit in the model depends on these limits. Rounded to £m, the published net and gross figures can differ by £1m.

## Years

Each fiscal year 2026-27 to 2029-30 is costed in full, because the proposal gives no start date. 2026-27 is already half over, so the dashboard leads with **2027-28**, the first full year a change could apply; 2026-27 stays in the tables as illustrative.

## Where the model and the law differ

| # | Issue | Direction for the cost | Handling |
|---|---|---|---|
| 1 | **Hours used.** Extended hours are capped by `maximum_extended_childcare_hours_usage`, an input the data draw (0-30 a week); universal hours use `max_free_entitlement_hours_used`, which defaults to 30. policyengine-uk replaces a 3- or 4-year-old's universal 570 hours a year with its drawn extended hours once the family is eligible, so with a draw under 15 a newly eligible child lost hours (about 10,000 families in an earlier version). The correction keeps the universal hours as a floor (in law the working-parent hours come on top of them), so no family loses (`recipients.families_losing` is 0) and a child gains only the drawn hours above 15. | Understates | High end: usage set to the full 30 hours in baseline and reform (`full_30_hour_usage`). |
| 2 | **Under-1s.** Ages are whole years and age 0 gets no hours, so 9-11-month-olds never qualify. | Understates | High end adds them outside the model (`under_ones`): age-0 children in newly eligible families x 30 hours x 38 weeks x the model's under-2 rate x the share of the year they are eligible. Funding starts in the term after a child turns 9 months, so a child turning 9 months during the year is funded only from the following term; the share reflects that, which roughly halves the earlier "a quarter of age-0 children" estimate. Newly eligible families have already passed the model's take-up draw (`would_claim_extended_childcare`). |
| 3 | **Adjusted net income ignores pension contributions and Gift Aid.** policyengine-uk's `adjusted_net_income` sums gross taxable income; Income Tax Act 2007 s58 deducts relief-at-source pension contributions and Gift Aid, and net-pay contributions reduce taxable earnings. Parents who stay under the limit through pension contributions appear above it in the model. | Overstates | Low end (`ani_net_of_pension_contributions`): a family in which no adult's adjusted net income less `pension_contributions_relief` exceeds £100,000 already qualifies in law, so its modelled gain is removed. A correction on the model's realised-income measure, given the data's contributions; it does not address the expected-income test (row 9). |
| 4 | **Strict inequality for the 30 hours.** policyengine-uk 2.102.3 tests `ANI < £100,000`; the 2022 Regulations exclude a parent only if ANI is expected to *exceed* £100,000, so exactly £100,000 qualifies. Tax-Free Childcare uses `<=`, correctly. The 30-hours parameter's reference also cites the 2015 TFC Regulations rather than SI 2022/1134. | Negligible in aggregate | Corrected (`<=`, corrections.py), in the population runs and the household calculator; fixed upstream in policyengine-uk#2079. |
| 5 | **Tax-Free Childcare routed share.** The certified release routes 59.3% of childcare spending through a Tax-Free Childcare account (`tax_free_childcare_spend_routed_share` = 0.593 for every record), and the central run uses it. (Builds before the certified release left the model's default of 1, all spending routed.) | Overstates slightly, if fewer families route spending | Low end (`tfc_routed_share`): 0.58 in baseline and reform. |
| 6 | **Fixed childcare spending.** A family gaining funded hours keeps paying for the same childcare, so its TFC top-up is not reduced. | Overstates slightly | Reported. |
| 7 | **A partner on a specified benefit.** policyengine-uk requires every adult to pass the minimum income test for the 30 hours, even where the work condition is met through a partner's caring or incapacity; SI 2022/1134 reg 14(4) and 15(4) exempt such a partner from the work and income conditions. The reform affects them: a family with a parent over £100,000 and a partner on, say, contributory ESA gains the 30 hours only once the limit goes. | Understated before the correction | Corrected (corrections.py) for the benefits the model holds: carer's allowance, contributory and income-related ESA, incapacity benefit, severe disablement allowance and the Universal Credit carer element. Not covered: limited capability for work itself (the model's `uc_limited_capability_for_WRA` is a PIP/DLA proxy, and the model's work condition does not accept it) and NI credits. Tax-Free Childcare has the same route (SI 2015/448 reg 13), not corrected here (fixed upstream in policyengine-uk#2079), so the TFC leg is slightly understated for such families. |
| 8 | **Reception-age 4-year-olds.** The model ends funded hours at compulsory school age (5), so 4-year-olds in reception still receive funded hours; in law the entitlement ends when a child starts school. | Overstates the 3-4-year-old leg (most in the high end) | Reported. |
| 9 | **Expected, not realised, income.** The law tests the adjusted net income a parent *expects* for the tax year when applying or reconfirming (SI 2022/1134 reg 14(3)(c)(i) and 15(3)(b)(i); SI 2015/448 reg 15(1)); the model tests realised annual income. A parent who expected to stay under £100,000 but ended the year above it can already receive support, which the model counts as a reform cost; a parent who expected to exceed £100,000 but ended below it is modelled as eligible today. CenTax find that a third (33%) of parents whose year-end income was £100,000-£120,000 claimed and received some free childcare ([Removing the childcare cliff-edge](https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf), September 2026, pp. 5-6 and 59-60). | Unknown | Reported; not in the range. The first effect lowers the true cost, the second raises it, and the data cannot separate them. |
| 10 | **Tax-Free Childcare alongside Universal Credit.** In law a family cannot use Tax-Free Childcare while it claims Universal Credit; the model does not make the two mutually exclusive. | Baseline only (families gaining from the reform are above £100,000 and not on UC) | Reported; it raises the modelled baseline TFC spend. |
| 11 | **Funded-hours rates.** The model's hourly funding rates for 2026-27 are 1-6% below DfE's published 2026-27 rates (for example £6.23 against £6.61 an hour for 3- and 4-year-olds). | Understates slightly | Reported. |

## The range

The low and high ends add the sensitivities above to the central estimate. The high end adds full 30-hour usage and the under-1s. The low end removes the pension-contribution and Tax-Free Childcare routing effects **from one joint run**, so a family affected by both is counted once (adding the two separately would subtract part of the same gain twice).

| £bn | 2026-27 | 2027-28 | 2028-29 | 2029-30 |
|---|---|---|---|---|
| Full 30-hour usage | +0.56 | +0.60 | +0.67 | +0.70 |
| Under-1s (from the term after 9 months) | +0.05 | +0.05 | +0.05 | +0.06 |
| Pension contributions and TFC routing, joint | -0.01 | -0.02 | -0.02 | -0.03 |
| **Low** | 0.54 | 0.58 | 0.64 | 0.65 |
| **Central** | 0.56 | 0.59 | 0.65 | 0.68 |
| **High** | 1.16 | 1.24 | 1.37 | 1.43 |

The routing adjustment is small because the release already routes 59.3% of childcare spending through Tax-Free Childcare accounts (`tax_free_childcare_spend_routed_share` = 0.593 for every record), close to the 58% the low end assumes. An earlier version of this analysis showed a step in this adjustment in 2029-30 (−£0.044bn) and described it as a policy effect; it came from the model counting salary sacrifice returned to pay under the 2029 National Insurance cap in adjusted net income, which the correction below removes from the income tests. With the correction the joint adjustment is −£0.025bn in 2029-30.


## Model corrections

`src/childcare_100k/corrections.py` replaces six policyengine-uk 2.102.3 formulas in every run, baseline and reform alike, and in the household calculator. Each replaced formula is fingerprinted, so a change upstream stops the build instead of being silently overwritten; the engine checks the corrections reached each population simulation, and the household calculator checks they reached its own.

1. **Exactly £100,000 qualifies for the 30 hours** (`extended_childcare_entitlement_meets_income_requirements`: `<=`, not `<`). Row 4 above.
2. **A partner on a specified benefit** (`extended_childcare_entitlement_eligible`): an adult on carer's allowance, ESA, incapacity benefit, severe disablement allowance or the Universal Credit carer element need not pass the income test (SI 2022/1134 reg 14(4), 15(4)); the working parent still must, and the model's work condition still needs one parent in work. Row 7 above.
3. **The universal and targeted 15 hours are a floor** (`universal_childcare_entitlement_eligible`, `targeted_childcare_entitlement_eligible`, `extended_childcare_entitlement`): eligibility for the extended hours no longer switches them off, and each child's extended value is its funded hours above them, `max(0, extended hours x rate x 38 - universal - targeted)`. For a 3- or 4-year-old, policyengine-uk's 30 extended hours are the whole entitlement, universal included, so this adds each hour once: a child's funded hours are the larger of the floor and its drawn extended hours. Row 1 above; policyengine-uk#1930.
4. **Salary sacrifice returned to pay** from April 2029 is not income for the limits (below).

Together, corrections 1-3 raise the static cost by £0.020bn in 2027-28 and £0.023bn in 2029-30 (all in the 30-hours leg). £0.011bn and £0.012bn of that is the losses that about 10,000 and 12,000 families had under correction 3's model artefact, now gone (no family loses); the rest is not separated between families whose gain no longer nets off a lost universal entitlement and the newly covered exempt-partner and exactly-£100,000 cases. Corrections 1 and 2 are fixed upstream in policyengine-uk#2079, merged after the certified 2.102.3.

### Salary sacrifice above the 2029 National Insurance cap

From 6 April 2029, pension contributions made through salary sacrifice above £2,000 a year are subject to Class 1 National Insurance. HMRC's [policy paper](https://www.gov.uk/government/publications/salary-sacrifice-reform-for-pension-contributions-effective-from-6-april-2029/salary-sacrifice-reform-for-pension-contributions) says the measure changes National Insurance only and leaves salary sacrifice's effect on adjusted net income unchanged, naming Tax-Free Childcare among the schemes unaffected.

policyengine-uk 2.102.3 models the cap by adding the excess (`salary_sacrifice_returned_to_income`) to `employment_income`, so it also raises `adjusted_net_income`. For example, a parent on £97,000 after £10,000 of sacrifice reads £104,844.80 in 2029-30 and fails both childcare income tests.

Correction 4 corrects this in every run, baseline and reform alike:
- **What changes:** both income tests, `extended_childcare_entitlement_meets_income_requirements` and `tax_free_childcare_meets_income_requirements`, compare adjusted net income *less* the returned salary sacrifice with £100,000.
- **What doesn't:** `adjusted_net_income`, income tax and National Insurance are left as the model computes them. Correcting ANI itself would deduct the amount twice, because the model also gives it as pension relief.
- **Before 2029-30:** the correction does nothing.

It stays until policyengine-uk is fixed upstream. When it was introduced (before corrections 1-3) it lowered the 2029-30 central cost from £0.675bn to £0.655bn (30 hours £0.489bn → £0.482bn; Tax-Free Childcare £0.186bn → £0.173bn) and the high end from £1.46bn to £1.43bn; 2026-27 to 2028-29 were unchanged.

## Behaviour

The headline costs are **static**: nobody changes how much they work. A labour supply response is costed alongside them (`labour_supply` in the results; `src/childcare_100k/labour_supply.py` and `hours_response.py`, ported from [PolicyEngine/free-childcare-reform](https://github.com/PolicyEngine/free-childcare-reform)) and gives a **dynamic cost** = static total − the money it brings back. It runs as its own cached job (`labour_supply`) on the central baseline and reform simulations, with the same provenance key as every other run, because the gain to work needs live simulations.

**Who responds.** Adults (the first two in each family; not self-employed, students, disabled or aged 60 and over, the OBR's exclusions in its Table A4; "disabled" is the model's `is_disabled_for_benefits`, receipt of DLA or PIP) in a family whose **youngest child is under 12** and in which **at least one adult's income, as the limits test it** (adjusted net income less salary sacrifice returned to pay), **is over £100,000** in the baseline. Under 12 because Tax-Free Childcare runs to 11 and contains the 30 hours' 9 months-4 years band; following Brewer et al., it is the parent whose *youngest* child is in the band that the support frees to work. Over £100,000 because that is the only place the reform changes anything: mechanically, the partner of a parent over the limit, who today gains no childcare support by working and under the reform brings the family the 30 hours and Tax-Free Childcare by doing so. The job checks that the reform leaves everyone else's gain to work unchanged (it does, in every year), and about 1.2-1.3 million adults are in the population.

**Moving into work (extensive margin).** OBR participation elasticities (Table A1: by sex, partner's work, age of youngest child and earnings quintile; policyengine-uk's `calculate_participation_elasticities`). Each is the percentage change in the probability of working for a percentage change in income in work; Adam and Phillips (IFS R75, Appendix E) convert it to the gain to work G by G / I, where I is in-work income (with G = I − O this is the familiar 1 − replacement rate). Our gain to work nets off childcare, so the factor is the childcare-adjusted G / I actually used. Because the elasticity is a change in the *probability* of working, it applies to the employed share: for a group with employment rate P the employed share rises by P × e × dG/G. As in Adam and Phillips, who reweight the working records, new employment is the weighted sum over responding *workers* of their own e × dG/G; those entrants are then given the earnings and fiscal profile of the responding non-workers, shared in proportion to each non-worker's own e × dG/G (no non-worker's probability exceeds 1). A worker whose gain to work falls leaves with probability e × |dG/G|. (An earlier version applied e × dG/G to each non-worker, which gives (1 − P) × e × dG/G: about 500 entrants in 2029-30 rather than 1,100.) The gain to work is in-work less out-of-work household net income, each recomputed by the model, **net of the childcare a parent pays to work**: a non-worker is given the mean childcare spend of working parents whose youngest child is the same age, pro-rated to 18.8 hours a week, less the Tax-Free Childcare the scenario would pay on it (from the model's own in-work eligibility); the 30 hours reach them through the model. Entrants work 18.8 hours at the median hourly wage of workers of their sex and age band (policyengine-uk's `impute_wages_for_nonworkers`). Responses are expected values, not random draws. The Exchequer gains an entrant's earnings less the rise in their household's net income (tax and National Insurance paid, less the childcare support the family now receives) and less the Tax-Free Childcare top-up on their new childcare.

**Hours (intensive margin).** An assumed childcare-price elasticity of hours of −0.042, for every responding adult who works and pays for childcare and whose out-of-pocket cost falls, **whatever their income**, including the parent over £100,000 (whose extra earnings are taxed at up to 62%; the elasticity is not measured on that group). It is an extrapolated scenario assumption, not an estimated price elasticity: Brewer, Cattan, Crawford and Rabe (IFS WP20/09, Table A.3 panel B) estimate +0.600 weekly hours, on a mean of 14.319 including zeros for non-workers, for mothers whose youngest child becomes eligible for full-time instead of part-time free care. Treating that eligibility as a 100% fall in price, and applying the result to every working adult with a child under 12, extends it to an intervention, to parents (fathers) and to child ages it was not estimated on; it is not varied over those mappings. Out-of-pocket cost is childcare spending less Tax-Free Childcare; under the reform, newly funded hours are *assumed* to displace paid care at 90.5% of their value, capped at the family's spending, and Tax-Free Childcare applies to what is left. The 90.5% is not a measured displacement of paid care: IFS BN189 (pp. 11-12) finds 570 more funded hours raised subsidisable care by 163 hours and all care outside the immediate family by 54, and 1 − 54/570 counts every displaced hour of non-family care, paid or unpaid, as paid. 1 − 163/570 (71.4%), where only subsidisable care already being bought is displaced, is the lower end; 100% is the upper. Varied alone at central elasticities (`intensive_displacement`), the 2029-30 hours offset is £0.031bn at 71.4% and £0.034bn at 100%, against £0.033bn. The model recomputes tax and benefits on the extra earnings. It is a total-hours estimate (mothers, with zeros for non-workers), so it overlaps with the extensive margin.

**Range.** Low and high scale every elasticity by 1/3 and 2. The range is illustrative, not a sourced uncertainty interval: the factors are the ratios of childcare-price elasticities of maternal *employment* of −0.05 and −0.30 to a central −0.15 (a reading of Akgündüz and Plantenga's meta-analysis for the UK, whose Table 1 gives UK responses of −0.09 for single and −0.138 for married mothers), a different outcome from the OBR participation elasticities and the hours assumption they scale. The dynamic range below should not be read as a confidence interval.

| £bn a year, positive = money back | 2026-27 | 2027-28 | 2028-29 | 2029-30 |
|---|---|---|---|---|
| Moving into work, central (low to high) | -0.005 (-0.002 to -0.010) | -0.005 (-0.002 to -0.010) | -0.005 (-0.002 to -0.011) | -0.005 (-0.002 to -0.010) |
| Hours, everyone whose childcare gets cheaper, central (low to high) | 0.201 (0.067 to 0.400) | 0.212 (0.071 to 0.423) | 0.234 (0.078 to 0.466) | 0.240 (0.080 to 0.481) |
| of which the parent over £100,000 | 0.173 (0.058 to 0.346) | 0.183 (0.061 to 0.364) | 0.202 (0.068 to 0.404) | 0.208 (0.069 to 0.415) |
| Bunching, CenTax (their high-cost to low-cost scenario) | 0.150 (0.100 to 0.630) | 0.150 (0.100 to 0.630) | 0.180 (0.110 to 0.700) | 0.210 (0.120 to 0.770) |
| **Dynamic cost**, central (low to high setting) | 0.212 (0.393 to -0.462) | 0.236 (0.424 to -0.450) | 0.242 (0.465 to -0.504) | 0.233 (0.480 to -0.563) |
| Entrants, central | 1,100 | 1,100 | 1,100 | 1,100 |

**Why so few move into work.** In 2029-30 about 1.28 million adults respond, 1.18 million of them in work and 99,000 not. The reform raises a worker's gain to work by about 3% on average and a non-worker's by about 13%. The OBR elasticities with respect to in-work income (about 0.16 for the workers, 0.38 for the non-workers) fall to about 0.03 with respect to the gain to work, because the gain to work is small next to the household's in-work income (G / I averages about 0.44 for workers and 0.09 for non-workers, whose partner earns over £100,000). Applied to the employed share, that gives about 1,100 entrants, about 200 of them implied by workers over £100,000. And they cost money rather than bringing it back: the tax and National Insurance on 18.8 hours is outweighed by the 30 hours and Tax-Free Childcare their family now receives (about £4,800 each, net), so the extensive offset is −£0.005bn. Nobody already in work has a lower gain to work under the reform now that the universal hours are kept, so there are no leavers.

**Bunching (outside the model).** Parents who today keep their income at or just below £100,000 and would earn more without the limit cannot be seen in the survey data, so their response is added from CenTax (Table 4.2, intensive-margin behavioural gain, free hours only): £0.15bn in 2027-28 and £0.21bn in 2029-30 central, from their high-cost scenario (£0.10bn, £0.12bn) to their low-cost one (£0.63bn, £0.77bn), which the low and high settings use. 2028-29 is the midpoint and 2026-27, which CenTax do not cost, is held at the 2027-28 figure. It may overlap a little with the hours response of parents near the limit. With all three responses at the high setting the reform raises money; that end combines doubled elasticities with CenTax's largest bunching estimate and is illustrative.

**Against CenTax.** CenTax (Table 4.2, 2030 = 2029-30, free hours only) find +£130m from partners entering work and +£210m from parents no longer keeping income below £100,000. Our extensive margin covers both schemes and brings back −£0.005bn: CenTax's partner response implies far more entrants than the OBR's elasticities give for second earners in high-income households, and it is not clear that CenTax net off the childcare support entrants' families then receive. Their £210m has no counterpart here. Neither figure is a target.

The household calculator and the breakdowns by income, family type and region are static.

## Take-up

Take-up holds Microcosm's existing `would_claim_extended_childcare` and `would_claim_tfc` draws fixed; it is not modelled afresh for newly eligible families. The draw rates differ by income; `assumptions` in the results gives each rate overall and where a parent is over £100,000. A Tax-Free Childcare top-up also needs recorded childcare spending.

## Baseline validation

`baseline_validation` sets the unreformed model against HMRC's income tax liabilities statistics (people with income of £100,000 or more: 1.950m in 2025-26, 2.063m in 2026-27, July 2026 Table 2.5), HMRC's Tax-Free Childcare statistics (June 2026: £599.8m of top-ups to 868k families in 2025-26), DfE's January 2026 early years census and DfE's 2026-27 early years funding technical note (£9.9bn on the free entitlements). On the certified release:

- people with income of £100,000 or more: 1.885m in 2025-26 against HMRC's 1.950m, and 2.037m in 2026-27 against 2.063m;
- Tax-Free Childcare: £0.605bn of top-ups against £0.600bn, 870k families against 868k, 1,161k children against 1,152k;
- working-parent entitlement: 422k under-3s against DfE's 502k (the model cannot include 9-11-month-olds), and 352k 3- and 4-year-olds against 389k (a 3- or 4-year-old counts once its family's drawn hours go beyond the universal 15; row 8 pulls the other way);
- free-entitlements spending in 2026-27: £6.04bn in the central run and £10.0bn with full 30-hour use, against DfE's £9.9bn.

## The £0.7bn benchmark

The Conservatives put the cost at about £700m a year when they announced the pledge (PA: "The Conservatives estimate the policy would cost £700 million a year"; BBC), funded by cutting staff at arm's-length public bodies (about £1.6bn by the end of the decade). The party's web announcement covers both the free hours and Tax-Free Childcare ("abolish the £100,000 childcare cliff edge for both free childcare hours and Tax-Free Childcare") and gives no figure or method. City AM says the costing "is based on a recent report by the Centre for the Analysis of Taxation" and that removing the Tax-Free Childcare limit as well "pushed up the costs slightly". CenTax label tax years by their later year (report p.2), so their "2030" is 2029-30, the year we compare. CenTax's report ([*Removing the childcare cliff-edge: impacts and cost of reform*](https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf), September 2026, Table 4.2) covers the **free childcare hours only**: a **static** cost of £980m in 2030, and a **net** cost of £640m after £340m of extra revenue: £210m of tax from parents who no longer keep their income below £100,000 (the intensive margin) and £130m of tax and National Insurance from partners who enter work (the extensive margin; Table 4.2 and the sentence after it). It does not cover Tax-Free Childcare.

The like-for-like comparison is therefore **our 30-hours leg against CenTax's static £0.98bn** (both static, both the free hours only). Our 30-hours leg is £0.51bn in 2029-30, about half CenTax's static £0.98bn; with full 30-hour usage it rises to roughly £1.2bn. Free-hours usage is one difference: the central run draws a mean of about 15 extended hours a week, and full 30-hour usage alone takes our leg past CenTax's figure. But we have not decomposed the gap between the two studies for the newly eligible families: take-up, the income distribution above £100,000, the treatment of under-1s, expected against realised income and the funding rates differ too, so how much of the £0.47bn gap each explains is not known. The £0.7bn is therefore close to CenTax's net free-hours figure, £0.64bn, plus a small Tax-Free Childcare addition. Our total covers both schemes on the same static basis as our 30-hours leg.

## Cliff example

One illustrative family, computed with policyengine.py's `calculate_household()` for 2027-28: a couple in the South East with children aged 2 and 3, £20,000 a year of their own childcare spending, one parent on £40,000. Household net income after that spending is £101,619 when the other parent earns £99,000, £102,199 at exactly £100,000 (which still qualifies, as in law; policyengine-uk's own strict `<` gave £88,331, corrected), and £84,331 at £100,001; with the limits removed it is £102,200 at £100,001, a cliff of about £17,900.

## Reproduce

```bash
uv venv && uv pip install -e ".[dev]"
export HF_TOKEN=...                   # read access to policyengine/populace-uk-private
.venv/bin/childcare-100k-build        # downloads and verifies the release, runs the population jobs, writes data/results.json
.venv/bin/pytest
```

`--aggregate-only` rebuilds the results file from cached runs, and refuses any cached run whose provenance key does not match.
