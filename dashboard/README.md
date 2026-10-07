# Dashboard

Next.js app for "Removing the £100,000 childcare limit", served under the PolicyEngine multizone at
`/uk/childcare-100k-threshold` (set once in `src/lib/basePath.json`, read by `next.config.mjs` and the components).

```sh
bun install
bun run dev     # http://localhost:3000/uk/childcare-100k-threshold
bun run lint
bun run test
bun run validate   # validate public/data/results.json (also runs before every build)
bun run build
```

## Data

The page reads one file, `public/data/results.json`, bundled at build time. The analysis pipeline writes
`data/results.json` at the repo root; copy it in after each run and commit both:

```sh
bun run data    # cp ../data/results.json public/data/results.json, then validate it
```

The analysis runs on Microcosm UK 2024-25 (the certified national release) through policyengine.py; there is one
dataset and no cross-check.

The tests read their expected numbers from the same file, so they pass on any valid results file. Every block is
validated by a reader in `src/lib/dataHelpers.js`, which throws a `ResultsError` naming the block when anything is
missing or invalid. There is no fallback: `scripts/validate-results.mjs` runs every reader before each build
(`prebuild`), so an invalid file fails the build rather than reaching the page, and the formatters throw rather
than print a placeholder. Vercel builds with bun (`vercel.json`) so the prebuild step runs there too.

The page leads with 2027-28 (`LEAD_YEAR`); 2026-27 is more than half over, so tables label it illustrative.

### Schema

Costs are positive £bn of extra government spending. Year keys are fiscal-year start years as strings
(`"2026"` = 2026-27).

```
meta                 policyengine, policyengine_uk, dataset, dataset_revision, years [2026, ...] (must include
                     2027), generated_at, git_revision; shown when present: dataset_repo, dataset_sha256,
                     dataset_management
reform               title, description, parameters [{name, baseline, reform: "removed"}]
budget               gross_bn {thirty_hours, tax_free_childcare, total}       each {"2026": n, ...}
                     net_bn {total}, variants {thirty_hours_only, tfc_only}
                     thirty_hours_components_bn {extended, universal, targeted}
                     range_bn {low, central, high}                            central = gross_bn.total
                     sensitivities {effects_bn {id: {...}}, low [ids], high [ids], descriptions {id: str}}
recipients           {"2029": {families_gaining, children_gaining, by_scheme, children_by_scheme,
                     children_gaining_by_age {"0-1", "2", "3-4", "5-11", "12+"}, mean_gain_gbp, families_losing}}
                     mean_gain_gbp is null only when suppressed (families_gaining 0, or suppressed: true)
distribution         {"2029": {by_decile [{decile, mean_change_gbp, pct_change, share_gaining_pct, suppressed}],
                     by_country [{country, total_change_bn, families_gaining, suppressed}]}}
assumptions          {microcosm: {year, would_claim_30_hours_pct {...}, would_claim_tfc_pct {...},
                     mean_extended_hours_usage}}
baseline_validation  [{label, year, model, official, unit, source, url, dataset?, note?}]
cliff_example        description, year, earnings [...], net_income_baseline [...], net_income_reform [...], notes
benchmarks           [{source, figure, ours, year, like_for_like, url, announcement_url, underlying_source_url}]
limitations          [str]
```

A suppressed cell (fewer than ten gaining records) has `suppressed: true` and `null` values; the page shows it as
"too few records", never as zero. A `null` without `suppressed: true` fails validation, and so does a single
suppressed nation (it could be worked out from the UK total).

`pct_change` and `share_gaining_pct` are percentages (0.16 means 0.16%), not fractions. `gross_bn.thirty_hours`
plus `gross_bn.tax_free_childcare` must equal `gross_bn.total` to within £0.02bn (rounding), or validation fails.
`baseline_validation[].unit` is `"£bn"`, `"£m"`, `"£"`, `"£/hour"`, `"%"` or a count noun such as `"children"`.
