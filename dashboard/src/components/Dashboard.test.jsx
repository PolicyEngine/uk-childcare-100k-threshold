/**
 * Render contract against the committed results file: every number checked here is read from the file, so the same
 * tests pass on any valid results file. Invalid data never reaches the page: validateResults runs before the build,
 * and the readers throw rather than render a placeholder.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const searchParams = new URLSearchParams();
const router = { replace: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router, useSearchParams: () => searchParams }));

import Dashboard, { TAB_OPTIONS } from "./Dashboard";
import LandingTab, { CENTAX } from "./LandingTab";
import WhoGainsTab, { DECILE_MEASURES, listOf, SUPPRESSED } from "./WhoGainsTab";
import CliffTab from "./CliffTab";
import MethodTab from "./MethodTab";
import { cliffSummary, getCliff, LEAD_YEAR, ResultsError } from "../lib/dataHelpers";
import { formatThousands } from "../lib/formatters";
import { bn, BROKEN_TEXT, fy, gbp, mutate, realData as data } from "../lib/testUtils";

const years = data.meta.years;
const final = years.at(-1);
const total = (y) => data.budget.gross_bn.total[String(y)];

describe("the page", () => {
  it("renders every tab without broken or placeholder text", () => {
    const { container } = render(<Dashboard data={data} />);
    for (const tab of TAB_OPTIONS) {
      fireEvent.click(screen.getByRole("tab", { name: tab.label }));
      const text = container.textContent.replace(/\s+/g, " ");
      expect(text, tab.label).not.toMatch(BROKEN_TEXT);
      expect(text, tab.label).not.toMatch(/\bunavailable\b|\bnull\b|\bundefined\b/i);
    }
  });

  // The committed file predates the Microcosm-only rebuild; this runs once the rebuilt results.json is synced.
  it.skipIf(!/microcosm/i.test(data.meta.dataset))("names no second dataset anywhere on the page", () => {
    const { container } = render(<Dashboard data={data} />);
    for (const tab of TAB_OPTIONS) {
      fireEvent.click(screen.getByRole("tab", { name: tab.label }));
      expect(container.textContent, tab.label).not.toMatch(/cross-check|Enhanced FRS/i);
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

  it("throws on an invalid file rather than rendering part of it", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<LandingTab data={mutate(`budget.gross_bn.thirty_hours.${final}`, null)} />)).toThrow(ResultsError);
    expect(() => render(<MethodTab data={mutate("baseline_validation", undefined, { remove: true })} />)).toThrow(ResultsError);
    expect(() => render(<WhoGainsTab data={mutate("distribution", {})} />)).toThrow(ResultsError);
    expect(() => render(<CliffTab data={mutate("cliff_example.earnings", data.cliff_example.earnings.slice(2))} />)).toThrow(ResultsError);
    console.error.mockRestore();
  });
});

describe("budget impact", () => {
  it("leads with 2027-28: its cost, range, split and the families gaining, from the file", () => {
    render(<LandingTab data={data} />);
    const g = data.budget.gross_bn;
    const r = data.budget.range_bn;
    const card = screen.getByTestId("card-cost").textContent;
    expect(card).toContain(fy(LEAD_YEAR).replace("-", "‑"));
    expect(card).toContain(bn(total(LEAD_YEAR)));
    expect(card).toContain(`Range ${bn(r.low[LEAD_YEAR])} to ${bn(r.high[LEAD_YEAR])}`);
    expect(screen.getByTestId("card-split").textContent).toContain(`${bn(g.thirty_hours[LEAD_YEAR])} and ${bn(g.tax_free_childcare[LEAD_YEAR])}`);
    const rec = data.recipients[LEAD_YEAR];
    expect(screen.getByTestId("card-families").textContent).toContain(formatThousands(rec.families_gaining));
    if (rec.mean_gain_gbp !== null) expect(screen.getByTestId("card-families").textContent).toContain(gbp(rec.mean_gain_gbp));
  });

  it("labels 2026-27 illustrative in the tables", () => {
    render(<LandingTab data={data} />);
    expect(within(screen.getByTestId("sensitivity-table")).getAllByRole("columnheader").map((h) => h.textContent)).toContain("2026-27 (illustrative)");
  });

  it("compares like for like: our 30 hours cost against CenTax's static cost of the free hours", () => {
    render(<LandingTab data={data} />);
    const b = data.benchmarks[0];
    const card = screen.getByTestId("card-benchmark");
    expect(card.textContent).toContain(b.figure);
    expect(card.textContent).toMatch(/traces to CenTax's cost of the free hours only/);
    expect(within(card).getByRole("link").getAttribute("href")).toBe(b.url);
    const topic = screen.getByTestId("benchmark");
    expect(topic.textContent).toMatch(/covers both the free hours and Tax-Free Childcare/);
    expect(within(topic).getByRole("link", { name: /CenTax's report/ }).getAttribute("href")).toBe(b.underlying_source_url);
    expect(screen.getByTestId("benchmark-centax").textContent).toContain(bn(CENTAX.staticBn));
    const lfl = screen.getByTestId("benchmark-like-for-like").textContent;
    expect(lfl).toContain(bn(data.budget.gross_bn.thirty_hours[final]));
    expect(lfl).toContain(`${bn(CENTAX.staticBn)} in ${CENTAX.year}`);
  });

  it("shows every sensitivity, signed in £m, from the file", () => {
    render(<LandingTab data={data} />);
    const effects = Object.entries(data.budget.sensitivities.effects_bn);
    const rows = within(screen.getByTestId("sensitivity-table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(effects.length);
    effects.forEach(([id, v], i) => {
      const m = Math.round(v[years[0]] * 1000);
      expect(rows[i].textContent, id).toContain(`${m > 0 ? "+" : m < 0 ? "-" : ""}£${Math.abs(m).toLocaleString("en-GB")}m`);
      expect(rows[i].textContent, id).toContain(data.budget.sensitivities.descriptions[id]);
    });
  });

  it("shows the 30 hours components", () => {
    render(<LandingTab data={data} />);
    expect(within(screen.getByTestId("components-table")).getAllByRole("row").length).toBeGreaterThan(2);
  });
});

describe("who gains", () => {
  it("opens on 2027-28, draws the deciles and switches measure and year", () => {
    render(<WhoGainsTab data={data} />);
    expect(screen.getByLabelText("Year").value).toBe(String(LEAD_YEAR));
    expect(screen.getByTestId("decile-chart")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Show"), { target: { value: DECILE_MEASURES[2].id } });
    expect(screen.getByLabelText("Show").value).toBe(DECILE_MEASURES[2].id);
    fireEvent.change(screen.getByLabelText("Year"), { target: { value: String(years[0]) } });
    const r = data.recipients[years[0]];
    const rows = within(screen.getByTestId("scheme-table")).getAllByRole("row");
    expect(rows.find((x) => /Either or both/.test(x.textContent)).textContent).toContain(r.families_gaining.toLocaleString("en-GB"));
  });

  it("shows every nation and the scheme counts from the file, with suppressed cells as too few records", () => {
    render(<WhoGainsTab data={data} />);
    const countries = data.distribution[LEAD_YEAR].by_country;
    const rows = within(screen.getByTestId("country-table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(countries.length);
    countries.forEach((c, i) => {
      if (c.suppressed) {
        expect(rows[i].textContent).toContain(SUPPRESSED);
        expect(rows[i].textContent).not.toMatch(/£0m|\b0\b/);
      } else expect(rows[i].textContent).toContain(c.families_gaining.toLocaleString("en-GB"));
    });
    const s = within(screen.getByTestId("scheme-table")).getAllByRole("row").slice(1);
    expect(s[0].textContent).toContain(data.recipients[LEAD_YEAR].by_scheme.thirty_hours.toLocaleString("en-GB"));
    expect(s[1].textContent).toContain(data.recipients[LEAD_YEAR].by_scheme.tax_free_childcare.toLocaleString("en-GB"));
  });

  it("names the suppressed deciles instead of drawing them as zero", () => {
    render(<WhoGainsTab data={data} />);
    const hidden = data.distribution[LEAD_YEAR].by_decile.filter((r) => r.suppressed).map((r) => r.decile);
    if (hidden.length) expect(screen.getByTestId("deciles-suppressed").textContent).toContain(`${listOf(hidden)}: ${SUPPRESSED}`);
    else expect(screen.queryByTestId("deciles-suppressed")).toBeNull();
  });
});

describe("the cliff", () => {
  it("says the universal 15 hours stay when the limit is crossed", () => {
    render(<CliffTab data={data} />);
    const text = screen.getByTestId("cliff-explainer").textContent;
    expect(text).toMatch(/keeps\s+the universal 15/);
    expect(text).not.toMatch(/both the 30 funded hours/);
  });

  it("states the drop at £100,000 from the file", () => {
    render(<CliffTab data={data} />);
    const s = cliffSummary(getCliff(data));
    expect(s.drop).toBeGreaterThan(0);
    const text = screen.getByTestId("cliff-drop").textContent;
    expect(text).toContain(gbp(s.drop));
    expect(text).toContain(gbp(s.before.earnings));
    expect(text).toContain(gbp(s.after.earnings));
    expect(screen.getByTestId("cliff-chart")).toBeTruthy();
  });
});

describe("methodology", () => {
  it("shows the versions, every validation row and every limitation from the file", () => {
    render(<MethodTab data={data} />);
    expect(screen.getByTestId("versions-table").textContent).toContain(data.meta.dataset);
    const rows = within(screen.getByTestId("validation-table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(data.baseline_validation.length);
    expect(within(screen.getByTestId("assumptions-table")).getAllByRole("row").length).toBe(6);
    expect(within(screen.getByTestId("limitations")).getAllByRole("listitem")).toHaveLength(data.limitations.length);
  });

  it("does not call the take-up rates equal above and below £100,000", () => {
    render(<MethodTab data={data} />);
    expect(document.body.textContent).not.toMatch(/the same above and below £100,000/);
    expect(document.body.textContent).toMatch(/held fixed/);
  });

  it("shows the dataset provenance the file carries", () => {
    const withProvenance = mutate("meta.dataset_management", "Pinned by this repository");
    render(<MethodTab data={withProvenance} />);
    expect(screen.getByTestId("versions-table").textContent).toContain("Pinned by this repository");
  });
});
