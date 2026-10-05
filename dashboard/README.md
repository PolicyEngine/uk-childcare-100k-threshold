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

Until real results exist, `public/data/results.json` is a **sample fixture** with placeholder numbers and
`"meta": {"sample": true}`. While that flag is set, every tab shows a "Sample data — not results" banner. The
pipeline's output omits the flag, so the banner disappears when the real file is copied in.

The tests read their expected numbers from the same file, so they pass on the fixture and on the real results.
Every block is validated by a reader in `src/lib/dataHelpers.js`; a missing or invalid block renders
"unavailable" on its own rather than breaking the page.

### Schema

Costs are positive £bn of extra government spending. Year keys are fiscal-year start years as strings
(`"2026"` = 2026-27).

```
meta               policyengine, policyengine_uk, dataset, dataset_revision, cross_check_dataset,
                   years [2026, ...], generated_at, git_revision, sample (optional)
reform             title, description, parameters [{name, baseline, reform: "removed"}]
budget             gross_bn {thirty_hours, tax_free_childcare, total}   each {"2026": n, ...}
                   net_bn {total}, variants {thirty_hours_only, tfc_only}, cross_check {total}
recipients         {"2029": {families_gaining, children_gaining, by_scheme {thirty_hours, tax_free_childcare},
                   mean_gain_gbp}, ...}
distribution       {"2029": {by_decile [{decile 1-10, mean_change_gbp, pct_change, share_gaining_pct}],
                   by_country [{country, total_change_bn, families_gaining}]}, ...}
baseline_validation [{label, year, model, official, unit, source, url}]
cliff_example      description, year, earnings [...], net_income_baseline [...], net_income_reform [...], notes
benchmarks         [{source, figure, ours, year, like_for_like, url}]
limitations        [str]
```

`pct_change` and `share_gaining_pct` are percentages (0.16 means 0.16%), not fractions. `gross_bn.thirty_hours`
plus `gross_bn.tax_free_childcare` must equal `gross_bn.total` to within £0.01bn, or the budget tab fails closed.
`baseline_validation[].unit` is `"£bn"`, `"£m"`, `"£"`, `"%"` or a count noun such as `"children"`.
