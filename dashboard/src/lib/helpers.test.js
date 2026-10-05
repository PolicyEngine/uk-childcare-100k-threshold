import { describe, expect, it } from "vitest";

import {
  cliffSummary,
  fyLabel,
  getBenchmarks,
  getBudget,
  getBudgetComparisons,
  getCliff,
  getCountries,
  getDeciles,
  getDistributionYears,
  getLimitations,
  getMeta,
  getRecipients,
  getReform,
  getValidation,
  getYears,
  isSample,
} from "./dataHelpers";
import { formatBn, formatCount, formatCurrency, formatPct, formatThousands } from "./formatters";
import { niceTicks } from "./ticks";
import { BAD_VALUES, mutate, realData as data } from "./testUtils";

const years = data.meta.years;
const final = years.at(-1);

describe("the results file", () => {
  it("passes every reader", () => {
    expect(getYears(data)).toEqual(years);
    expect(getMeta(data)).not.toBeNull();
    expect(getReform(data)).not.toBeNull();
    expect(getBudget(data)).not.toBeNull();
    const c = getBudgetComparisons(data);
    for (const k of ["net", "thirtyOnly", "tfcOnly", "crossCheck"]) expect(c[k], k).not.toBeNull();
    expect(getDistributionYears(data)).toEqual(years);
    expect(getValidation(data)).not.toBeNull();
    expect(getCliff(data)).not.toBeNull();
    expect(getBenchmarks(data)).not.toBeNull();
    expect(getLimitations(data)).not.toBeNull();
  });

  it("has costs that add up: the two schemes make the total each year", () => {
    for (const r of getBudget(data).rows) expect(Math.abs(r.thirty_hours + r.tax_free_childcare - r.total)).toBeLessThanOrEqual(0.02);
  });

  it("counts no more families in either scheme than gain in all", () => {
    for (const y of years) {
      const r = getRecipients(data, y);
      expect(r.by_scheme.thirty_hours).toBeLessThanOrEqual(r.families_gaining);
      expect(r.by_scheme.tax_free_childcare).toBeLessThanOrEqual(r.families_gaining);
    }
  });

  it("has the example household no worse off under the reform at any earnings", () => {
    const c = getCliff(data);
    for (const r of c.rows) expect(r.reform).toBeGreaterThanOrEqual(r.baseline);
  });
});

describe("readers fail closed", () => {
  it.each(BAD_VALUES)("on a bad cost (%s)", (bad) => {
    expect(getBudget(mutate(`budget.gross_bn.total.${final}`, bad))).toBeNull();
  });

  it("when the schemes do not add up to the total", () => {
    expect(getBudget(mutate(`budget.gross_bn.total.${final}`, 99))).toBeNull();
  });

  it("on bad years", () => {
    expect(getYears(mutate("meta.years", [2027, 2026]))).toBeNull();
    expect(getYears(mutate("meta.years", []))).toBeNull();
    expect(getBudget(mutate("meta.years", null))).toBeNull();
  });

  it("on a missing comparison, without dropping the others", () => {
    const c = getBudgetComparisons(mutate("budget.cross_check", null));
    expect(c.crossCheck).toBeNull();
    expect(c.thirtyOnly).not.toBeNull();
  });

  it.each(BAD_VALUES)("on a bad decile value (%s)", (bad) => {
    expect(getDeciles(mutate(`distribution.${final}.by_decile.3.mean_change_gbp`, bad), final)).toBeNull();
  });

  it("on a short decile list, and drops that year from the choice", () => {
    const broken = mutate(`distribution.${final}.by_decile`, data.distribution[final].by_decile.slice(0, 9));
    expect(getDeciles(broken, final)).toBeNull();
    expect(getDistributionYears(broken)).not.toContain(final);
  });

  it("on a bad country row", () => {
    expect(getCountries(mutate(`distribution.${final}.by_country.0.country`, ""), final)).toBeNull();
  });

  it("on cliff arrays of different lengths", () => {
    expect(getCliff(mutate("cliff_example.net_income_reform", data.cliff_example.net_income_reform.slice(1)))).toBeNull();
  });

  it("on a reform parameter that is not removed", () => {
    expect(getReform(mutate("reform.parameters.0.reform", 120000))).toBeNull();
  });

  it("on a validation row without a source link", () => {
    expect(getValidation(mutate("baseline_validation.0.url", null))).toBeNull();
  });
});

describe("the sample flag", () => {
  it("is read only from an explicit meta.sample true", () => {
    expect(isSample({ meta: { sample: true } })).toBe(true);
    expect(isSample({ meta: { sample: "true" } })).toBe(false);
    expect(isSample({ meta: {} })).toBe(false);
    expect(isSample({ sample: true })).toBe(false);
  });
});

describe("the cliff summary", () => {
  it("finds the drop just above £100,000 and where income recovers", () => {
    const rows = [
      { earnings: 99000, baseline: 100, reform: 100 },
      { earnings: 100000, baseline: 101, reform: 101 },
      { earnings: 101000, baseline: 80, reform: 102 },
      { earnings: 120000, baseline: 101, reform: 120 },
    ];
    const s = cliffSummary({ rows });
    expect(s.drop).toBe(21);
    expect(s.recoverAt).toBe(120000);
  });

  it("says income never recovers within the range when it does not", () => {
    const rows = [
      { earnings: 100000, baseline: 101, reform: 101 },
      { earnings: 101000, baseline: 80, reform: 102 },
    ];
    expect(cliffSummary({ rows }).recoverAt).toBeNull();
  });
});

describe("formatters", () => {
  it("print nothing broken for bad values", () => {
    for (const bad of BAD_VALUES) {
      for (const f of [formatBn, formatCount, formatCurrency, formatPct, formatThousands]) expect(f(bad)).toBe("unavailable");
    }
  });

  it("format the common cases", () => {
    expect(formatBn(0.774, 2)).toBe("£0.77bn");
    expect(formatCurrency(-1234.4)).toBe("-£1,234");
    expect(formatThousands(94560)).toBe("95,000");
    expect(formatPct(-0.04)).toBe("0.0%");
    expect(fyLabel(2029)).toBe("2029-30");
  });

  it("pick round axis ticks that include zero", () => {
    expect(niceTicks(0.1, 0.77)).toEqual([0, 0.2, 0.4, 0.6, 0.8]);
  });
});
