/**
 * Render contract against the committed results file: every number checked here is read from the file, so the same
 * tests pass when the real results replace the sample, and a missing or broken block must fail closed
 * ("unavailable"), never NaN.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const searchParams = new URLSearchParams();
const router = { replace: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router, useSearchParams: () => searchParams }));

import Dashboard, { TAB_OPTIONS } from "./Dashboard";
import LandingTab from "./LandingTab";
import WhoGainsTab, { DECILE_MEASURES } from "./WhoGainsTab";
import CliffTab from "./CliffTab";
import MethodTab from "./MethodTab";
import { cliffSummary, getCliff } from "../lib/dataHelpers";
import { formatThousands } from "../lib/formatters";
import { bn, BROKEN_TEXT, fy, gbp, mutate, realData as data, withSample } from "../lib/testUtils";

const years = data.meta.years;
const final = years.at(-1);
const total = (y) => data.budget.gross_bn.total[String(y)];

describe("the page", () => {
  it("renders every tab without broken text", () => {
    const { container } = render(<Dashboard data={data} />);
    for (const tab of TAB_OPTIONS) {
      fireEvent.click(screen.getByRole("tab", { name: tab.label }));
      const text = container.textContent.replace(/\s+/g, " ");
      expect(text, tab.label).not.toMatch(BROKEN_TEXT);
      // Formatter and inline fallbacks print a bare "unavailable"; nothing on the committed file may fail validation.
      expect(text, tab.label).not.toMatch(/\bunavailable\b|\bnull\b|\bundefined\b/i);
      expect(screen.queryAllByTestId("unavailable"), tab.label).toHaveLength(0);
    }
  });

  it("lists each tab's sections in the side menu, and every listed section exists", () => {
    render(<Dashboard data={data} />);
    for (const tab of TAB_OPTIONS) {
      fireEvent.click(screen.getByRole("tab", { name: tab.label }));
      const links = within(screen.getByTestId("section-nav")).getAllByRole("link");
      expect(links.length, tab.label).toBeGreaterThan(1);
      for (const a of links) expect(document.getElementById(a.getAttribute("href").slice(1)), a.textContent).toBeTruthy();
    }
  });

  it("states the modelled period in the intro, from the file", () => {
    render(<Dashboard data={data} />);
    expect(screen.getByTestId("intro").textContent).toContain(`from ${fy(years[0])} to ${fy(final)}`);
  });

  it("shows the sample banner on every tab when meta.sample is true", () => {
    render(<Dashboard data={withSample(true)} />);
    for (const tab of TAB_OPTIONS) {
      fireEvent.click(screen.getByRole("tab", { name: tab.label }));
      expect(screen.getByTestId("sample-banner")).toBeTruthy();
    }
  });

  it("has no sample banner once meta.sample is gone", () => {
    render(<Dashboard data={withSample(false)} />);
    expect(screen.queryByTestId("sample-banner")).toBeNull();
  });
});

describe("budget impact", () => {
  it("shows the final year's cost, its split and the families gaining, from the file", () => {
    render(<LandingTab data={data} />);
    const g = data.budget.gross_bn;
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(total(final)));
    expect(screen.getByTestId("card-split").textContent).toContain(`${bn(g.thirty_hours[final])} and ${bn(g.tax_free_childcare[final])}`);
    const r = data.recipients[final];
    expect(screen.getByTestId("card-families").textContent).toContain(formatThousands(r.families_gaining));
    expect(screen.getByTestId("card-families").textContent).toContain(gbp(r.mean_gain_gbp));
  });

  it("compares with the Conservatives' figure for the year the file names", () => {
    render(<LandingTab data={data} />);
    const b = data.benchmarks[0];
    const card = screen.getByTestId("card-benchmark").textContent;
    expect(card).toContain(bn(total(b.year)));
    expect(card).toContain(b.figure);
    expect(screen.getByTestId("topic-conservatives").textContent).toContain(b.like_for_like);
  });

  it("shows each comparison table with a row per year", () => {
    render(<LandingTab data={data} />);
    const panel = screen.getByTestId("comparisons");
    for (const [title, table] of [
      ["One scheme at a time", "variants-table"],
      ["Another dataset", "cross-check-table"],
      ["After other taxes and benefits", "net-table"],
    ]) {
      fireEvent.click(within(panel).getByRole("tab", { name: new RegExp(title) }));
      const rows = within(screen.getByTestId(table)).getAllByRole("row").slice(1);
      expect(rows).toHaveLength(years.length);
      expect(rows.at(-1).textContent).toContain(bn(total(final)));
    }
  });

  it("fails closed when a cost is missing", () => {
    render(<LandingTab data={mutate(`budget.gross_bn.thirty_hours.${final}`, null)} />);
    expect(screen.getByTestId("unavailable")).toBeTruthy();
  });

  it("drops only the cross-check when it is missing", () => {
    render(<LandingTab data={mutate("budget.cross_check", undefined, { remove: true })} />);
    expect(screen.getByTestId("card-cost")).toBeTruthy();
    fireEvent.click(within(screen.getByTestId("comparisons")).getByRole("tab", { name: /Another dataset/ }));
    expect(screen.getByTestId("unavailable").textContent).toMatch(/cross-check is unavailable/);
  });
});

describe("who gains", () => {
  it("draws the deciles and switches measure and year", () => {
    render(<WhoGainsTab data={data} />);
    expect(screen.getByTestId("decile-chart")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Show"), { target: { value: DECILE_MEASURES[2].id } });
    expect(screen.getByLabelText("Show").value).toBe(DECILE_MEASURES[2].id);
    fireEvent.change(screen.getByLabelText("Year"), { target: { value: String(years[0]) } });
    const r = data.recipients[years[0]];
    const rows = within(screen.getByTestId("scheme-table")).getAllByRole("row");
    expect(rows.at(-1).textContent).toContain(r.families_gaining.toLocaleString("en-GB"));
  });

  it("shows every nation and the scheme counts from the file", () => {
    render(<WhoGainsTab data={data} />);
    const countries = data.distribution[final].by_country;
    const rows = within(screen.getByTestId("country-table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(countries.length);
    countries.forEach((c, i) => expect(rows[i].textContent).toContain(bn(c.total_change_bn)));
    const s = within(screen.getByTestId("scheme-table")).getAllByRole("row").slice(1);
    expect(s[0].textContent).toContain(data.recipients[final].by_scheme.thirty_hours.toLocaleString("en-GB"));
    expect(s[1].textContent).toContain(data.recipients[final].by_scheme.tax_free_childcare.toLocaleString("en-GB"));
  });

  it("leaves a year with a broken distribution out of the choice", () => {
    const broken = mutate(`distribution.${final}.by_decile`, []);
    render(<WhoGainsTab data={broken} />);
    const options = within(screen.getByLabelText("Year")).getAllByRole("option").map((o) => o.textContent);
    expect(options).not.toContain(fy(final));
    expect(screen.queryAllByTestId("unavailable")).toHaveLength(0);
  });

  it("fails closed when no year is usable", () => {
    render(<WhoGainsTab data={mutate("distribution", {})} />);
    expect(screen.getByTestId("unavailable")).toBeTruthy();
  });
});

describe("the cliff", () => {
  it("states the drop at £100,000 from the file", () => {
    render(<CliffTab data={data} />);
    const s = cliffSummary(getCliff(data));
    expect(s.drop).toBeGreaterThan(0);
    expect(screen.getByTestId("cliff-drop").textContent).toContain(gbp(s.drop));
    expect(screen.getByTestId("cliff-chart")).toBeTruthy();
  });

  it("fails closed when the example arrays do not line up", () => {
    render(<CliffTab data={mutate("cliff_example.earnings", data.cliff_example.earnings.slice(2))} />);
    expect(screen.getByTestId("unavailable")).toBeTruthy();
  });
});

describe("methodology", () => {
  it("shows the versions, every validation row and every limitation from the file", () => {
    render(<MethodTab data={data} />);
    expect(screen.getByTestId("versions-table").textContent).toContain(data.meta.dataset);
    const rows = within(screen.getByTestId("validation-table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(data.baseline_validation.length);
    expect(within(screen.getByTestId("limitations")).getAllByRole("listitem")).toHaveLength(data.limitations.length);
  });

  it("fails closed on a missing block without hiding the others", () => {
    render(<MethodTab data={mutate("baseline_validation", undefined, { remove: true })} />);
    expect(screen.getAllByTestId("unavailable")).toHaveLength(1);
    expect(screen.getByTestId("limitations")).toBeTruthy();
  });
});
