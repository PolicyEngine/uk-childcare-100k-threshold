/**
 * Readers for results.json (the schema is in dashboard/README.md).
 *
 * Every figure the dashboard shows is read from the results file. Each reader validates the block it returns and
 * gives back `null` when any field is missing or invalid, so the component renders "unavailable" instead of "NaN",
 * "£bn" or a blank.
 */

export const UNAVAILABLE = "unavailable";
export const SCHEMES = ["thirty_hours", "tax_free_childcare"];
export const SCHEME_LABELS = {
  thirty_hours: "30 hours for working parents",
  tax_free_childcare: "Tax-Free Childcare",
};
export const COUNTRIES = ["England", "Scotland", "Wales", "Northern Ireland"];

export function isNum(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function isText(value) {
  return typeof value === "string" && value.trim().length > 0;
}

/** Fiscal year named by start year: 2027 -> "2027-28". */
export function fyLabel(year) {
  if (!Number.isInteger(year)) return UNAVAILABLE;
  return `${year}-${String((year + 1) % 100).padStart(2, "0")}`;
}

/** True only for an explicit `"meta": {"sample": true}`. */
export function isSample(data) {
  return data?.meta?.sample === true;
}

/** The modelled years as increasing integers, or null. */
export function getYears(data) {
  const years = data?.meta?.years;
  if (!Array.isArray(years) || years.length === 0 || !years.every(Number.isInteger)) return null;
  for (let i = 1; i < years.length; i += 1) if (years[i] <= years[i - 1]) return null;
  return years;
}

export function getFinalYear(data) {
  return getYears(data)?.at(-1) ?? null;
}

/** Values of an object keyed by year ("2026": n) in the order of `years`, or null if any is not a number. */
export function byYear(obj, years) {
  if (!obj || typeof obj !== "object" || !years) return null;
  const out = years.map((y) => obj[String(y)]);
  return out.every(isNum) ? out : null;
}

const META_TEXT = ["policyengine", "policyengine_uk", "dataset", "dataset_revision", "cross_check_dataset", "generated_at", "git_revision"];

/** Data and model versions, or null. */
export function getMeta(data) {
  const m = data?.meta;
  if (!m || !getYears(data) || META_TEXT.some((k) => !isText(m[k]))) return null;
  return m;
}

/** The reform's title, description and changed parameters, or null. */
export function getReform(data) {
  const r = data?.reform;
  if (!r || !isText(r.title) || !isText(r.description) || !Array.isArray(r.parameters) || r.parameters.length === 0) return null;
  if (!r.parameters.every((p) => isText(p?.name) && isNum(p.baseline) && p.reform === "removed")) return null;
  return r;
}

/** The gross cost by scheme and in total, each year (£bn, positive = extra spending), or null. */
export function getBudget(data) {
  const years = getYears(data);
  const g = data?.budget?.gross_bn;
  const thirty = byYear(g?.thirty_hours, years);
  const tfc = byYear(g?.tax_free_childcare, years);
  const total = byYear(g?.total, years);
  if (!thirty || !tfc || !total) return null;
  // The two schemes must add up to the total (to rounding), or the split shown would not match the headline.
  if (total.some((t, i) => Math.abs(thirty[i] + tfc[i] - t) > 0.02)) return null;
  return {
    years,
    rows: years.map((year, i) => ({ year, label: fyLabel(year), thirty_hours: thirty[i], tax_free_childcare: tfc[i], total: total[i] })),
  };
}

/** The Enhanced FRS low-central-high range by year, or null. The central must be the headline total. */
export function getRange(data) {
  const years = getYears(data);
  const r = data?.budget?.range_bn;
  const low = byYear(r?.low, years);
  const central = byYear(r?.central, years);
  const high = byYear(r?.high, years);
  const total = byYear(data?.budget?.gross_bn?.total, years);
  if (!low || !central || !high || !total) return null;
  if (years.some((_, i) => !(low[i] <= central[i] && central[i] <= high[i]) || Math.abs(central[i] - total[i]) > 0.001)) return null;
  return { years, low, central, high };
}

/** The sensitivity runs: each effect (£bn by year), its description, and whether it builds the low or high end. */
export function getSensitivities(data) {
  const years = getYears(data);
  const s = data?.budget?.sensitivities;
  if (!s || !s.effects_bn || typeof s.effects_bn !== "object") return null;
  // Each side must be a list of effect ids; any other shape makes the block unavailable.
  const ids = (v) => v === undefined || (Array.isArray(v) && v.every(isText));
  if (!ids(s.low) || !ids(s.high)) return null;
  const side = (id) => (s.low?.includes(id) ? "low" : s.high?.includes(id) ? "high" : null);
  const rows = Object.entries(s.effects_bn).map(([id, v]) => ({
    id,
    values: byYear(v, years),
    description: s.descriptions?.[id],
    side: side(id),
  }));
  if (rows.length === 0 || rows.some((r) => !r.values || !isText(r.description) || !r.side)) return null;
  return { years, rows };
}

/** The Microcosm cross-check: total and scheme split by year, or null. */
export function getCrossCheck(data) {
  const years = getYears(data);
  const c = data?.budget?.cross_check;
  const total = byYear(c?.total, years);
  const thirty = byYear(c?.thirty_hours, years);
  const tfc = byYear(c?.tax_free_childcare, years);
  if (!total || !thirty || !tfc) return null;
  return { years, total, thirty_hours: thirty, tax_free_childcare: tfc };
}

/** The 30 hours cost split into the extended hours gained and the universal hours the model switches off. */
export function getThirtyHoursComponents(data) {
  const years = getYears(data);
  const c = data?.budget?.thirty_hours_components_bn;
  const extended = byYear(c?.extended, years);
  const universal = byYear(c?.universal, years);
  const targeted = byYear(c?.targeted, years);
  if (!extended || !universal || !targeted) return null;
  return { years, extended, universal, targeted };
}

/** The other comparisons; each is null on its own when missing. */
export function getBudgetComparisons(data) {
  const years = getYears(data);
  const b = data?.budget;
  return {
    net: byYear(b?.net_bn?.total, years),
    thirtyOnly: byYear(b?.variants?.thirty_hours_only, years),
    tfcOnly: byYear(b?.variants?.tfc_only, years),
  };
}

function validRecipients(r) {
  return (
    r &&
    [r.families_gaining, r.children_gaining, r.mean_gain_gbp, r.by_scheme?.thirty_hours, r.by_scheme?.tax_free_childcare].every(isNum)
  );
}

/** Families and children gaining in one year (Enhanced FRS), or null. */
export function getRecipients(data, year) {
  const r = data?.recipients?.[String(year)];
  return validRecipients(r) ? r : null;
}

/** The Microcosm recipients in one year, or null. */
export function getRecipientsCrossCheck(data, year) {
  const r = data?.recipients_cross_check?.[String(year)];
  return validRecipients(r) ? r : null;
}

export const AGE_GROUPS = [
  { id: "0-1", label: "Under 2" },
  { id: "2", label: "2" },
  { id: "3-4", label: "3 and 4" },
  { id: "5-11", label: "5 to 11" },
  { id: "12+", label: "12 and over" },
];

/** Children gaining by age group, or null. */
export function getChildrenByAge(data, year) {
  const a = data?.recipients?.[String(year)]?.children_gaining_by_age;
  if (!a) return null;
  const rows = AGE_GROUPS.map((g) => ({ ...g, value: a[g.id] }));
  return rows.every((r) => isNum(r.value)) ? rows : null;
}

/**
 * A breakdown cell: valid if it has every number, or if it is marked suppressed (too few records) with no numbers.
 * A suppressed cell must never be read as zero.
 */
function validCell(r, keys) {
  if (r?.suppressed === true) return keys.every((k) => r[k] === null || r[k] === undefined);
  return keys.every((k) => isNum(r?.[k]));
}

const DECILE_KEYS = ["mean_change_gbp", "pct_change", "share_gaining_pct"];

/** Ten income deciles in order; a suppressed decile carries `suppressed: true` and null values. Or null. */
export function getDeciles(data, year) {
  const rows = data?.distribution?.[String(year)]?.by_decile;
  if (!Array.isArray(rows) || rows.length !== 10) return null;
  const ok = rows.every((r, i) => r?.decile === i + 1 && validCell(r, DECILE_KEYS));
  if (!ok || rows.every((r) => r.suppressed === true)) return null;
  return rows.map((r) => ({ ...r, suppressed: r.suppressed === true }));
}

/** The change by nation; a suppressed nation carries `suppressed: true` and null values. Or null. */
export function getCountries(data, year) {
  const rows = data?.distribution?.[String(year)]?.by_country;
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const ok = rows.every((r) => isText(r?.country) && validCell(r, ["total_change_bn", "families_gaining"]));
  return ok ? rows.map((r) => ({ ...r, suppressed: r.suppressed === true })) : null;
}

/** The years with valid recipients and distribution, for the "Who gains" year choice. */
export function getDistributionYears(data) {
  const years = getYears(data) ?? [];
  return years.filter((y) => getRecipients(data, y) && getDeciles(data, y) && getCountries(data, y));
}

/** Rows comparing the model's baseline with official statistics, each with the dataset it comes from, or null. */
export function getValidation(data) {
  const rows = data?.baseline_validation;
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const ok = rows.every(
    (r) =>
      isText(r?.label) && Number.isInteger(r.year) && isNum(r.model) && isNum(r.official) && isText(r.unit) && isText(r.source) && isText(r.url) &&
      (r.dataset === undefined || isText(r.dataset)) && (r.note === undefined || isText(r.note)),
  );
  return ok ? rows.map((r) => ({ ...r, dataset: r.dataset ?? "Model" })) : null;
}

/** Take-up and usage assumptions for each dataset, or null. */
export function getAssumptions(data) {
  const a = data?.assumptions;
  if (!a || typeof a !== "object") return null;
  const rows = Object.entries(a).map(([id, v]) => ({ id, ...v }));
  const ok =
    rows.length > 0 &&
    rows.every(
      (r) =>
        Number.isInteger(r.year) &&
        [
          r.would_claim_30_hours_pct?.families_with_child_under_5,
          r.would_claim_30_hours_pct?.of_which_parent_over_100k,
          r.would_claim_tfc_pct?.families_with_child_under_12,
          r.would_claim_tfc_pct?.of_which_parent_over_100k,
          r.mean_extended_hours_usage,
        ].every(isNum),
    );
  return ok ? rows : null;
}

/** The example household's net income against earnings, with and without the limit, or null. */
export function getCliff(data) {
  const c = data?.cliff_example;
  if (!c || !isText(c.description) || !Number.isInteger(c.year)) return null;
  const { earnings, net_income_baseline: base, net_income_reform: reform } = c;
  if (![earnings, base, reform].every((a) => Array.isArray(a) && a.length >= 2 && a.every(isNum))) return null;
  if (base.length !== earnings.length || reform.length !== earnings.length) return null;
  for (let i = 1; i < earnings.length; i += 1) if (earnings[i] <= earnings[i - 1]) return null;
  const rows = earnings.map((e, i) => ({ earnings: e, baseline: base[i], reform: reform[i] }));
  return { ...c, rows, notes: isText(c.notes) ? c.notes : null };
}

/**
 * The cliff in the example: income just below the limit (the last point under it), the first point above it, the
 * income lost between them, and the earnings needed to get back to the income below the limit (null if never within
 * the range). Measured from below the limit because the model may already withdraw support at exactly £100,000.
 */
export function cliffSummary(cliff, limit = 100000) {
  const rows = cliff?.rows;
  if (!rows) return null;
  const below = rows.findLastIndex((r) => r.earnings < limit);
  const above = rows.findIndex((r) => r.earnings > limit);
  if (below < 0 || above < 0) return null;
  const before = rows[below];
  const after = rows[above];
  const recover = rows.slice(above).find((r) => r.baseline >= before.baseline);
  return { before, after, drop: before.baseline - after.baseline, recoverAt: recover?.earnings ?? null };
}

/** Published estimates to compare against, or null. */
export function getBenchmarks(data) {
  const rows = data?.benchmarks;
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const ok = rows.every(
    (b) =>
      isText(b?.source) && isText(b.figure) && isNum(b.ours) && Number.isInteger(b.year) && isText(b.like_for_like) && isText(b.url) &&
      (b.announcement_url === undefined || isText(b.announcement_url)),
  );
  return ok ? rows : null;
}

export function getLimitations(data) {
  const rows = data?.limitations;
  return Array.isArray(rows) && rows.length > 0 && rows.every(isText) ? rows : null;
}
