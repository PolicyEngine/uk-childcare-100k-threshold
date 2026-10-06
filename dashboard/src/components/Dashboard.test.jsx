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
import WhoGainsTab, { DECILE_MEASURES, listOf, SUPPRESSED } from "./WhoGainsTab";
import CliffTab from "./CliffTab";
import MethodTab from "./MethodTab";
import { cliffSummary, getCliff, getValidation } from "../lib/dataHelpers";
import { formatThousands } from "../lib/formatters";
import { bn, BROKEN_TEXT, fy, gbp, mutate, realData as data, withSample } from "../lib/testUtils";

const years = data.meta.years;
const first = years[0];
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
  it("leads with the first year's cost, its range, its split and the families gaining, from the file", () => {
    render(<LandingTab data={data} />);
    const g = data.budget.gross_bn;
    const r = data.budget.range_bn;
    const card = screen.getByTestId("card-cost").textContent;
    expect(card).toContain(fy(first));
    expect(card).toContain(bn(total(first)));
    expect(card).toContain(`Range ${bn(r.low[first])} to ${bn(r.high[first])}`);
    expect(screen.getByTestId("card-split").textContent).toContain(`${bn(g.thirty_hours[first])} and ${bn(g.tax_free_childcare[first])}`);
    const rec = data.recipients[first];
    expect(screen.getByTestId("card-families").textContent).toContain(formatThousands(rec.families_gaining));
    expect(screen.getByTestId("card-families").textContent).toContain(gbp(rec.mean_gain_gbp));
  });

  it("labels the Conservatives' figure as the party's, as reported, and links the report", () => {
    render(<LandingTab data={data} />);
    const b = data.benchmarks[0];
    const card = screen.getByTestId("card-benchmark");
    expect(card.textContent).toContain(b.figure);
    expect(card.textContent).toMatch(/party's estimate as reported/);
    expect(card.textContent).toMatch(/based on CenTax.*not like for like/);
    expect(within(card).getByRole("link").getAttribute("href")).toBe(b.url);
  });

  it("attributes the figure to CenTax's estimate and says it is not like for like", () => {
    render(<LandingTab data={data} />);
    const panel = screen.getByTestId("comparisons");
    fireEvent.click(within(panel).getByRole("tab", { name: /Conservatives' figure/ }));
    const topic = screen.getByTestId("benchmark");
    expect(topic.textContent).toMatch(/based on CenTax's report/);
    expect(within(topic).getByRole("link", { name: /CenTax's report/ }).getAttribute("href")).toBe(data.benchmarks[0].underlying_source_url);
    expect(screen.getByTestId("benchmark-centax").textContent).toMatch(/£640m in 2030.*free childcare hours only/);
    expect(screen.getByTestId("benchmark-where").textContent).toMatch(/not like for like/);
  });

  it("shows every sensitivity, signed in £m, from the file", () => {
    render(<LandingTab data={data} />);
    const effects = Object.entries(data.budget.sensitivities.effects_bn);
    const rows = within(screen.getByTestId("sensitivity-table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(effects.length);
    effects.forEach(([id, v], i) => {
      const m = Math.round(v[first] * 1000);
      expect(rows[i].textContent, id).toContain(`${m > 0 ? "+" : m < 0 ? "-" : ""}£${Math.abs(m).toLocaleString("en-GB")}m`);
      expect(rows[i].textContent, id).toContain(data.budget.sensitivities.descriptions[id]);
    });
  });

  it("shows the Microcosm cross-check with its reason, and the 30 hours components", () => {
    render(<LandingTab data={data} />);
    const panel = screen.getByTestId("comparisons");
    fireEvent.click(within(panel).getByRole("tab", { name: /Microcosm cross-check/ }));
    const rows = within(screen.getByTestId("cross-check-table")).getAllByRole("row");
    expect(rows[1].textContent).toContain(bn(data.budget.cross_check.total[final]));
    expect(screen.getByTestId("cross-check-reason").textContent).toMatch(/more people on £100,000 or more than HMRC projects/);
    fireEvent.click(within(panel).getByRole("tab", { name: /Inside the 30 hours/ }));
    expect(within(screen.getByTestId("components-table")).getAllByRole("row").length).toBeGreaterThan(2);
  });

  it("fails closed when a cost is missing", () => {
    render(<LandingTab data={mutate(`budget.gross_bn.thirty_hours.${final}`, null)} />);
    expect(screen.getByTestId("unavailable")).toBeTruthy();
  });

  it("drops only the cross-check when it is missing", () => {
    render(<LandingTab data={mutate("budget.cross_check", undefined, { remove: true })} />);
    expect(screen.getByTestId("card-cost")).toBeTruthy();
    fireEvent.click(within(screen.getByTestId("comparisons")).getByRole("tab", { name: /Microcosm cross-check/ }));
    expect(screen.getByTestId("unavailable").textContent).toMatch(/cross-check is unavailable/);
  });

  it("drops only the sensitivities when they are missing", () => {
    render(<LandingTab data={mutate("budget.sensitivities", undefined, { remove: true })} />);
    expect(screen.getAllByTestId("unavailable")).toHaveLength(1);
    expect(screen.getByTestId("card-cost")).toBeTruthy();
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
    expect(rows.find((x) => /Either or both/.test(x.textContent)).textContent).toContain(r.families_gaining.toLocaleString("en-GB"));
  });

  it("shows every nation and the scheme counts from the file, with suppressed cells as too few records", () => {
    render(<WhoGainsTab data={data} />);
    const countries = data.distribution[final].by_country;
    const rows = within(screen.getByTestId("country-table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(countries.length);
    countries.forEach((c, i) => {
      if (c.suppressed) {
        expect(rows[i].textContent).toContain(SUPPRESSED);
        expect(rows[i].textContent).not.toMatch(/£0m|\b0\b/);
      } else expect(rows[i].textContent).toContain(c.families_gaining.toLocaleString("en-GB"));
    });
    const s = within(screen.getByTestId("scheme-table")).getAllByRole("row").slice(1);
    expect(s[0].textContent).toContain(data.recipients[final].by_scheme.thirty_hours.toLocaleString("en-GB"));
    expect(s[1].textContent).toContain(data.recipients[final].by_scheme.tax_free_childcare.toLocaleString("en-GB"));
  });

  it("never shows a single suppressed nation, so none can be worked out from the UK total", () => {
    for (const y of Object.keys(data.distribution)) {
      const n = data.distribution[y].by_country.filter((c) => c.suppressed).length;
      expect(n, y).not.toBe(1);
    }
  });

  it("names the suppressed deciles instead of drawing them as zero", () => {
    render(<WhoGainsTab data={data} />);
    const hidden = data.distribution[final].by_decile.filter((r) => r.suppressed).map((r) => r.decile);
    if (hidden.length) expect(screen.getByTestId("deciles-suppressed").textContent).toContain(`${listOf(hidden)}: ${SUPPRESSED}`);
    else expect(screen.queryByTestId("deciles-suppressed")).toBeNull();
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
  it("says the universal 15 hours stay when the limit is crossed", () => {
    render(<CliffTab data={data} />);
    const text = screen.getByTestId("cliff-explainer").textContent;
    expect(text).toMatch(/keeps\s+the universal 15/);
    expect(text).not.toMatch(/both the 30 funded hours/);
  });

  it("does not call the take-up rates equal above and below £100,000", () => {
    render(<MethodTab data={data} />);
    expect(document.body.textContent).not.toMatch(/the same above and below £100,000/);
    expect(document.body.textContent).toMatch(/held fixed/);
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

  it("fails closed when the example arrays do not line up", () => {
    render(<CliffTab data={mutate("cliff_example.earnings", data.cliff_example.earnings.slice(2))} />);
    expect(screen.getByTestId("unavailable")).toBeTruthy();
  });
});

describe("methodology", () => {
  it("shows the versions, every validation row and every limitation from the file", () => {
    render(<MethodTab data={data} />);
    expect(screen.getByTestId("versions-table").textContent).toContain(data.meta.dataset);
    const v = getValidation(data);
    const sets = [...new Set(v.map((r) => r.dataset))];
    for (const d of sets) {
      if (sets.length > 1) fireEvent.change(screen.getByLabelText("Source of the model figures"), { target: { value: d } });
      const rows = within(screen.getByTestId("validation-table")).getAllByRole("row").slice(1);
      expect(rows, d).toHaveLength(v.filter((r) => r.dataset === d).length);
    }
    expect(within(screen.getByTestId("assumptions-table")).getAllByRole("row").length).toBe(6);
    expect(within(screen.getByTestId("limitations")).getAllByRole("listitem")).toHaveLength(data.limitations.length);
  });

  it("fails closed on a missing block without hiding the others", () => {
    render(<MethodTab data={mutate("baseline_validation", undefined, { remove: true })} />);
    expect(screen.getAllByTestId("unavailable")).toHaveLength(1);
    expect(screen.getByTestId("limitations")).toBeTruthy();
  });
});
