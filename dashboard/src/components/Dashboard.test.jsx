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
import LandingTab from "./LandingTab";
import { CENTAX } from "./Comparison";
import WhoGainsTab, { DECILE_MEASURES, listOf, recipientViews, sortGroups, SUPPRESSED } from "./WhoGainsTab";
import MethodTab from "./MethodTab";
import { cliffSummary, getHouseholdGrid, householdRows, LEAD_YEAR, ResultsError } from "../lib/dataHelpers";
import { formatBn, formatMoneyBn, formatThousands } from "../lib/formatters";
import { bn, BROKEN_TEXT, fy, gbp, mutate, realData as data, textOf } from "../lib/testUtils";

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

  it("names the policyengine.py version and the dataset in the footer, from the file", () => {
    render(<Dashboard data={data} />);
    const text = screen.getByTestId("replication").textContent;
    expect(text).toContain(`policyengine.py ${data.meta.policyengine} on Microcosm UK 2024-25. Replication code`);
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
    expect(() => render(<WhoGainsTab data={mutate("household_grid.earnings", data.household_grid.earnings.slice(2))} />)).toThrow(ResultsError);
    console.error.mockRestore();
  });
});

describe("budget impact", () => {
  it("leads with 2027-28: its cost, split and the families gaining, from the file", () => {
    render(<LandingTab data={data} />);
    const g = data.budget.gross_bn;
    const card = screen.getByTestId("card-cost").textContent;
    expect(card).toContain(fy(LEAD_YEAR).replace("-", "‑"));
    expect(card).toContain(bn(total(LEAD_YEAR)));
    expect(card).not.toMatch(/Range/);
    expect(screen.getByTestId("card-split").textContent).toContain(`${bn(g.thirty_hours[LEAD_YEAR])} and ${bn(g.tax_free_childcare[LEAD_YEAR])}`);
    const rec = data.recipients[LEAD_YEAR];
    expect(screen.getByTestId("card-families").textContent).toContain(formatThousands(rec.families_gaining));
    if (rec.mean_gain_gbp !== null) expect(screen.getByTestId("card-families").textContent).toContain(gbp(rec.mean_gain_gbp));
  });

  it("switches the cards to the year whose bar is clicked", () => {
    render(<LandingTab data={data} />);
    fireEvent.click(within(screen.getByTestId("card-cost")).getByRole("button", { name: new RegExp(fy(final)) }));
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(total(final)));
    expect(screen.getByTestId("card-families").textContent).toContain(formatThousands(data.recipients[final].families_gaining));
  });

  it("shows one scheme in both cards when it is clicked, and both again on a second click", () => {
    render(<LandingTab data={data} />);
    const rec = data.recipients[LEAD_YEAR];
    const bar = () => within(screen.getByTestId("card-families")).getByRole("button", { name: /^Tax-Free Childcare/ });
    fireEvent.click(bar());
    expect(screen.getByTestId("card-families").textContent).toContain(formatThousands(rec.by_scheme.tax_free_childcare));
    expect(screen.getByTestId("card-split").textContent).toContain(bn(data.budget.gross_bn.tax_free_childcare[LEAD_YEAR]));
    fireEvent.click(bar());
    expect(screen.getByTestId("card-families").textContent).toContain(formatThousands(rec.families_gaining));
  });

  it("labels 2026-27 illustrative where years are chosen", () => {
    render(<WhoGainsTab data={data} />);
    const options = within(screen.getByTestId("year-select")).getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("2026-27 (illustrative)");
  });

  it("compares like for like: our 30 hours cost against CenTax's static cost of the free hours", () => {
    render(<MethodTab data={data} />);
    const b = data.benchmarks[0];
    const topic = screen.getByTestId("benchmark");
    expect(within(topic).getByRole("link", { name: "City AM" }).getAttribute("href")).toBe(b.url);
    expect(topic.textContent).toMatch(/covers both the free hours and Tax-Free Childcare/);
    expect(within(topic).getByRole("link", { name: /CenTax's report/ }).getAttribute("href")).toBe(b.underlying_source_url);
    const table = screen.getByTestId("comparison-table").textContent;
    expect(table).toContain(bn(data.budget.gross_bn.thirty_hours[final]));
    expect(table).toContain(bn(data.budget.gross_bn.total[final]));
    expect(table).toContain(bn(CENTAX.staticBn));
    expect(screen.getByTestId("benchmark-like-for-like").textContent).toMatch(/like-for-like pair/);
  });

});

describe("who gains", () => {
  it("opens on 2027-28, draws the deciles and switches measure and year", () => {
    render(<WhoGainsTab data={data} />);
    expect(screen.getByLabelText("Year").value).toBe(String(LEAD_YEAR));
    expect(screen.getByTestId("decile-chart")).toBeTruthy();
    const show = within(screen.getByTestId("section-breakdown")).getByLabelText("Show");
    fireEvent.change(show, { target: { value: DECILE_MEASURES[2].id } });
    expect(show.value).toBe(DECILE_MEASURES[2].id);
    fireEvent.change(screen.getByLabelText("Year"), { target: { value: String(years[0]) } });
    const r = data.recipients[years[0]];
    const rows = within(screen.getByTestId("scheme-table")).getAllByRole("row");
    expect(rows.find((x) => /Either or both/.test(x.textContent)).textContent).toContain(r.families_gaining.toLocaleString("en-GB"));
  });

  it("breaks the gains down by region and family type from the file, with suppressed cells as too few records", () => {
    render(<WhoGainsTab data={data} />);
    for (const [id, key, name] of [["region", "by_region", "region"], ["family_type", "by_family_type", "family_type"]]) {
      fireEvent.change(screen.getByLabelText("Break down by"), { target: { value: id } });
      const cells = sortGroups(data.distribution[LEAD_YEAR][key], "total_change_bn");
      const rows = within(screen.getByTestId("group-table")).getAllByRole("row").slice(1);
      expect(rows).toHaveLength(cells.length);
      cells.forEach((c, i) => {
        expect(rows[i].textContent).toContain(c[name]);
        if (c.suppressed) {
          expect(rows[i].textContent).toContain(SUPPRESSED);
          expect(rows[i].textContent).not.toMatch(/£0m|\b0\b/);
        } else expect(rows[i].textContent).toContain(c.families_gaining.toLocaleString("en-GB"));
      });
      expect(within(screen.getByTestId("section-breakdown")).getByTestId("group-chart")).toBeTruthy();
    }
  });

  it("splits families gaining by which parent is over £100,000, and shows the partner not working, from the file", () => {
    render(<WhoGainsTab data={data} />);
    const g = data.gender[LEAD_YEAR];
    const section = screen.getByTestId("section-gender");
    const shown = g.families_gaining_by_earner.filter((c) => !c.suppressed);
    expect(shown.reduce((t, c) => t + c.families_gaining, 0)).toBeLessThanOrEqual(data.recipients[LEAD_YEAR].families_gaining);
    for (const p of g.partner_not_working.filter((c) => !c.suppressed))
      expect(within(section).getByTestId("partner-not-working").textContent).toContain(`${Math.round(p.partner_not_working_pct)}%`);
  });

  it("draws the families and children gaining, with the scheme counts from the file", () => {
    render(<WhoGainsTab data={data} />);
    expect(screen.getByTestId("recipients-chart")).toBeTruthy();
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

describe("your household", () => {
  it("says the universal 15 hours stay when the limit is crossed", () => {
    render(<WhoGainsTab data={data} />);
    const text = screen.getByTestId("section-household").textContent;
    expect(text).toMatch(/keeps\s+the universal 15/);
    expect(text).not.toMatch(/both the 30 funded hours/);
  });

  it("opens on the default family, which hits the cliff, and states the drop from the file", () => {
    render(<WhoGainsTab data={data} />);
    const grid = getHouseholdGrid(data);
    const s = cliffSummary(householdRows(grid, grid.default));
    expect(s.drop).toBeGreaterThan(0);
    const text = screen.getByTestId("cliff-drop").textContent;
    expect(text).toContain(gbp(s.drop));
    expect(text).toContain(gbp(s.before.earnings));
    expect(text).toContain(gbp(s.after.earnings));
    expect(screen.getByTestId("cliff-chart")).toBeTruthy();
  });

  it("redraws for every family the form offers", () => {
    render(<WhoGainsTab data={data} />);
    const grid = getHouseholdGrid(data);
    for (const p of grid.options.parents) {
      fireEvent.change(screen.getByLabelText("Parents"), { target: { value: p.id } });
      const s = cliffSummary(householdRows(grid, { ...grid.default, parent: p.id }));
      const text = screen.getByTestId("cliff-drop").textContent;
      if (s.drop > 0) expect(text).toContain(gbp(s.drop));
      else expect(text).toMatch(/does not lose income/);
    }
  });
});

describe("methodology", () => {
  it("shows the versions, every validation row and every limitation from the file", () => {
    render(<MethodTab data={data} />);
    expect(screen.getByTestId("versions-table").textContent).toContain(data.meta.dataset_label);
    const rows = within(screen.getByTestId("validation-table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(data.baseline_validation.length);
    expect(within(screen.getByTestId("assumptions-table")).getAllByRole("row").length).toBe(6);
    expect(within(screen.getByTestId("limitations")).getAllByRole("listitem")).toHaveLength(data.limitations.length);
  });

  it("compares every modelling choice in one table, with each tested alternative's effect in £m from the file", () => {
    render(<MethodTab data={data} />);
    const table = screen.getByTestId("comparison-table");
    const final = years.at(-1);
    for (const a of data.modelling_assumptions.filter((x) => x.effect_bn || x.id === "static")) {
      expect(table.textContent, a.id).toContain(a.ours);
      if (a.effect_bn) {
        const m = Math.round(a.effect_bn[final] * 1000);
        expect(table.textContent, a.id).toContain(`£${Math.abs(m).toLocaleString("en-GB")}m`);
        const row = screen.getByTestId(`effect-${a.id}`);
        const m0 = Math.round(a.effect_bn[years[0]] * 1000);
        expect(row.textContent).toContain(`£${Math.abs(m0).toLocaleString("en-GB")}m`);
      }
    }
  });

  it("does not call the take-up rates equal above and below £100,000", () => {
    render(<MethodTab data={data} />);
    expect(document.body.textContent).not.toMatch(/the same above and below £100,000/);
    expect(document.body.textContent).toMatch(/held fixed/);
  });

  it("reports the entry and income-basis sensitivities of the labour supply response", () => {
    render(<MethodTab data={data} />);
    const text = screen.getByTestId("labour-supply-method").textContent;
    const ls = data.labour_supply;
    const y = String(Object.keys(ls.extensive.offset_bn.central).at(-1));
    const b3 = (x) => formatBn(x, 3);
    const m = (x) => `£${Math.abs(x).toFixed(1)}m`;
    expect(text).toContain(m(ls.extensive.entry_sensitivity.same_cell_only.offset_m[y]));
    expect(text).toContain(m(ls.extensive.entry_sensitivity.worker_profile.offset_m[y]));
    expect(text).toContain(b3(ls.intensive_income_basis.paid_care_fixed_spend.offset_bn[y]));
    expect(text).toContain(b3(ls.intensive_income_basis.government_cost.offset_bn[y]));
    expect(text).toMatch(/top-up the family no longer gets/);
  });

  it("pins the model package and the dataset release, revision and checksum", () => {
    render(<MethodTab data={data} />);
    const text = screen.getByTestId("versions-table").textContent;
    for (const k of ["policyengine", "policyengine_uk", "dataset_release", "dataset_revision", "dataset_sha256"]) expect(text, k).toContain(data.meta[k]);
  });
});

describe("the labour supply control", () => {
  const ls = data.labour_supply;
  const lead = String(LEAD_YEAR);

  it("opens static, and switching a margin on changes the cost card and the URL", () => {
    router.replace.mockClear();
    render(<Dashboard data={data} />);
    expect(screen.getByTestId("toggle-extensive").getAttribute("aria-checked")).toBe("false");
    expect(screen.getByTestId("toggle-intensive").getAttribute("aria-checked")).toBe("false");
    expect(screen.queryByTestId("toggle-extensive-bound")).toBeNull();
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(data.budget.gross_bn.total[lead]));

    fireEvent.click(screen.getByTestId("toggle-intensive"));
    const cost = data.budget.gross_bn.total[lead] - ls.intensive.offset_bn.central[lead];
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(cost));
    expect(screen.getByTestId("card-cost").textContent).toContain("(hours)");
    expect(router.replace).toHaveBeenLastCalledWith("/?ls=int", { scroll: false });

    fireEvent.click(screen.getByTestId("toggle-extensive"));
    fireEvent.change(screen.getByTestId("toggle-extensive-bound"), { target: { value: "high" } });
    fireEvent.change(screen.getByTestId("toggle-intensive-bound"), { target: { value: "high" } });
    const both = data.budget.gross_bn.total[lead] - ls.extensive.offset_bn.high[lead] - ls.intensive.offset_bn.high[lead];
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(both));
    expect(router.replace).toHaveBeenLastCalledWith("/?ls=ext%3Ahigh%2Cint%3Ahigh", { scroll: false });
  });

  it("sits under the tab bar on Budget impact only, the one tab it changes", () => {
    render(<Dashboard data={data} />);
    const tablist = screen.getByRole("tablist");
    const control = screen.getByTestId("labour-supply-control");
    // Below the tabs: the tab bar precedes the control in document order.
    expect(tablist.compareDocumentPosition(control) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByTestId("intro").contains(control)).toBe(false);

    fireEvent.click(screen.getByRole("tab", { name: "Who gains" }));
    expect(screen.queryByTestId("labour-supply-control")).toBeNull();

    fireEvent.click(screen.getByRole("tab", { name: "Methodology" }));
    expect(screen.queryByTestId("labour-supply-control")).toBeNull();
  });

  it("explains labour supply on Methodology from the results file", () => {
    const text = textOf(<MethodTab data={data} />);
    expect(text).toContain(ls.responding_population);
    expect(text).toContain(String(ls.assumptions.hours_price_elasticity));
    expect(text).toContain(ls.not_modelled);
    expect(text).toContain(bn(CENTAX.parentsBn));
    expect(text).toContain(bn(CENTAX.partnersBn));
  });

  it("states the hours response's price effect (money back) and income effect (money out) by group", () => {
    const text = textOf(<MethodTab data={data} />);
    const f = String(final);
    const i = ls.intensive;
    expect(i.price_offset_bn.central[f]).toBeGreaterThanOrEqual(0);
    expect(i.income_offset_bn.central[f]).toBeLessThanOrEqual(0);
    expect(text).toContain(ls.assumptions.income_elasticities);
    expect(text).toContain(`price effect brings back ${formatMoneyBn(i.price_offset_bn.central[f])}`);
    expect(text).toContain(`${formatMoneyBn(i.over_limit.price_offset_bn.central[f])} from those over it`);
    expect(text).toContain(`income effect costs ${formatMoneyBn(-i.income_offset_bn.central[f])}`);
    expect(text).toContain(`a net ${formatMoneyBn(i.offset_bn.central[f])} back`);
  });

  it("fills the comparison's dynamic cost: both margins with the range when off, the chosen margins when on", () => {
    const f = String(final);
    const off = textOf(<MethodTab data={data} />);
    expect(off).toContain(`${bn(ls.dynamic_cost_bn.central[f])} (${bn(ls.dynamic_cost_bn.high[f])} to ${bn(ls.dynamic_cost_bn.low[f])}`);
    expect(off).toContain("moving into work, and hours net of the income effect; bunching not modelled");
    const on = textOf(<MethodTab data={data} setting={{ extensive: true, intensive: false, bound: "low" }} />);
    const cost = data.budget.gross_bn.total[f] - ls.extensive.offset_bn.low[f];
    expect(on).toContain(`${bn(cost)} (moving into work at the low setting)`);
  });

  it("shows the money back in the yearly chart only when a margin is on", () => {
    expect(textOf(<LandingTab data={data} />)).not.toContain("Back from parents working more");
    expect(textOf(<LandingTab data={data} setting={{ extensive: true, intensive: true, bound: "central" }} />)).toContain(
      "Back from parents working more",
    );
  });
});

describe("who gains: the recipients view across years", () => {
  it("falls back to families when the chosen year has no child counts by scheme", () => {
    const final = String(years.at(-1));
    const partial = mutate(`recipients.${final}.children_by_scheme`, null, { remove: true });
    expect(recipientViews(partial.recipients[final]).map((v) => v.id)).toEqual(["families"]);
    render(<WhoGainsTab data={partial} />);
    const section = screen.getByTestId("section-recipients");
    fireEvent.change(within(section).getByLabelText("Show"), { target: { value: "children" } });
    // Switching to a year without children_by_scheme must not crash, and shows families.
    expect(() => fireEvent.change(screen.getByLabelText("Year"), { target: { value: final } })).not.toThrow();
    expect(within(section).getByLabelText("Show").value).toBe("families");
    expect(within(section).getByTestId("recipients-chart")).toBeTruthy();
    // Back to a year with child counts, the reader's choice returns.
    fireEvent.change(screen.getByLabelText("Year"), { target: { value: String(LEAD_YEAR) } });
    expect(within(section).getByLabelText("Show").value).toBe("children");
  });
});

