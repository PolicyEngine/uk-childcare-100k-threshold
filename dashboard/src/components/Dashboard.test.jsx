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
import LandingTab, { rangeChartRows } from "./LandingTab";
import { CENTAX } from "./Comparison";
import WhoGainsTab, { DECILE_MEASURES, listOf, recipientViews, sortGroups, SUPPRESSED } from "./WhoGainsTab";
import MethodTab from "./MethodTab";
import { plainText, RichText } from "./ui";
import { cliffSummary, getHouseholdGrid, getUncertainty, householdRows, LEAD_YEAR, ResultsError } from "../lib/dataHelpers";
import { formatMoneyBn, formatThousands } from "../lib/formatters";
import { bn, BROKEN_TEXT, fy, gbp, mutate, realData as data, textOf } from "../lib/testUtils";

const years = data.meta.years;
const final = years.at(-1);
const total = (y) => data.budget.gross_bn.total[String(y)];
const takeUp = data.budget.take_up;
// Families and children gaining on the headline take-up basis, as Budget impact shows them.
const headlineRecipients = (y) => takeUp.bases[takeUp.headline].recipients[String(y)];

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

  it("names the policyengine.py version in the footer, from the file, and links the replication code", () => {
    render(<Dashboard data={data} />);
    const footer = screen.getByTestId("replication");
    expect(footer.textContent).toBe(
      `Built with policyengine.py ${data.meta.policyengine}. Replication code: PolicyEngine/uk-childcare-100k-threshold.`,
    );
    expect(within(footer).getByRole("link", { name: "PolicyEngine/uk-childcare-100k-threshold" }).getAttribute("href")).toBe(
      "https://github.com/PolicyEngine/uk-childcare-100k-threshold",
    );
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
    const rec = headlineRecipients(LEAD_YEAR);
    expect(screen.getByTestId("card-families").textContent).toContain(formatThousands(rec.families_gaining));
    if (rec.mean_gain_gbp !== null) expect(screen.getByTestId("card-families").textContent).toContain(gbp(rec.mean_gain_gbp));
  });

  it("switches the cards to the year whose bar is clicked", () => {
    render(<LandingTab data={data} />);
    fireEvent.click(within(screen.getByTestId("card-cost")).getByRole("button", { name: new RegExp(fy(final)) }));
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(total(final)));
    expect(screen.getByTestId("card-families").textContent).toContain(formatThousands(headlineRecipients(final).families_gaining));
  });

  it("shows one scheme in both cards when it is clicked, and both again on a second click", () => {
    render(<LandingTab data={data} />);
    const rec = headlineRecipients(LEAD_YEAR);
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
  it("shows the pinned versions, every validation row and every limitation from the file", () => {
    render(<MethodTab data={data} />);
    const versions = screen.getByTestId("method-step-versions").textContent;
    for (const k of ["policyengine", "policyengine_uk"]) expect(versions, k).toContain(data.meta[k]);
    const rows = within(screen.getByTestId("validation-table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(data.baseline_validation.length);
    // Every limitation in the file, plus the age profile, each a title and a one-sentence summary in one group.
    const group = screen.getByTestId("limitations");
    expect(group.children).toHaveLength(data.limitations.length + 1);
    for (const l of data.limitations) expect(group.textContent).toContain(`${l.title}. ${plainText(l.summary)}`);
  });

  it("shows every costing step inline, with no expanders, in about 200 words", () => {
    render(<MethodTab data={data} />);
    const card = document.getElementById("model");
    expect(card.querySelectorAll("details")).toHaveLength(0);
    expect(screen.getByTestId("method-steps").children).toHaveLength(5);
    expect(card.textContent.split(/\s+/).filter(Boolean).length).toBeLessThanOrEqual(210);
  });

  it("compares every modelling choice in one table, with each tested alternative's effect in £m from the file", () => {
    render(<MethodTab data={data} />);
    const table = screen.getByTestId("comparison-table");
    const final = years.at(-1);
    for (const a of data.modelling_assumptions.filter((x) => x.effect_bn || x.id === "static")) {
      // A long choice is shown as its key point with the detail on a second line.
      for (const part of a.ours.split(/: |; /)) expect(table.textContent, a.id).toContain(part);
      if (a.effect_bn) {
        const m = Math.round(a.effect_bn[final] * 1000);
        expect(table.textContent, a.id).toContain(`£${Math.abs(m).toLocaleString("en-GB")}m`);
        // The alternative it tests sits under the effect, as the one home for it.
        const cell = screen.getByTestId(`effect-${a.id}`);
        expect(cell.textContent).toContain(`£${Math.abs(m).toLocaleString("en-GB")}m`);
        expect(cell.textContent).toContain(a.alternative);
      }
    }
  });

  it("has no separate list of the choices: the comparison table and one method-notes link carry them", () => {
    render(<MethodTab data={data} />);
    expect(screen.queryByTestId("choices")).toBeNull();
    expect(screen.queryByTestId("effects-table")).toBeNull();
    const card = document.getElementById("assumptions");
    expect(within(card).getAllByRole("link", { name: /method notes on GitHub/i })).toHaveLength(1);
  });

  it("does not call the take-up rates equal above and below £100,000", () => {
    render(<MethodTab data={data} />);
    expect(document.body.textContent).not.toMatch(/the same above and below £100,000/);
  });

  it("keeps the labour supply sensitivities in the method notes, linked from the Sensitivities item", () => {
    render(<MethodTab data={data} />);
    const item = screen.getByTestId("ls-sensitivities");
    expect(within(item).getByRole("link", { name: "method notes on GitHub" }).getAttribute("href")).toMatch(/docs\/METHOD\.md$/);
  });

});

describe("the labour supply control", () => {
  const ls = data.labour_supply;
  const lead = String(LEAD_YEAR);

  it("opens static, and switching the hours response on changes the cost card and the URL", () => {
    router.replace.mockClear();
    render(<Dashboard data={data} />);
    // One response: partners moving into work is not published.
    expect(screen.queryByTestId("toggle-extensive")).toBeNull();
    expect(screen.getByTestId("toggle-intensive").getAttribute("aria-checked")).toBe("false");
    expect(screen.queryByTestId("toggle-intensive-bound")).toBeNull();
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(data.budget.gross_bn.total[lead]));

    fireEvent.click(screen.getByTestId("toggle-intensive"));
    const cost = data.budget.gross_bn.total[lead] - ls.intensive.offset_bn.central[lead];
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(cost));
    expect(screen.getByTestId("card-cost").textContent).toContain("(parents' hours)");
    expect(router.replace).toHaveBeenLastCalledWith("/?ls=int", { scroll: false });

    fireEvent.change(screen.getByTestId("toggle-intensive-bound"), { target: { value: "high" } });
    const high = data.budget.gross_bn.total[lead] - ls.intensive.offset_bn.high[lead];
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(high));
    expect(screen.getByTestId("card-cost").textContent).toContain("(parents' hours at the high setting)");
    expect(router.replace).toHaveBeenLastCalledWith("/?ls=int%3Ahigh", { scroll: false });
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
    expect(text).toContain(plainText(ls.responding_population));
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
    expect(text).toContain("OBR's income elasticities");
    expect(text).toContain(`price effect brings back ${formatMoneyBn(i.price_offset_bn.central[f])}`);
    expect(text).toContain(`${formatMoneyBn(i.over_limit.price_offset_bn.central[f])} from those over it`);
    expect(text).toContain(`income effect costs ${formatMoneyBn(-i.income_offset_bn.central[f])}`);
    expect(text).toContain(`a net ${formatMoneyBn(i.offset_bn.central[f])} back`);
    // The findings give the totals; the split by group is in the Method list's "Hours" item.
    expect(screen.queryByTestId("ls-intensive")).toBeNull();
  });

  it("fills the comparison's dynamic cost: hours with the range when off, the chosen setting when on", () => {
    const f = String(final);
    const off = textOf(<MethodTab data={data} />);
    // The key figure, then the range and what it covers on a second line.
    expect(off).toContain(`${bn(ls.dynamic_cost_bn.central[f])}${bn(ls.dynamic_cost_bn.high[f])} to ${bn(ls.dynamic_cost_bn.low[f])}`);
    expect(off).toContain("parents' hours only, net of the income effect");
    expect(ls.dynamic_cost_bn.central[f]).toBeCloseTo(data.budget.gross_bn.total[f] - ls.intensive.offset_bn.central[f], 3);
    const on = textOf(<MethodTab data={data} setting={{ intensive: true, bounds: { intensive: "low" } }} />);
    const cost = data.budget.gross_bn.total[f] - ls.intensive.offset_bn.low[f];
    expect(on).toContain(`${bn(cost)}parents' hours at the low setting`);
    // Nothing on the page reports partners moving into work as a result.
    expect(off).not.toMatch(/Partners moving into work:|Moving into work/);
  });

  it("shows the money back in the yearly chart only when the hours response is on", () => {
    expect(textOf(<LandingTab data={data} />)).not.toContain("Back from parents working more");
    expect(textOf(<LandingTab data={data} setting={{ intensive: true, bound: "central" }} />)).toContain(
      "Back from parents working more",
    );
  });
});

