/**
 * The yearly cost chart (the static cost) and its notes. Recharts' ResponsiveContainer measures zero in
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

import LandingTab, { costChartData, netGrossGapM } from "./LandingTab";
import { CustomTooltip } from "./ui";
import { getBudget, SCHEMES } from "../lib/dataHelpers";
import { formatMoneyBn } from "../lib/formatters";
import { realData as data, textOf } from "../lib/testUtils";

const years = data.meta.years.map(String);

describe("the yearly cost chart", () => {
  it("draws the two schemes only: the static cost", () => {
    // The yearly chart only: the range chart under "How certain" draws a bar of its own.
    const { container } = render(<LandingTab data={data} />);
    const bars = container.querySelector('[data-testid="cost-chart"]').querySelectorAll(".recharts-bar");
    expect(bars).toHaveLength(2);
    expect(bars[1].querySelectorAll(".recharts-bar-rectangle")).toHaveLength(years.length);
  });

  it("adds up, in each year, to the static total", () => {
    costChartData(getBudget(data)).forEach((row, i) => {
      expect(row.thirty_hours + row.tax_free_childcare).toBeCloseTo(data.budget.gross_bn.total[years[i]], 2);
    });
  });

  it("totals the tooltip over the two schemes", () => {
    const row = costChartData(getBudget(data))[1];
    const payload = SCHEMES.map((s) => ({ name: s, value: row[s], color: "#000" }));
    render(<CustomTooltip active payload={payload} label={row.label} formatter={formatMoneyBn} totalLabel="Total" />);
    expect(screen.getByText("Total").nextSibling.textContent).toBe(formatMoneyBn(row.thirty_hours + row.tax_free_childcare));
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

  it("states the actual gap between net and gross", () => {
    const gap = netGrossGapM(net, gross);
    const text = textOf(<LandingTab data={data} />);
    if (gap > 0 && gap <= 2) expect(text).toContain(`within £${gap}m`);
    expect(text).not.toContain("The cost is the same net of other taxes and benefits: nothing else changes");
  });

  it("measures the gap in £m", () => {
    expect(netGrossGapM([0.538, 0.574], [0.539, 0.573])).toBe(1);
    expect(netGrossGapM([0.5], [0.5])).toBe(0);
  });
});
