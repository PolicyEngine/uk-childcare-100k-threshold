/**
 * The yearly cost chart and its notes under each labour supply setting. Recharts' ResponsiveContainer measures zero in
 * happy-dom and draws nothing, so it is replaced by a fixed-size container: the bars and the tooltip are then rendered
 * from the same data the page uses.
 */
import { cloneElement } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, ResponsiveContainer: ({ children }) => cloneElement(children, { width: 800, height: 340 }) };
});

import LandingTab, { chartRowTotal, costChartData, netGrossGapM, OFFSET_KEY, offsetLabel } from "./LandingTab";
import { CustomTooltip } from "./ui";
import { getBudget, labourSupplyOffset } from "../lib/dataHelpers";
import { formatMoneyBn } from "../lib/formatters";
import { realData as data, textOf } from "../lib/testUtils";

const BOTH = { extensive: true, intensive: true, bound: "central" };
const ALL = { extensive: true, intensive: true, bunching: true, bound: "central" };
const EXTENSIVE = { extensive: true, intensive: false, bound: "central" };
const STATIC = { extensive: false, intensive: false, bound: "central" };
const years = data.meta.years.map(String);

describe("the yearly cost chart", () => {
  it("draws the labour supply response as its own series when a margin is on", () => {
    const { container: off } = render(<LandingTab data={data} setting={STATIC} />);
    expect(off.querySelectorAll(".recharts-bar")).toHaveLength(2);
    const { container: on } = render(<LandingTab data={data} setting={BOTH} />);
    expect(on.querySelectorAll(".recharts-bar")).toHaveLength(3);
    expect(on.querySelectorAll(".recharts-bar")[2].querySelectorAll(".recharts-bar-rectangle")).toHaveLength(years.length);
  });

  it.each([
    ["both margins", BOTH],
    ["all three responses", ALL],
    ["moving into work alone", EXTENSIVE],
    ["static", STATIC],
  ])("adds up, in each year, to the cost after the response (%s)", (_, setting) => {
    const offsets = labourSupplyOffset(data, setting);
    const static_ = setting === STATIC;
    const { rows, series } = costChartData(getBudget(data), offsets, !static_);
    expect(series.includes(OFFSET_KEY)).toBe(!static_);
    rows.forEach((row, i) => {
      const y = years[i];
      const expected = static_ ? data.budget.gross_bn.total[y] : data.budget.gross_bn.total[y] - offsets[i];
      expect(chartRowTotal(row, series)).toBeCloseTo(expected, 9);
      if (setting === ALL) expect(Math.abs(chartRowTotal(row, series) - data.labour_supply.dynamic_cost_bn.central[y])).toBeLessThan(0.002);
    });
  });

  it("totals the tooltip over the series drawn, so it shows the selected setting's cost", () => {
    const offsets = labourSupplyOffset(data, BOTH);
    const { rows, series } = costChartData(getBudget(data), offsets, true);
    const row = rows[1];
    const payload = series.map((s) => ({ name: s, value: row[s], color: "#000" }));
    render(<CustomTooltip active payload={payload} label={row.label} formatter={formatMoneyBn} totalLabel="Cost after the response" />);
    expect(screen.getByText("Cost after the response").nextSibling.textContent).toBe(formatMoneyBn(row.total - offsets[1]));
  });
});

describe("sign-aware wording", () => {
  it("names the response by its sign", () => {
    expect(offsetLabel([0.03, 0.02])).toBe("Back from parents working more");
    expect(offsetLabel([-0.005, -0.005])).toBe("Added by the labour supply response");
    expect(offsetLabel([0.01, -0.01])).toBe("Labour supply response");
  });

  it("says the cost rises, in £m, when moving into work alone adds to it", () => {
    const offsets = labourSupplyOffset(data, EXTENSIVE);
    const text = textOf(<LandingTab data={data} setting={EXTENSIVE} />);
    if (offsets.every((v) => v < 0)) {
      expect(text).not.toContain("Back from parents working more");
      expect(text).toContain("Added by the labour supply response");
      const lead = years.indexOf(String(data.meta.lead_year));
      expect(text).toContain(`${formatMoneyBn(-offsets[lead])} more, as the response raises the cost`);
      expect(text).not.toMatch(/£0\.00bn/);
    }
  });

  it("calls the response money back when it lowers the cost", () => {
    const offsets = labourSupplyOffset(data, BOTH);
    if (offsets.every((v) => v > 0)) expect(textOf(<LandingTab data={data} setting={BOTH} />)).toContain("Back from parents working more");
  });

  it("formats small amounts in £m", () => {
    expect(formatMoneyBn(0.003)).toBe("£3m");
    expect(formatMoneyBn(-0.005)).toBe("-£5m");
    expect(formatMoneyBn(0.55)).toBe("£0.55bn");
  });
});

describe("the net-cost note", () => {
  const gross = years.map((y) => data.budget.gross_bn.total[y]);
  const net = years.map((y) => data.budget.net_bn.total[y]);

  it("states the actual gap between net and gross, in the static setting only", () => {
    const gap = netGrossGapM(net, gross);
    const text = textOf(<LandingTab data={data} setting={STATIC} />);
    if (gap > 0 && gap <= 2) expect(text).toContain(`within £${gap}m`);
    expect(text).not.toContain("The cost is the same net of other taxes and benefits: nothing else changes");
    expect(textOf(<LandingTab data={data} setting={BOTH} />)).not.toContain("Net of other taxes and benefits");
  });

  it("measures the gap in £m", () => {
    expect(netGrossGapM([0.538, 0.574], [0.539, 0.573])).toBe(1);
    expect(netGrossGapM([0.5], [0.5])).toBe(0);
  });
});
