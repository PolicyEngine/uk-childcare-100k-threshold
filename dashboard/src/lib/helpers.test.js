import { describe, expect, it } from "vitest";

import {
  cliffSummary,
  fyLabel,
  getBenchmarks,
  getBudget,
  getAssumptions,
  getBudgetComparisons,
  getChildrenByAge,
  getCliff,
  getCrossCheck,
  getCountries,
  getDeciles,
  getDistributionYears,
  getLimitations,
  getMeta,
  getRange,
  getRecipients,
  getReform,
  getSensitivities,
  getThirtyHoursComponents,
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
    for (const k of ["net", "thirtyOnly", "tfcOnly"]) expect(c[k], k).not.toBeNull();
    expect(getRange(data)).not.toBeNull();
    expect(getSensitivities(data)).not.toBeNull();
    expect(getCrossCheck(data)).not.toBeNull();
    expect(getThirtyHoursComponents(data)).not.toBeNull();
    expect(getAssumptions(data)).not.toBeNull();
    for (const y of years) expect(getChildrenByAge(data, y), String(y)).not.toBeNull();
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

  it("builds the low and high ends from the central cost and the sensitivities", () => {
    const r = getRange(data);
    const s = getSensitivities(data);
    years.forEach((_, i) => {
      for (const side of ["low", "high"]) {
        const sum = s.rows.filter((x) => x.side === side).reduce((a, x) => a + x.values[i], r.central[i]);
        expect(Math.abs(sum - r[side][i]), `${side} ${years[i]}`).toBeLessThan(0.003);
      }
    });
  });

  it("splits the 30 hours cost into components that add up to it", () => {
    const c = getThirtyHoursComponents(data);
    const b = getBudget(data);
    b.rows.forEach((row, i) => expect(Math.abs(c.extended[i] + c.universal[i] + c.targeted[i] - row.thirty_hours)).toBeLessThan(0.003));
  });

  it("marks every cell without numbers as suppressed, never as a silent gap", () => {
    for (const y of years) {
      for (const r of [...getDeciles(data, y), ...getCountries(data, y)]) {
        if (r.suppressed) expect(r.mean_change_gbp ?? r.total_change_bn ?? null).toBeNull();
      }
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

  it("on a missing cross-check, without dropping the budget", () => {
    const broken = mutate("budget.cross_check", null);
    expect(getCrossCheck(broken)).toBeNull();
    expect(getBudget(broken)).not.toBeNull();
  });

  it("on a range whose central is not the headline cost", () => {
    expect(getRange(mutate(`budget.range_bn.central.${final}`, 9))).toBeNull();
  });

  it("on a sensitivity with no side", () => {
    expect(getSensitivities(mutate("budget.sensitivities.low", []))).toBeNull();
  });

  it("on a sensitivity side that is not a list of ids", () => {
    expect(getSensitivities(mutate("budget.sensitivities.low", 42))).toBeNull();
    expect(getSensitivities(mutate("budget.sensitivities.high", {}))).toBeNull();
    expect(getSensitivities(mutate("budget.sensitivities.high", [1, 2]))).toBeNull();
  });

  it("on a missing value that is not marked suppressed", () => {
    expect(getDeciles(mutate(`distribution.${final}.by_decile.9.mean_change_gbp`, null), final)).toBeNull();
    expect(getCountries(mutate(`distribution.${final}.by_country.0.total_change_bn`, null), final)).toBeNull();
  });

  it("on a suppressed cell that still carries a number", () => {
    const i = data.distribution[final].by_country.findIndex((r) => !r.suppressed);
    expect(getCountries(mutate(`distribution.${final}.by_country.${i}.suppressed`, true), final)).toBeNull();
  });

  it.each(BAD_VALUES)("on a bad decile value (%s)", (bad) => {
    expect(getDeciles(mutate(`distribution.${final}.by_decile.9.mean_change_gbp`, bad), final)).toBeNull();
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
  it("measures from the last point below £100,000 to the first above it, and finds where income recovers", () => {
    const rows = [
      { earnings: 99000, baseline: 100, reform: 100 },
      { earnings: 100000, baseline: 90, reform: 101 },
      { earnings: 101000, baseline: 80, reform: 102 },
      { earnings: 120000, baseline: 101, reform: 120 },
    ];
    const s = cliffSummary({ rows });
    expect(s.before.earnings).toBe(99000);
    expect(s.after.earnings).toBe(101000);
    expect(s.drop).toBe(20);
    expect(s.recoverAt).toBe(120000);
  });

  it("says income never recovers within the range when it does not", () => {
    const rows = [
      { earnings: 99000, baseline: 101, reform: 101 },
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