describe("the take-up control", () => {
  const lead = String(LEAD_YEAR);
  const basis = (id) => takeUp.bases[id];
  const select = () => screen.getByTestId("take-up-select");
  const choose = (id) => fireEvent.change(select(), { target: { value: id } });

  it("opens on the headline, DfE's rates by age, with each option's 30 hours cost in the drop-down", () => {
    render(<Dashboard data={data} />);
    expect(screen.getByLabelText("Take-up of the 30 hours among newly eligible families")).toBe(select());
    expect(select().value).toBe(takeUp.headline);
    const options = within(select()).getAllByRole("option");
    expect(options.map((o) => o.value)).toEqual(takeUp.order);
    for (const [k, id] of takeUp.order.entries()) {
      expect(options[k].textContent).toContain(basis(id).short_label);
      expect(options[k].textContent).toContain(bn(basis(id).gross_bn.thirty_hours[lead]));
    }
    expect(options[takeUp.order.indexOf(takeUp.headline)].textContent).toContain("(headline)");
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(total(LEAD_YEAR)));
  });

  it("explains every option once, with its source, in a box closed by default", () => {
    render(<Dashboard data={data} />);
    const box = screen.getByTestId("take-up-options");
    expect(box.tagName).toBe("DETAILS");
    expect(box.open).toBe(false);
    for (const id of takeUp.order) {
      const item = within(box).getByTestId(`take-up-option-${id}`);
      expect(item.textContent).toContain(basis(id).description);
      expect(within(item).getByRole("link", { name: basis(id).source }).getAttribute("href")).toBe(basis(id).source_url);
    }
    // DfE's rates appear once on Budget impact: in this box ("42% at 9-11 months" is the first of them).
    const first = basis(takeUp.headline).rates_text.split(",")[0];
    expect(document.body.textContent.split(first).length - 1).toBe(1);
  });

  it.each(["centax", "contract"])("switches the headline figures to %s and keeps it in the URL", (id) => {
    router.replace.mockClear();
    render(<Dashboard data={data} />);
    choose(id);
    expect(select().value).toBe(id);
    const g = basis(id).gross_bn;
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(g.total[lead]));
    expect(screen.getByTestId("card-split").textContent).toContain(`${bn(g.thirty_hours[lead])} and ${bn(g.tax_free_childcare[lead])}`);
    expect(screen.getByTestId("card-families").textContent).toContain(formatThousands(basis(id).recipients[lead].families_gaining));
    const phrase = { centax: "CenTax's take-up rates", contract: "one flat take-up rate" }[id];
    expect(screen.getByTestId("uncertainty-table").textContent).toContain(`With ${phrase}`);
    expect(screen.getByTestId("range-legend-central").textContent).toBe(`Our estimate, with ${phrase}`);
    expect(document.getElementById("uncertainty").textContent).toContain(`using ${phrase}`);
    if (id === "centax") expect(screen.getByTestId("range-legend-centax").textContent).toBe("CenTax's own estimate (static)");
    expect(router.replace).toHaveBeenLastCalledWith(`/?takeup=${id}`, { scroll: false });
    // Back to the headline: the URL is clean again.
    choose(takeUp.headline);
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(total(LEAD_YEAR)));
    expect(router.replace).toHaveBeenLastCalledWith("/", { scroll: false });
  });

  it("explains take-up on Methodology, with the flat rate's per-point effect and links to the options", () => {
    render(<MethodTab data={data} />);
    const step = screen.getByTestId("method-take-up");
    expect(step.id).toBe("take-up-method");
    expect(step.textContent).toContain(`£${basis("contract").per_point_m[lead]}m`);
    expect(within(step).getByRole("link", { name: "Budget impact" }).getAttribute("href")).toBe("?tab=budget#take-up-options");
  });

  it("groups the boxes under the range chart, with no pointer line to Methodology under them", () => {
    render(<LandingTab data={data} />);
    const group = screen.getByTestId("uncertainty-notes");
    expect(group.className).toContain("expandable-group");
    expect([...group.children].map((c) => c.dataset.testid)).toEqual(["uncertainty-expandable", "note-range"]);
    expect(screen.queryByTestId("take-up-note")).toBeNull();
    expect(screen.queryByTestId("note-age")).toBeNull();
    expect(screen.queryByTestId("uncertainty-method-link")).toBeNull();
  });

  it("adds the labour supply response to the chosen basis's cost", () => {
    render(<Dashboard data={data} />);
    choose("centax");
    fireEvent.click(screen.getByTestId("toggle-intensive"));
    const cost = basis("centax").gross_bn.total[lead] - data.labour_supply.intensive.offset_bn.central[lead];
    expect(screen.getByTestId("card-cost").textContent).toContain(bn(cost));
  });

  it("opens on the basis the URL names, and shows only on Budget impact", () => {
    searchParams.set("takeup", "contract");
    try {
      render(<Dashboard data={data} />);
      expect(select().value).toBe("contract");
      expect(screen.getByTestId("card-cost").textContent).toContain(bn(basis("contract").gross_bn.total[lead]));
      fireEvent.click(screen.getByRole("tab", { name: "Who gains" }));
      expect(screen.queryByTestId("take-up-control")).toBeNull();
      fireEvent.click(screen.getByRole("tab", { name: "Methodology" }));
      expect(screen.queryByTestId("take-up-control")).toBeNull();
      // The comparison stays on the headline, whose effects its rows measure, whatever the basis chosen.
      const table = screen.getByTestId("comparison-table").textContent;
      const f = String(final);
      const staticCell = screen.getByTestId("static-cell").textContent;
      expect(staticCell.startsWith(bn(basis(takeUp.headline).gross_bn.total[f]))).toBe(true);
      expect(staticCell).toContain(`take-up: ${basis(takeUp.headline).label}`);
      expect(table).not.toContain(`${bn(basis("contract").gross_bn.total[f])}30 hours`);
      expect(screen.getByTestId("dynamic-cell").textContent).toContain(bn(data.labour_supply.dynamic_cost_bn.central[f]));
    } finally {
      searchParams.delete("takeup");
    }
  });

  it("works without the control: each tab alone shows the headline", () => {
    const g = takeUp.bases[takeUp.headline].gross_bn;
    expect(textOf(<LandingTab data={data} />)).toContain(bn(g.total[lead]));
    expect(textOf(<MethodTab data={data} />)).toContain(bn(g.total[String(final)]));
    // On Methodology the rates are stated once, in the comparison table's take-up row.
    const method = textOf(<MethodTab data={data} />);
    expect(method.split(basis(takeUp.headline).rates_text).length - 1).toBe(1);
  });
});

