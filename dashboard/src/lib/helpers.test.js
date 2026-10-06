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
  LEAD_YEAR,
  ResultsError,
  validateResults,
  yearHeading,
} from "./dataHelpers";
import { formatBn, formatCount, formatCurrency, formatPct, formatThousands } from "./formatters";
import { niceTicks } from "./ticks";
import { BAD_VALUES, mutate, realData as data } from "./testUtils";

const years = data.meta.years;
const final = years.at(-1);

describe("the results file", () => {
  it("passes validation", () => {
    expect(validateResults(data)).toBe(true);
    expect(getYears(data)).toEqual(years);
    expect(getYears(data)).toContain(LEAD_YEAR);
    expect(getDistributionYears(data)).toEqual(years);
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

  it("never has a single suppressed nation, so none can be worked out from the UK total", () => {
    for (const y of years) expect(getCountries(data, y).filter((c) => c.suppressed).length, String(y)).not.toBe(1);
  });

  it("has the example household no worse off under the reform at any earnings", () => {
    for (const r of getCliff(data).rows) expect(r.reform).toBeGreaterThanOrEqual(r.baseline);
  });
});

describe("validation throws, naming the block", () => {
  const throwsOn = (fn, block) => {
    expect(fn).toThrow(ResultsError);
    expect(fn).toThrow(block);
  };

  it.each(BAD_VALUES)("on a bad cost (%s)", (bad) => {
    throwsOn(() => getBudget(mutate(`budget.gross_bn.total.${final}`, bad)), "budget.gross_bn.total");
  });

  it("when the schemes do not add up to the total", () => {
    throwsOn(() => getBudget(mutate(`budget.gross_bn.total.${final}`, 99)), "budget.gross_bn");
  });

  it("on bad years, and on years without the lead year", () => {
    throwsOn(() => getYears(mutate("meta.years", [2027, 2026])), "meta.years");
    throwsOn(() => getYears(mutate("meta.years", [])), "meta.years");
    throwsOn(() => getYears(mutate("meta.years", [2028, 2029])), "lead year");
  });

  it("on a missing provenance field", () => {
    throwsOn(() => getMeta(mutate("meta.git_revision", undefined, { remove: true })), "meta.git_revision");
  });

  it("on a range whose central is not the headline cost", () => {
    throwsOn(() => getRange(mutate(`budget.range_bn.central.${final}`, 9)), "budget.range_bn");
  });

  it("on a sensitivity on neither side, or a side that is not a list of ids", () => {
    throwsOn(() => getSensitivities(mutate("budget.sensitivities.low", [])), "budget.sensitivities");
    throwsOn(() => getSensitivities(mutate("budget.sensitivities.low", 42)), "budget.sensitivities.low");
    throwsOn(() => getSensitivities(mutate("budget.sensitivities.high", {})), "budget.sensitivities.high");
    throwsOn(() => getSensitivities(mutate("budget.sensitivities.high", [1, 2])), "budget.sensitivities.high");
  });

  it("on a missing block that the page reads", () => {
    for (const block of ["budget.sensitivities", "budget.thirty_hours_components_bn", "baseline_validation", "limitations", "benchmarks", "assumptions"]) {
      expect(() => validateResults(mutate(block, undefined, { remove: true })), block).toThrow(ResultsError);
    }
  });

  it("on a missing value that is not marked suppressed", () => {
    throwsOn(() => getDeciles(mutate(`distribution.${final}.by_decile.9.mean_change_gbp`, null), final), `distribution.${final}.by_decile.9`);
    const i = data.distribution[final].by_country.findIndex((r) => !r.suppressed);
    throwsOn(() => getCountries(mutate(`distribution.${final}.by_country.${i}.total_change_bn`, null), final), `distribution.${final}.by_country`);
  });

  it("on a suppressed cell that still carries a number", () => {
    const i = data.distribution[final].by_country.findIndex((r) => !r.suppressed);
    throwsOn(() => getCountries(mutate(`distribution.${final}.by_country.${i}.suppressed`, true), final), `distribution.${final}.by_country`);
  });

  it("on a mean gain that is null without being suppressed", () => {
    throwsOn(() => getRecipients(mutate(`recipients.${final}.mean_gain_gbp`, null), final), "mean_gain_gbp");
  });

  it.each(BAD_VALUES)("on a bad decile value (%s)", (bad) => {
    expect(() => getDeciles(mutate(`distribution.${final}.by_decile.9.mean_change_gbp`, bad), final)).toThrow(ResultsError);
  });

  it("on a short decile list: the year is not dropped from the choice, the file fails", () => {
    const broken = mutate(`distribution.${final}.by_decile`, data.distribution[final].by_decile.slice(0, 9));
    throwsOn(() => getDistributionYears(broken), `distribution.${final}.by_decile`);
  });

  it("on an unknown nation", () => {
    throwsOn(() => getCountries(mutate(`distribution.${final}.by_country.0.country`, ""), final), `distribution.${final}.by_country.0.country`);
  });

  it("on cliff arrays of different lengths", () => {
    throwsOn(() => getCliff(mutate("cliff_example.net_income_reform", data.cliff_example.net_income_reform.slice(1))), "cliff_example");
  });

  it("on a reform parameter that is not removed", () => {
    throwsOn(() => getReform(mutate("reform.parameters.0.reform", 120000)), "reform.parameters");
  });

  it("on a validation row without a source link", () => {
    throwsOn(() => getValidation(mutate("baseline_validation.0.url", null)), "baseline_validation.0");
  });

  it("on a benchmark without its CenTax source", () => {
    throwsOn(() => getBenchmarks(mutate("benchmarks.0.underlying_source_url", undefined, { remove: true })), "benchmarks.0");
  });

  it("covers every reader in validateResults", () => {
    expect(getChildrenByAge(data, final)).toHaveLength(5);
    expect(getAssumptions(data).length).toBeGreaterThan(0);
    expect(getLimitations(data).length).toBeGreaterThan(0);
    expect(getBudgetComparisons(data).net).toHaveLength(years.length);
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

  it("throws when the earnings do not span the limit", () => {
    expect(() => cliffSummary({ rows: [{ earnings: 99000, baseline: 1, reform: 1 }] })).toThrow(ResultsError);
  });
});

describe("formatters", () => {
  it("throw on bad values rather than print a placeholder", () => {
    for (const bad of BAD_VALUES) {
      for (const f of [formatBn, formatCount, formatCurrency, formatPct, formatThousands]) expect(() => f(bad)).toThrow(TypeError);
    }
  });

  it("format the common cases", () => {
    expect(formatBn(0.774, 2)).toBe("£0.77bn");
    expect(formatCurrency(-1234.4)).toBe("-£1,234");
    expect(formatThousands(94560)).toBe("95,000");
    expect(formatPct(-0.04)).toBe("0.0%");
    expect(fyLabel(2029)).toBe("2029-30");
    expect(yearHeading(2026)).toBe("2026-27 (illustrative)");
    expect(yearHeading(2027)).toBe("2027-28");
  });

  it("pick round axis ticks that include zero", () => {
    expect(niceTicks(0.1, 0.77)).toEqual([0, 0.2, 0.4, 0.6, 0.8]);
  });
});
