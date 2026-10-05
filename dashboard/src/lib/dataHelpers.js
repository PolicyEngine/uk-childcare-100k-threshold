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

/** The comparisons around the main costing; each is null on its own when missing. */
export function getBudgetComparisons(data) {
  const years = getYears(data);
  const b = data?.budget;
  return {
    net: byYear(b?.net_bn?.total, years),
    thirtyOnly: byYear(b?.variants?.thirty_hours_only, years),
    tfcOnly: byYear(b?.variants?.tfc_only, years),
    crossCheck: byYear(b?.cross_check?.total, years),
  };
}

function validRecipients(r) {
  return (
    r &&
    [r.families_gaining, r.children_gaining, r.mean_gain_gbp, r.by_scheme?.thirty_hours, r.by_scheme?.tax_free_childcare].every(isNum)
  );
}

/** Families and children gaining in one year, or null. */
export function getRecipients(data, year) {
  const r = data?.recipients?.[String(year)];
  return validRecipients(r) ? r : null;
}

/** Ten income deciles with the mean change, % change and share gaining, in decile order, or null. */
export function getDeciles(data, year) {
  const rows = data?.distribution?.[String(year)]?.by_decile;
  if (!Array.isArray(rows) || rows.length !== 10) return null;
  const ok = rows.every(
    (r, i) => r?.decile === i + 1 && isNum(r.mean_change_gbp) && isNum(r.pct_change) && isNum(r.share_gaining_pct),
  );
  return ok ? rows : null;
}

/** The change by nation, or null. */
export function getCountries(data, year) {
  const rows = data?.distribution?.[String(year)]?.by_country;
  if (!Array.isArray(rows) || rows.length === 0) return null;
  return rows.every((r) => isText(r?.country) && isNum(r.total_change_bn) && isNum(r.families_gaining)) ? rows : null;
}

/** The years with valid recipients and distribution, for the "Who gains" year choice. */
export function getDistributionYears(data) {
  const years = getYears(data) ?? [];
  return years.filter((y) => getRecipients(data, y) && getDeciles(data, y) && getCountries(data, y));
}

/** Rows comparing the model's baseline with official statistics, or null. */
export function getValidation(data) {
  const rows = data?.baseline_validation;
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const ok = rows.every(
    (r) => isText(r?.label) && Number.isInteger(r.year) && isNum(r.model) && isNum(r.official) && isText(r.unit) && isText(r.source) && isText(r.url),
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
 * Where the example household falls off the cliff: the last point at or below £100,000, the first above it, the
 * income lost there, and the earnings needed to get back to the income at the limit (null if never within range).
 */
export function cliffSummary(cliff, limit = 100000) {
  const rows = cliff?.rows;
  if (!rows) return null;
  const at = rows.findLastIndex((r) => r.earnings <= limit);
  if (at < 0 || at === rows.length - 1) return null;
  const before = rows[at];
  const after = rows[at + 1];
  const recover = rows.slice(at + 1).find((r) => r.baseline >= before.baseline);
  return { before, after, drop: before.baseline - after.baseline, recoverAt: recover?.earnings ?? null };
}

/** Published estimates to compare against, or null. */
export function getBenchmarks(data) {
  const rows = data?.benchmarks;
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const ok = rows.every(
    (b) => isText(b?.source) && isText(b.figure) && isNum(b.ours) && Number.isInteger(b.year) && isText(b.like_for_like) && isText(b.url),
  );
  return ok ? rows : null;
}

export function getLimitations(data) {
  const rows = data?.limitations;
  return Array.isArray(rows) && rows.length > 0 && rows.every(isText) ? rows : null;
}
