# `data/results.json` schema

Written by `childcare-100k-build` (`src/childcare_100k/cli.py`). Year keys are strings naming the fiscal year by its start (`"2026"` = 2026-27). Keys marked *extra* are additions to the schema the dashboard was built against; everything else is the agreed schema, unchanged.

## Conventions

- **Sign:** costs are positive £bn = extra government spending (or lower receipts). A negative cost would be a saving.
- **Units:** `_bn` = £ billion, 3 dp. `_gbp` = £ a year. `pct_change` and `share_gaining_pct` are **percentages** (0.16 means 0.16%), not fractions.
- **Counts** (families, children) are weighted population estimates rounded to the nearest 1,000.
- **Families** are benefit units (one adult or a couple and their dependent children). Households can hold more than one.
- **Suppression:** a breakdown cell (decile, country) that rests on 1-9 gaining records, or on 1-9 records whose value changes at all (gaining or losing), is published as `null` with `"suppressed": true`. If that leaves a single suppressed cell in a breakdown, the smallest other cell with a nonzero change is suppressed too (complementary suppression), so no suppressed cell equals a published total less the published cells. Record counts are never published.

Every block except `budget.cross_check`, `recipients_cross_check` and the Microcosm rows of `baseline_validation` comes from the **Enhanced FRS** (the headline dataset; METHOD.md says why). Microcosm is the cross-check.

## Blocks

| Key | Contents |
|---|---|
| `meta` | `policyengine`, `policyengine_uk` (versions run), `dataset` (`enhanced_frs_2024_25`, the headline), `dataset_revision` (bundle revision of that file), `cross_check_dataset` (`populace_uk_2023`, Microcosm), `years`, `generated_at` (UTC), `git_revision` (commit the build ran on, so the commit *before* the one that adds the file). *Extra:* `dataset_sha256`, `cross_check_dataset_revision`, `min_cell_size`, `run_seconds` and `peak_rss_gb` per `dataset/scenario` job. |
| `reform` | `title`, `description`, `parameters`: the two policyengine-uk parameters, baseline £100,000, reform `"removed"` (set to infinity from 2026-27). |
| `budget.gross_bn` | `thirty_hours`: change in spending on all three funded-hours entitlements (extended, universal, targeted; the universal 15 hours switch off when a family becomes eligible for the extended hours, so the change in extended spending alone would double count). `tax_free_childcare`: change in TFC top-ups. `total` = the sum (the dashboard checks this to within £0.02bn). Enhanced FRS, central assumptions. |
| `budget.net_bn.total` | Change in the government balance (minus `gov_balance` change): gross plus any knock-on change in other taxes and benefits. Equal to gross here: nothing else in the model depends on these limits. |
| `budget.thirty_hours_components_bn` *extra* | The `thirty_hours` leg split into `extended`, `universal` and `targeted` (£bn by year; they sum to `thirty_hours`). `universal` is negative: it is the 3- and 4-year-olds' universal 15 hours switched off as their families move onto the extended entitlement. |
| `budget.variants` | `thirty_hours_only`, `tfc_only`: gross total if only one limit is removed. They add to `total` because neither scheme's calculation references the other's. |
| `budget.cross_check` | The same on Microcosm: `total`; *extra* `thirty_hours`, `tax_free_childcare`, `net_total`, `thirty_hours_components_bn`, `variants`, `range_bn`, `effects_bn`. |
| `budget.range_bn` *extra* | `low`, `central` (= `gross_bn.total`), `high`, by year. |
| `budget.sensitivities` *extra* | `effects_bn`: each adjustment's effect on the gross total by year (+ raises the cost); `low` / `high`: which effects make up each end; `descriptions`. Effects: `full_30_hour_usage` (+), `under_ones` (+), `ani_net_of_pension_contributions` (-), `tfc_routed_share` (-). The ends add the effects, ignoring interactions. |
| `recipients[year]` | `families_gaining` (gain > £1 a year), `children_gaining` (children in gaining families newly receiving the 30 hours or a TFC top-up), `by_scheme` (**families** gaining from each scheme; a family can gain from both), `mean_gain_gbp` (mean gain per gaining family). *Extra:* `children_by_scheme`, `children_gaining_by_age` (bands `0-1`, `2`, `3-4`, `5-11`, `12+`), `families_losing` (a model artefact: see METHOD.md). |
| `recipients_cross_check` *extra* | The headline recipient numbers on Microcosm. |
| `distribution[year]` | `by_decile`: households by baseline equivalised household net income decile (people-weighted, as policyengine-uk's `household_income_decile`; households with negative income excluded), with `mean_change_gbp` (mean over all households in the decile), `pct_change` (change in decile total net income as a % of its baseline total; net income includes the value of funded hours), `share_gaining_pct`, *extra* `suppressed`. `by_country`: `total_change_bn`, `families_gaining`, *extra* `suppressed`. |
| `baseline_validation` | Rows `label`, `year` (fiscal year of the model figure), `model`, `official`, `unit`, `source`, `url`; *extra* `dataset` (which dataset the model figure comes from, or `parameters`) and `note`. |
| `assumptions` *extra* | Per dataset: the model's take-up draws (share of families with `would_claim_*` true, overall and where a parent is over £100,000) and mean extended hours used. |
| `cliff_example` | `description`, `year` (2027), `earnings` (one parent's employment income, with £100,001 added next to £100,000), `net_income_baseline`, `net_income_reform` (household net income minus the family's own fixed childcare spending), `notes`. *Extra:* `components` (funded-hours value, TFC top-up, income tax, each baseline and reform). |
| `benchmarks` | `source`, `figure`, `ours` (our `gross_bn.total` for `year`), `year`, `like_for_like`, `url`; *extra* `announcement_url`, `underlying_source` and `underlying_source_url` (the study the reported figure is based on), `difference_bn` (ours minus theirs; the figures are not like for like, see `like_for_like`). |
| `limitations` | Strings. |