describe("the range chart", () => {
  it("draws, for each year, the 30 hours and both schemes from the file, with CenTax on the 30 hours and no single draw", () => {
    const u = data.budget.uncertainty.by_year;
    const centax = data.benchmarks[0].underlying_static_by_year_bn;
    const rows = rangeChartRows(getUncertainty(data), centax);
    expect(rows).toHaveLength(2 * Object.keys(u).length);
    for (const [y, v] of Object.entries(u)) {
      const [thirty, both] = rows.filter((r) => r.key.startsWith(y));
      expect(thirty.range).toEqual([v[takeUp.headline].thirty_hours.p5_bn, v[takeUp.headline].thirty_hours.p95_bn]);
      expect(both.range).toEqual([v[takeUp.headline].total.p5_bn, v[takeUp.headline].total.p95_bn]);
      expect(thirty.central).toBe(takeUp.bases[takeUp.headline].gross_bn.thirty_hours[y]);
      expect(both.central).toBe(takeUp.bases[takeUp.headline].gross_bn.total[y]);
      expect(thirty.centax).toBe(centax[y] ?? null);
      expect("single" in thirty).toBe(false);
      expect(both.centax).toBeNull();
    }
    render(<LandingTab data={data} />);
    const chart = screen.getByTestId("range-chart");
    expect(within(chart).getByRole("img").getAttribute("aria-describedby")).toBe("range-chart-desc");
    expect(document.getElementById("range-chart-desc").textContent).toContain(bn(rows[0].range[0]));
  });

  it("shows one leg at a time, the 30 hours by default, with only that leg's markers and numbers", () => {
    render(<LandingTab data={data} />);
    const n = Object.keys(data.budget.uncertainty.by_year).length;
    const select = screen.getByTestId("range-leg-select");
    const rowCount = () => document.getElementById("range-chart-desc").textContent.split(";").length;
    const legend = () => ["band", "central", "centax", "single"].filter((id) => screen.queryByTestId(`range-legend-${id}`));
    const tableLabels = () => [...screen.getByTestId("uncertainty-table").querySelectorAll("tbody td:first-child")].map((td) => td.textContent);
    expect(select.value).toBe("thirty_hours");
    expect(rowCount()).toBe(n);
    expect(legend()).toEqual(["band", "central", "centax"]);
    expect(tableLabels().every((l) => l.startsWith("30 hours"))).toBe(true);
    fireEvent.change(select, { target: { value: "total" } });
    expect(rowCount()).toBe(n);
    expect(document.getElementById("range-chart-desc").textContent).not.toContain("CenTax");
    expect(legend()).toEqual(["band", "central"]);
    expect(tableLabels()).toEqual(["Both schemes: our standard deviation", "Both schemes: our likely range (90% of resamples)"]);
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


describe("links in the results file's text", () => {
  it("renders [label](url) as links: external in a new tab, internal in the same one", () => {
    render(<p data-testid="rt"><RichText text="See [the law](https://www.legislation.gov.uk/uksi/2015/448/regulation/15) and [below](#validation)." /></p>);
    const [ext, int] = within(screen.getByTestId("rt")).getAllByRole("link");
    expect(ext.getAttribute("target")).toBe("_blank");
    expect(ext.getAttribute("rel")).toContain("noopener");
    expect(int.getAttribute("target")).toBeNull();
    expect(screen.getByTestId("rt").textContent).toBe("See the law and below.");
    expect(plainText("a [b](c) d")).toBe("a b d");
  });

  it("leaves no raw markup on any tab", () => {
    for (const Tab of [LandingTab, WhoGainsTab, MethodTab]) {
      expect(textOf(<Tab data={data} />)).not.toMatch(/\]\((https?:|\?|#)/);
    }
  });
});

describe("who gains: the intros", () => {
  it("says the single-draw point once on the tab", () => {
    const text = textOf(<WhoGainsTab data={data} />);
    expect(text.split("single draw of who claims").length - 1).toBe(1);
    expect(text).toContain(`as the higher earner's pay rises to £140,000.`);
  });
});
