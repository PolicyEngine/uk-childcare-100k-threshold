# Dashboard

Next.js app for "Removing the £100,000 childcare limit", served under the PolicyEngine multizone at
`/uk/childcare-100k-threshold` (see `next.config.js`).

```sh
bun install
bun run dev     # http://localhost:3000/uk/childcare-100k-threshold
bun run lint
bun run test
bun run build
```

## Data

The page reads one file, `public/data/results.json`, bundled at build time. The analysis pipeline writes
`data/results.json` at the repo root; copy it in after each run and commit both:

```sh
bun run data    # cp ../data/results.json public/data/results.json
```

The committed file is the real output of the analysis (Enhanced FRS headline, Microcosm cross-check). If a file
carries `"meta": {"sample": true}`, every tab shows a "Sample data — not results" banner.

The tests read their expected numbers from the same file, so they pass on any valid results file.
Every block is validated by a reader in `src/lib/dataHelpers.js`; a missing or invalid block renders
"unavailable" on its own rather than breaking the page.

### Schema

Costs are positive £bn of extra government spending. Year keys are fiscal-year start years as strings
(`"2026"` = 2026-27).

```
meta                 policyengine, policyengine_uk, dataset, dataset_revision, cross_check_dataset,
                     cross_check_dataset_revision, years [2026, ...], generated_at, git_revision, sample (optional)
reform               title, description, parameters [{name, baseline, reform: "removed"}]
budget               gross_bn {thirty_hours, tax_free_childcare, total}       each {"2026": n, ...}
                     net_bn {total}, variants {thirty_hours_only, tfc_only}
                     thirty_hours_components_bn {extended, universal, targeted}
                     range_bn {low, central, high}                            central = gross_bn.total
                     sensitivities {effects_bn {id: {...}}, low [ids], high [ids], descriptions {id: str}}
                     cross_check {total, thirty_hours, tax_free_childcare, ...}   (Microcosm)
recipients           {"2029": {families_gaining, children_gaining, by_scheme, children_by_scheme,
                     children_gaining_by_age {"0-1", "2", "3-4", "5-11", "12+"}, mean_gain_gbp, families_losing}}
recipients_cross_check  {"2029": {families_gaining, children_gaining, by_scheme, mean_gain_gbp}}
distribution         {"2029": {by_decile [{decile, mean_change_gbp, pct_change, share_gaining_pct, suppressed}],
                     by_country [{country, total_change_bn, families_gaining, suppressed}]}}
assumptions          {enhanced_frs | microcosm: {year, would_claim_30_hours_pct {...}, would_claim_tfc_pct {...},
                     mean_extended_hours_usage}}
baseline_validation  [{label, year, model, official, unit, source, url, dataset, note?}]
cliff_example        description, year, earnings [...], net_income_baseline [...], net_income_reform [...], notes
benchmarks           [{source, figure, ours, year, like_for_like, url, announcement_url}]
limitations          [str]
```

A suppressed cell (fewer than ten gaining records) has `suppressed: true` and `null` values; the page shows it as
"too few records", never as zero. A `null` without `suppressed: true` fails validation.

`pct_change` and `share_gaining_pct` are percentages (0.16 means 0.16%), not fractions. `gross_bn.thirty_hours`
plus `gross_bn.tax_free_childcare` must equal `gross_bn.total` to within £0.02bn (rounding), or the budget tab fails closed.
`baseline_validation[].unit` is `"£bn"`, `"£m"`, `"£"`, `"£/hour"`, `"%"` or a count noun such as `"children"`.
