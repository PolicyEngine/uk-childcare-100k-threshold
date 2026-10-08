/**
 * Readers for results.json (the schema is in dashboard/README.md).
 *
 * Every figure the dashboard shows is read from the results file. Each reader validates the block it returns and
 * throws a ResultsError naming the block when any field is missing or invalid. There is no fallback: a bad file
 * fails `validateResults`, which runs before every build (scripts/validate-results.mjs) and in the tests, so it
 * can never reach the page.
 */

export class ResultsError extends Error {
  constructor(block, problem) {
    super(`results.json: ${block}: ${problem}`);
    this.name = "ResultsError";
    this.block = block;
  }
}

function fail(block, problem) {
  throw new ResultsError(block, problem);
}

/** The year the page leads with. 2026-27 is half over, so its full-year cost is illustrative. */
export const LEAD_YEAR = 2027;
export const ILLUSTRATIVE_YEAR = 2026;
export const SCHEMES = ["thirty_hours", "tax_free_childcare"];
export const SCHEME_LABELS = {
  thirty_hours: "30 hours for working parents",
  tax_free_childcare: "Tax-Free Childcare",
};

export function isNum(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function isText(value) {
  return typeof value === "string" && value.trim().length > 0;
}

/** Fiscal year named by start year: 2027 -> "2027-28". */
export function fyLabel(year) {
  if (!Number.isInteger(year)) fail("year", `${year} is not a year`);
  return `${year}-${String((year + 1) % 100).padStart(2, "0")}`;
}

/** The fiscal year as a table heading, marking the half-elapsed year as illustrative. */
export function yearHeading(year) {
  return year === ILLUSTRATIVE_YEAR ? `${fyLabel(year)} (illustrative)` : fyLabel(year);
}

/** The modelled years as increasing integers, including the lead year. */
export function getYears(data) {
  const years = data?.meta?.years;
  if (!Array.isArray(years) || years.length === 0 || !years.every(Number.isInteger)) fail("meta.years", "not a list of years");
  for (let i = 1; i < years.length; i += 1) if (years[i] <= years[i - 1]) fail("meta.years", "not increasing");
  if (!years.includes(LEAD_YEAR)) fail("meta.years", `does not include the lead year ${LEAD_YEAR}`);
  return years;
}

/** Values of an object keyed by year ("2026": n) in the order of `years`. */
export function byYear(obj, years, block) {
  if (!obj || typeof obj !== "object") fail(block, "missing");
  return years.map((y) => {
    const v = obj[String(y)];
    if (!isNum(v)) fail(block, `${y} is ${JSON.stringify(v)}, not a number`);
    return v;
  });
}

const META_TEXT = ["policyengine", "policyengine_uk", "dataset", "dataset_revision", "generated_at", "git_revision"];
/** Provenance shown when the file carries it (the certified-release fields). */
export const META_PROVENANCE = [
  ["dataset_repo", "Dataset repository"],
  ["dataset_sha256", "Dataset sha256"],
  ["dataset_management", "Dataset pinning"],
];

/** Data and model versions. */
export function getMeta(data) {
  const m = data?.meta;
  if (!m) fail("meta", "missing");
  getYears(data);
  for (const k of META_TEXT) if (!isText(m[k])) fail(`meta.${k}`, "missing");
  for (const [k] of META_PROVENANCE) if (k in m && !isText(m[k])) fail(`meta.${k}`, "not text");
  return m;
}

/** The reform's title, description and changed parameters. */
export function getReform(data) {
  const r = data?.reform;
  if (!r || !isText(r.title) || !isText(r.description) || !Array.isArray(r.parameters) || r.parameters.length === 0) fail("reform", "incomplete");
  if (!r.parameters.every((p) => isText(p?.name) && isNum(p.baseline) && p.reform === "removed")) fail("reform.parameters", "invalid");
  return r;
}

/** The gross cost by scheme and in total, each year (£bn, positive = extra spending). */
export function getBudget(data) {
  const years = getYears(data);
  const g = data?.budget?.gross_bn;
  const thirty = byYear(g?.thirty_hours, years, "budget.gross_bn.thirty_hours");
  const tfc = byYear(g?.tax_free_childcare, years, "budget.gross_bn.tax_free_childcare");
  const total = byYear(g?.total, years, "budget.gross_bn.total");
  // The two schemes must add up to the total (to rounding), or the split shown would not match the headline.
  years.forEach((y, i) => {
    if (Math.abs(thirty[i] + tfc[i] - total[i]) > 0.02) fail("budget.gross_bn", `${y}: schemes do not add up to the total`);
  });
  return {
    years,
    rows: years.map((year, i) => ({ year, label: fyLabel(year), thirty_hours: thirty[i], tax_free_childcare: tfc[i], total: total[i] })),
  };
}

/** The low-central-high range by year. The central must be the headline total. */
export function getRange(data) {
  const years = getYears(data);
  const r = data?.budget?.range_bn;
  const low = byYear(r?.low, years, "budget.range_bn.low");
  const central = byYear(r?.central, years, "budget.range_bn.central");
  const high = byYear(r?.high, years, "budget.range_bn.high");
  const total = byYear(data?.budget?.gross_bn?.total, years, "budget.gross_bn.total");
  years.forEach((y, i) => {
    if (!(low[i] <= central[i] && central[i] <= high[i])) fail("budget.range_bn", `${y}: low, central and high are out of order`);
    if (Math.abs(central[i] - total[i]) > 0.001) fail("budget.range_bn.central", `${y}: not the headline total`);
  });
  return { years, low, central, high };
}

/** The sensitivity runs: each effect (£bn by year), its description, and whether it builds the low or high end. */
export function getSensitivities(data) {
  const years = getYears(data);
  const s = data?.budget?.sensitivities;
  if (!s || !s.effects_bn || typeof s.effects_bn !== "object") fail("budget.sensitivities", "missing");
  // Each side must be a list of effect ids.
  for (const side of ["low", "high"]) {
    if (!Array.isArray(s[side]) || !s[side].every(isText)) fail(`budget.sensitivities.${side}`, "not a list of effect ids");
  }
  const rows = Object.entries(s.effects_bn).map(([id, v]) => {
    const side = s.low.includes(id) ? "low" : s.high.includes(id) ? "high" : fail(`budget.sensitivities.${id}`, "on neither side");
    if (!isText(s.descriptions?.[id])) fail(`budget.sensitivities.descriptions.${id}`, "missing");
    return { id, values: byYear(v, years, `budget.sensitivities.effects_bn.${id}`), description: s.descriptions[id], side };
  });
  if (rows.length === 0) fail("budget.sensitivities.effects_bn", "empty");
  for (const id of [...s.low, ...s.high]) if (!(id in s.effects_bn)) fail(`budget.sensitivities`, `${id} has no effect`);
  return { years, rows };
}

/** The 30 hours cost split by entitlement: the extended hours gained, and the universal and targeted hours (kept, so zero). */
export function getThirtyHoursComponents(data) {
  const years = getYears(data);
  const c = data?.budget?.thirty_hours_components_bn;
  return {
    years,
    extended: byYear(c?.extended, years, "budget.thirty_hours_components_bn.extended"),
    universal: byYear(c?.universal, years, "budget.thirty_hours_components_bn.universal"),
    targeted: byYear(c?.targeted, years, "budget.thirty_hours_components_bn.targeted"),
  };
}

/** The net cost and each scheme's limit removed alone. */
export function getBudgetComparisons(data) {
  const years = getYears(data);
  const b = data?.budget;
  return {
    net: byYear(b?.net_bn?.total, years, "budget.net_bn.total"),
  };
}

/** Families and children gaining in one year. */
export function getRecipients(data, year) {
  const block = `recipients.${year}`;
  const r = data?.recipients?.[String(year)];
  if (!r) fail(block, "missing");
  const keys = { families_gaining: r.families_gaining, children_gaining: r.children_gaining, "by_scheme.thirty_hours": r.by_scheme?.thirty_hours, "by_scheme.tax_free_childcare": r.by_scheme?.tax_free_childcare };
  for (const [k, v] of Object.entries(keys)) if (!isNum(v)) fail(`${block}.${k}`, "not a number");
  // The mean gain is null only when it is suppressed: nobody gains, or the cell is marked suppressed.
  if (r.mean_gain_gbp === null) {
    if (!(r.families_gaining === 0 || r.suppressed === true || r.mean_gain_suppressed === true)) fail(`${block}.mean_gain_gbp`, "null but not suppressed");
  } else if (!isNum(r.mean_gain_gbp)) fail(`${block}.mean_gain_gbp`, "not a number");
  if ("families_losing" in r && !isNum(r.families_losing)) fail(`${block}.families_losing`, "not a number");
  if ("children_by_scheme" in r && !SCHEMES.every((sc) => isNum(r.children_by_scheme?.[sc]))) fail(`${block}.children_by_scheme`, "invalid");
  return r;
}

export const AGE_GROUPS = [
  { id: "0-1", label: "Under 2" },
  { id: "2", label: "2" },
  { id: "3-4", label: "3 and 4" },
  { id: "5-11", label: "5 to 11" },
  { id: "12+", label: "12 and over" },
];

/** Children gaining by age group. */
export function getChildrenByAge(data, year) {
  const block = `recipients.${year}.children_gaining_by_age`;
  const a = data?.recipients?.[String(year)]?.children_gaining_by_age;
  if (!a) fail(block, "missing");
  return AGE_GROUPS.map((g) => {
    if (!isNum(a[g.id])) fail(`${block}.${g.id}`, "not a number");
    return { ...g, value: a[g.id] };
  });
}

/**
 * A breakdown cell: valid if it has every number, or if it is marked suppressed (too few records) with no numbers.
 * A suppressed cell must never be read as zero.
 */
function checkCell(r, keys, block) {
  if (r?.suppressed === true) {
    if (!keys.every((k) => r[k] === null || r[k] === undefined)) fail(block, "suppressed but carries a number");
    return;
  }
  for (const k of keys) if (!isNum(r?.[k])) fail(`${block}.${k}`, "not a number");
}

const DECILE_KEYS = ["mean_change_gbp", "pct_change", "share_gaining_pct"];

/** Ten income deciles in order; a suppressed decile carries `suppressed: true` and null values. */
export function getDeciles(data, year) {
  const block = `distribution.${year}.by_decile`;
  const rows = data?.distribution?.[String(year)]?.by_decile;
  if (!Array.isArray(rows) || rows.length !== 10) fail(block, "not ten deciles");
  rows.forEach((r, i) => {
    if (r?.decile !== i + 1) fail(`${block}.${i}`, "out of order");
    checkCell(r, DECILE_KEYS, `${block}.${i}`);
  });
  if (rows.every((r) => r.suppressed === true)) fail(block, "every decile suppressed");
  return rows.map((r) => ({ ...r, suppressed: r.suppressed === true }));
}

export const REGIONS = [
  "North East",
  "North West",
  "Yorkshire and the Humber",
  "East Midlands",
  "West Midlands",
  "East of England",
  "London",
  "South East",
  "South West",
  "Wales",
  "Scotland",
  "Northern Ireland",
];
export const FAMILY_TYPES = ["Lone parent", "Couple, one child", "Couple, two children", "Couple, three or more children", "Other family"];

/** The breakdowns by region and family type; each cell carries a cost and families gaining, or is suppressed. */
export const GROUPINGS = {
  region: { key: "by_region", label: "region", names: REGIONS },
  family_type: { key: "by_family_type", label: "family_type", names: FAMILY_TYPES },
};

export function getGroups(data, year, grouping) {
  const g = GROUPINGS[grouping];
  if (!g) fail(`distribution.${year}`, `unknown grouping ${JSON.stringify(grouping)}`);
  const block = `distribution.${year}.${g.key}`;
  const rows = data?.distribution?.[String(year)]?.[g.key];
  if (!Array.isArray(rows) || rows.length !== g.names.length) fail(block, "missing");
  rows.forEach((r, i) => {
    if (r?.[g.label] !== g.names[i]) fail(`${block}.${i}.${g.label}`, "out of order");
    checkCell(r, ["total_change_bn", "families_gaining"], `${block}.${i}`);
  });
  if (rows.filter((r) => r.suppressed === true).length === 1) fail(block, "a single suppressed cell can be recovered from the total");
  return rows.map((r) => ({ name: r[g.label], ...r, suppressed: r.suppressed === true }));
}

export const EARNER_GROUPS = ["Father over £100,000", "Mother over £100,000", "Both parents over £100,000", "Lone parent over £100,000"];

/** Families gaining by who is over £100,000, and how often the other parent does not work, by sex of the higher earner. */
export function getGender(data, year) {
  const block = `gender.${year}`;
  const g = data?.gender?.[String(year)];
  if (!g) fail(block, "missing");
  const rows = g.families_gaining_by_earner;
  if (!Array.isArray(rows) || rows.length !== EARNER_GROUPS.length) fail(`${block}.families_gaining_by_earner`, "missing");
  rows.forEach((r, i) => {
    if (r?.group !== EARNER_GROUPS[i]) fail(`${block}.families_gaining_by_earner.${i}.group`, "out of order");
    checkCell(r, ["families_gaining"], `${block}.families_gaining_by_earner.${i}`);
  });
  if (rows.filter((r) => r.suppressed === true).length === 1) fail(`${block}.families_gaining_by_earner`, "a single suppressed cell can be recovered from the total");
  const partner = g.partner_not_working;
  if (!Array.isArray(partner) || partner.length !== 2) fail(`${block}.partner_not_working`, "missing");
  partner.forEach((r, i) => checkCell(r, ["families", "partner_not_working_pct"], `${block}.partner_not_working.${i}`));
  return {
    byEarner: rows.map((r) => ({ name: r.group, ...r, suppressed: r.suppressed === true })),
    partner: partner.map((r) => ({ ...r, suppressed: r.suppressed === true })),
  };
}

/** The years for the "Who gains" choice: every modelled year, each of which must have a valid distribution. */
export function getDistributionYears(data) {
  const years = getYears(data);
  for (const y of years) {
    getRecipients(data, y);
    getDeciles(data, y);
    getGroups(data, y, "region");
    getGroups(data, y, "family_type");
    getGender(data, y);
  }
  return years;
}

/** Rows comparing the model's baseline with official statistics. */
export function getValidation(data) {
  const rows = data?.baseline_validation;
  if (!Array.isArray(rows) || rows.length === 0) fail("baseline_validation", "missing");
  rows.forEach((r, i) => {
    const ok =
      isText(r?.label) && Number.isInteger(r.year) && isNum(r.model) && isNum(r.official) && isText(r.unit) && isText(r.source) && isText(r.url) &&
      (!("dataset" in r) || isText(r.dataset)) && (!("note" in r) || isText(r.note));
    if (!ok) fail(`baseline_validation.${i}`, "invalid");
  });
  return rows;
}

/** Take-up and usage assumptions for each dataset in the file. */
export function getAssumptions(data) {
  const a = data?.assumptions;
  if (!a || typeof a !== "object") fail("assumptions", "missing");
  const rows = Object.entries(a).map(([id, v]) => ({ id, ...v }));
  if (rows.length === 0) fail("assumptions", "empty");
  rows.forEach((r) => {
    const ok =
      Number.isInteger(r.year) &&
      [
        r.would_claim_30_hours_pct?.families_with_child_under_5,
        r.would_claim_30_hours_pct?.of_which_parent_over_100k,
        r.would_claim_tfc_pct?.families_with_child_under_12,
        r.would_claim_tfc_pct?.of_which_parent_over_100k,
        r.mean_extended_hours_usage,
      ].every(isNum);
    if (!ok) fail(`assumptions.${r.id}`, "invalid");
  });
  return rows;
}

/** The modelling assumptions, each with what the code models and, where tested, the alternative's effect by year. */
export function getModellingAssumptions(data) {
  const rows = data?.modelling_assumptions;
  const years = getYears(data);
  if (!Array.isArray(rows) || rows.length === 0) fail("modelling_assumptions", "missing");
  rows.forEach((r, i) => {
    if (!isText(r?.id) || !isText(r.title) || !isText(r.modelled) || !isText(r.ours) || !isText(r.source_says)) fail(`modelling_assumptions.${i}`, "incomplete");
    if (!isText(r.source?.label) || !isText(r.source?.url)) fail(`modelling_assumptions.${i}.source`, "missing");
    if ("sources" in r && !(Array.isArray(r.sources) && r.sources.every((x) => isText(x?.label) && isText(x?.url)))) fail(`modelling_assumptions.${i}.sources`, "invalid");
    if ("alternative" in r || "effect_bn" in r) {
      if (!isText(r.alternative)) fail(`modelling_assumptions.${i}.alternative`, "missing");
      byYear(r.effect_bn, years, `modelling_assumptions.${i}.effect_bn`);
    }
  });
  return rows.map((r) => ("effect_bn" in r ? { ...r, effects: byYear(r.effect_bn, years, "") } : r));
}

/** The example household's net income against earnings, with and without the limit. */
export function getCliff(data) {
  const c = data?.cliff_example;
  if (!c || !isText(c.description) || !Number.isInteger(c.year)) fail("cliff_example", "incomplete");
  const { earnings, net_income_baseline: base, net_income_reform: reform } = c;
  if (![earnings, base, reform].every((a) => Array.isArray(a) && a.length >= 2 && a.every(isNum))) fail("cliff_example", "arrays invalid");
  if (base.length !== earnings.length || reform.length !== earnings.length) fail("cliff_example", "arrays of different lengths");
  for (let i = 1; i < earnings.length; i += 1) if (earnings[i] <= earnings[i - 1]) fail("cliff_example.earnings", "not increasing");
  if ("notes" in c && !isText(c.notes)) fail("cliff_example.notes", "not text");
  const rows = earnings.map((e, i) => ({ earnings: e, baseline: base[i], reform: reform[i] }));
  return { ...c, rows };
}

/**
 * The cliff in the example: income just below the limit (the last point under it), the first point above it, the
 * income lost between them, and the earnings needed to get back to the income below the limit (null if never within
 * the range, which the page states). Measured from the last point below the limit to the first above it; exactly
 * £100,000 still qualifies.
 */
export function cliffSummary(cliff, limit = 100000) {
  const rows = cliff.rows;
  const below = rows.findLastIndex((r) => r.earnings < limit);
  const above = rows.findIndex((r) => r.earnings > limit);
  if (below < 0 || above < 0) fail("cliff_example.earnings", `does not span £${limit}`);
  const before = rows[below];
  const after = rows[above];
  const recover = rows.slice(above).find((r) => r.baseline >= before.baseline);
  return { before, after, drop: before.baseline - after.baseline, recoverAt: recover ? recover.earnings : null };
}

/** Published estimates to compare against. */
export function getBenchmarks(data) {
  const rows = data?.benchmarks;
  if (!Array.isArray(rows) || rows.length === 0) fail("benchmarks", "missing");
  rows.forEach((b, i) => {
    const ok =
      isText(b?.source) && isText(b.figure) && isNum(b.ours) && Number.isInteger(b.year) && isText(b.like_for_like) && isText(b.url) &&
      isText(b.announcement_url) && isText(b.underlying_source_url);
    if (!ok) fail(`benchmarks.${i}`, "invalid");
  });
  return rows;
}

export function getLimitations(data) {
  const rows = data?.limitations;
  if (!(Array.isArray(rows) && rows.length > 0 && rows.every(isText))) fail("limitations", "missing");
  return rows;
}

/** The household form's precomputed families: options, the default family, and net income by earnings for each. */
export function getHouseholdGrid(data) {
  const g = data?.household_grid;
  if (!g || !Number.isInteger(g.year) || !Array.isArray(g.earnings)) fail("household_grid", "incomplete");
  const dims = ["parents", "children", "spend_per_child"];
  for (const d of dims) {
    const opts = g.options?.[d];
    if (!Array.isArray(opts) || opts.length === 0 || !opts.every((o) => isText(o?.id) && isText(o?.label))) fail(`household_grid.options.${d}`, "invalid");
  }
  const def = g.default;
  if (!def || !g.options.parents.some((o) => o.id === def.parent) || !g.options.children.some((o) => o.id === def.children) || !g.options.spend_per_child.some((o) => o.id === def.spend_per_child)) fail("household_grid.default", "not an option");
  for (let i = 1; i < g.earnings.length; i += 1) if (!(g.earnings[i] > g.earnings[i - 1])) fail("household_grid.earnings", "not increasing");
  for (const p of g.options.parents)
    for (const c of g.options.children)
      for (const s of g.options.spend_per_child) {
        const key = `${p.id}|${c.id}|${s.id}`;
        const v = g.series?.[key];
        if (!v || ![v.baseline, v.reform].every((a) => Array.isArray(a) && a.length === g.earnings.length && a.every(isNum))) fail(`household_grid.series.${key}`, "invalid");
      }
  return g;
}

/** One family's rows from the grid, in the shape cliffSummary reads. */
export function householdRows(grid, choice) {
  const v = grid.series[`${choice.parent}|${choice.children}|${choice.spend_per_child}`];
  if (!v) fail("household_grid.series", `no family ${JSON.stringify(choice)}`);
  return { rows: grid.earnings.map((e, i) => ({ earnings: e, baseline: v.baseline[i], reform: v.reform[i] })) };
}

// ── Labour supply ─────────────────────────────────────────────────────────

export const LS_BOUNDS = ["central", "low", "high"];
export const LS_BOUND_LABELS = { central: "Central", low: "Low", high: "High" };
/** The page opens static: no margin on, central elasticities. */
export const STATIC_SETTING = {
  extensive: false,
  intensive: false,
  bound: "central",
  bounds: { extensive: "central", intensive: "central" },
};

/** The labour supply block: each margin's offset (£bn by year, positive = money back) and the dynamic cost. */
export function getLabourSupply(data) {
  const years = getYears(data);
  const ls = data?.labour_supply;
  if (!ls || typeof ls !== "object") fail("labour_supply", "missing");
  const read = (path) =>
    Object.fromEntries(
      LS_BOUNDS.map((b) => [b, byYear(path.reduce((o, k) => o?.[k], ls)?.[b], years, `labour_supply.${path.join(".")}.${b}`)]),
    );
  const out = {
    years,
    extensive: { offset: read(["extensive", "offset_bn"]), entrants: read(["extensive", "entrants"]), ftes: read(["extensive", "ftes"]) },
    intensive: {
      offset: read(["intensive", "offset_bn"]),
      ftes: read(["intensive", "ftes"]),
      // Its price effect (money back) and income effect (money out), for each group and both together.
      ...Object.fromEntries(
        ["at_or_below_limit", "over_limit"].map((g) => [
          g,
          { price: read(["intensive", g, "price_offset_bn"]), income: read(["intensive", g, "income_offset_bn"]) },
        ]),
      ),
      price: read(["intensive", "price_offset_bn"]),
      income: read(["intensive", "income_offset_bn"]),
    },
    dynamic: read(["dynamic_cost_bn"]),
    assumptions: ls.assumptions,
    notModelled: ls.not_modelled,
  };
  if (!isText(ls.not_modelled)) fail("labour_supply.not_modelled", "missing");
  if (!isText(ls.responding_population)) fail("labour_supply.responding_population", "missing");
  if (!isText(ls.assumptions?.participation_elasticities)) fail("labour_supply.assumptions.participation_elasticities", "missing");
  if (!isText(ls.assumptions?.income_elasticities)) fail("labour_supply.assumptions.income_elasticities", "missing");
  if (!isText(ls.assumptions?.couples)) fail("labour_supply.assumptions.couples", "missing");
  if (!isText(ls.assumptions?.couples_issue_url)) fail("labour_supply.assumptions.couples_issue_url", "missing");
  for (const k of ["hours_for_new_entrants", "free_hours_displacement"]) {
    if (!isNum(ls.assumptions?.[k])) fail(`labour_supply.assumptions.${k}`, "missing");
  }
  for (const b of ["low", "high"]) {
    if (!isNum(ls.assumptions?.elasticity_scales?.[b])) fail(`labour_supply.assumptions.elasticity_scales.${b}`, "missing");
    if (!isNum(ls.assumptions?.free_hours_displacement_range?.[b])) fail(`labour_supply.assumptions.free_hours_displacement_range.${b}`, "missing");
  }
  for (const k of ["hours_price_elasticity", "price_elasticity_central", "price_elasticity_low", "price_elasticity_high"]) {
    if (!isNum(ls.assumptions?.[k])) fail(`labour_supply.assumptions.${k}`, "missing");
  }
  // The dynamic cost must be the static total less both offsets, or the page's adjusted figures would not match it.
  const total = byYear(data?.budget?.gross_bn?.total, years, "budget.gross_bn.total");
  for (const b of LS_BOUNDS) {
    years.forEach((y, i) => {
      if (out.extensive.entrants[b][i] < 0) fail("labour_supply.extensive.entrants", `${b} ${y}: negative`);
      const hours = out.intensive.price[b][i] + out.intensive.income[b][i];
      if (Math.abs(out.intensive.offset[b][i] - hours) > 0.002) fail("labour_supply.intensive.offset_bn", `${b} ${y}: not price plus income`);
      const expected = total[i] - out.extensive.offset[b][i] - out.intensive.offset[b][i];
      if (Math.abs(out.dynamic[b][i] - expected) > 0.002) fail("labour_supply.dynamic_cost_bn", `${b} ${y}: not static less the offsets`);
    });
  }
  return out;
}

const LS_KEYS = { extensive: "ext", intensive: "int" };
const LS_WORDS = { extensive: "moving into work", intensive: "hours" };

/** A response's own setting (low, central or high); `bound` is the shared default. */
export const boundOf = (setting, margin) => setting.bounds?.[margin] ?? setting.bound ?? "central";

/**
 * The labour supply setting from the URL: `?ls=ext,int:high` switches responses on, each with its own
 * setting (central when none is given); `bound` is an older shared setting, kept as the default. Anything unknown
 * reads as static.
 */
export function parseLabourSupply(ls, bound) {
  const fallback = LS_BOUNDS.includes(bound) ? bound : "central";
  const on = new Map(
    (ls ?? "")
      .split(",")
      .filter(Boolean)
      .map((part) => {
        const [key, b] = part.split(":");
        return [key, LS_BOUNDS.includes(b) ? b : fallback];
      }),
  );
  const out = { bound: "central", bounds: {} };
  for (const [margin, key] of Object.entries(LS_KEYS)) {
    out[margin] = on.has(key);
    out.bounds[margin] = on.get(key) ?? fallback;
  }
  return out;
}

/** The URL parameters for a setting: none when static, so the default URL stays clean. */
export function labourSupplyParams(setting) {
  const on = Object.entries(LS_KEYS)
    .filter(([margin]) => setting[margin])
    .map(([margin, key]) => (boundOf(setting, margin) === "central" ? key : `${key}:${boundOf(setting, margin)}`));
  return on.length ? [["ls", on.join(",")]] : [];
}

export const isStatic = (setting) => !setting.extensive && !setting.intensive;

/** Which responses are on, in words: "moving into work and hours at the high setting". */
export function labourSupplyLabel(setting) {
  const on = Object.keys(LS_KEYS)
    .filter((m) => setting[m])
    .map((m) => (boundOf(setting, m) === "central" ? LS_WORDS[m] : `${LS_WORDS[m]} at the ${boundOf(setting, m)} setting`));
  if (on.length === 0) return "static: no change in work";
  return on.length > 1 ? `${on.slice(0, -1).join(", ")} and ${on.at(-1)}` : on[0];
}

/** The money back (£bn by year, positive = less cost) from the responses switched on, each at its own setting. */
export function labourSupplyOffset(data, setting) {
  const ls = getLabourSupply(data);
  return ls.years.map((_, i) =>
    Object.keys(LS_KEYS).reduce((t, m) => t + (setting[m] ? ls[m].offset[boundOf(setting, m)][i] : 0), 0),
  );
}

/** Run every reader over the file; throws a ResultsError on the first invalid block. */
export function validateResults(data) {
  const years = getYears(data);
  getMeta(data);
  getReform(data);
  getBudget(data);
  getRange(data);
  getSensitivities(data);
  getThirtyHoursComponents(data);
  getBudgetComparisons(data);
  getDistributionYears(data);
  for (const y of years) getChildrenByAge(data, y);
  getValidation(data);
  getAssumptions(data);
  getModellingAssumptions(data);
  cliffSummary(getCliff(data));
  const grid = getHouseholdGrid(data);
  cliffSummary(householdRows(grid, grid.default));
  getBenchmarks(data);
  getLimitations(data);
  getLabourSupply(data);
  return true;
}
