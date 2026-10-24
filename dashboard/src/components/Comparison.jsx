"use client";

import {
  fyLabel,
  getBenchmarks,
  getBudget,
  getLabourSupply,
  getModellingAssumptions,
  getTakeUp,
  isStatic,
  labourSupplyLabel,
  labourSupplyOffset,
  STATIC_SETTING,
} from "../lib/dataHelpers";
import { formatBn } from "../lib/formatters";

const nb = (year) => fyLabel(year).replace("-", "\u2011");

export const CENTAX = { year: 2030, staticBn: 0.98, netBn: 0.64, parentsBn: 0.21, partnersBn: 0.13 };
// Their £0.34bn behavioural gain: £0.21bn of tax from parents who stop holding income below £100,000 (intensive
// margin) and £0.13bn of tax and NI from partners entering work (extensive margin).
// CenTax, Removing the childcare cliff-edge (September 2026), Table 4.2, 2030 (= tax year 2029-30), free hours only.
// Negative net = the reform raises money once behaviour is allowed for.
export const CENTAX_SCENARIOS = [
  { id: "central", label: "CenTax, central scenario", staticBn: 0.98, netBn: 0.64 },
  { id: "high", label: "CenTax, high-cost scenario", staticBn: 1.01, netBn: 0.77 },
  { id: "low", label: "CenTax, low-cost scenario", staticBn: 0.7, netBn: -0.16 },
];

export function BenchmarkNotes({ data }) {
  const benchmark = getBenchmarks(data)[0];
  return (
    <div className="space-y-3" data-testid="benchmark">
      <p>
        The Conservatives put the cost at about £700m a year when they announced the pledge, to be paid for by
        cutting staff at arm&apos;s-length public bodies. Their{" "}
        <a href={benchmark.announcement_url} target="_blank" rel="noreferrer">
          announcement
        </a>{" "}
        covers both the free hours and Tax-Free Childcare, but publishes no method.{" "}
        <a href={benchmark.url} target="_blank" rel="noreferrer">
          City AM
        </a>{" "}
        says the figure is based on{" "}
        <a href={benchmark.underlying_source_url} target="_blank" rel="noreferrer">
          CenTax&apos;s report
        </a>
        , which costs removing the limit on the free childcare hours only, and that adding Tax-Free Childcare
        &ldquo;pushed up the costs slightly&rdquo;.
      </p>
      <p data-testid="benchmark-like-for-like">
        Compare figures on the same basis. Our 30 hours cost and CenTax&apos;s static cost both cover the free hours
        before any change in how much parents work, so they are the like-for-like pair. CenTax&apos;s net figures
        allow for parents earning more once the limit goes (fewer keep their income just below £100,000) and partners
        moving into work, which brings in extra tax. The party&apos;s £0.7bn is close to CenTax&apos;s central net
        figure plus a small addition for Tax-Free Childcare. CenTax label tax years by their later year, so their
        2030 is 2029-30.
      </p>
    </div>
  );
}


const SI_2022_1134_URL = "https://www.legislation.gov.uk/uksi/2022/1134";

/** £bn as a signed £m figure. */
const signedM = (v) => {
  const m = Math.round(v * 1000);
  return `${m > 0 ? "+" : m < 0 ? "-" : ""}£${Math.abs(m).toLocaleString("en-GB")}m`;
};

const Link = ({ href, children }) => (
  <a href={href} target="_blank" rel="noreferrer">
    {children}
  </a>
);

/**
 * One table: the cost and every modelling choice, PolicyEngine against CenTax, the Conservatives and the official
 * sources or the law. The effect column is what changing our choice to the tested alternative does to the cost in
 * the final year.
 */
/**
 * Our cost once parents change how much they work, in the final year. With the labour supply control off it shows
 * both margins at central elasticities with the low-high range; with it on, the margins and elasticities chosen.
 */
export function dynamicCell(data, setting, basis) {
  const takeUp = getTakeUp(data);
  const id = basis ?? takeUp.headline;
  const budget = getBudget(data, id);
  const li = budget.years.length - 1;
  const ls = getLabourSupply(data);
  if (isStatic(setting)) {
    // The published dynamic cost is the headline's; on another take-up basis it is that basis's static cost less the
    // same offsets.
    const total = budget.rows[li].total;
    const d = id === takeUp.headline
      ? Object.fromEntries(["central", "low", "high"].map((b) => [b, ls.dynamic[b][li]]))
      : Object.fromEntries(["central", "low", "high"].map((b) => [b, total - ls.extensive.offset[b][li] - ls.intensive.offset[b][li]]));
    return `${formatBn(d.central, 2)} (${formatBn(d.high, 2)} to ${formatBn(d.low, 2)}, an illustrative range; moving into work, and hours net of the income effect; bunching not modelled)`;
  }
  const cost = budget.rows[li].total - labourSupplyOffset(data, setting)[li];
  return `${formatBn(cost, 2)} (${labourSupplyLabel(setting)})`;
}

export function UnifiedComparison({ data, setting = STATIC_SETTING, basis }) {
  const takeUp = getTakeUp(data);
  const chosen = takeUp.bases[basis ?? takeUp.headline];
  const budget = getBudget(data, chosen.id);
  const last = budget.rows.at(-1);
  const li = budget.years.length - 1;
  const a = Object.fromEntries(getModellingAssumptions(data).map((r) => [r.id, r]));
  const [central, high, low] = ["central", "high", "low"].map((id) => CENTAX_SCENARIOS.find((c) => c.id === id));
  const net = (v) => (v < 0 ? `raises ${formatBn(-v, 2)}` : formatBn(v, 2));
  const eff = (id) => (a[id]?.effects ? signedM(a[id].effects[li]) : "Not tested");
  const benchmark = getBenchmarks(data)[0];
  const centaxBeforeBunching = benchmark?.underlying_static_before_bunching_by_year_bn?.[String(last.year)];
  const groups = [
    {
      title: "Cost",
      rows: [
        ["Schemes covered", "30 hours and Tax-Free Childcare", "", "Free hours only", "30 hours and Tax-Free Childcare", ""],
        [
          `Static cost, ${nb(last.year)}`,
          `${formatBn(last.total, 2)} (30 hours ${formatBn(last.thirty_hours, 2)}; take-up: ${chosen.label})`,
          "",
          `${formatBn(central.staticBn, 2)} (${formatBn(low.staticBn, 2)} to ${formatBn(high.staticBn, 2)}; ${formatBn(centaxBeforeBunching, 2)} before their deduction for parents keeping income just under £100,000)`,
          "Not given",
          "",
        ],
        [
          `After parents change how much they work, ${nb(last.year)}`,
          <span key="dyn" data-testid="dynamic-cell">{dynamicCell(data, setting, chosen.id)}</span>,
          "",
          `${formatBn(central.netBn, 2)} (${net(low.netBn)} to ${net(high.netBn)})`,
          "About £0.7bn a year; basis not stated",
          "",
        ],
      ],
    },
    {
      title: "How it is modelled",
      rows: [
        [
          "Work, pay and pensions",
          a.static.ours,
          eff("static"),
          "Parents stop keeping income below £100,000; partners move into work",
          "Not stated",
          "",
        ],
        [
          "Hours of childcare used",
          a.hours.ours,
          eff("hours"),
          "Full entitlement: 30 hours x 38 weeks",
          "Not stated",
          <span key="h">{a.hours.source_says}. <Link href={a.hours.source.url}>{a.hours.source.label}</Link></span>,
        ],
        [
          "Babies under one",
          a.under_ones.ours,
          "",
          "Included, as in the law",
          "Not stated",
          <span key="u">{a.under_ones.source_says}. <Link href={a.under_ones.source.url}>{a.under_ones.source.label}</Link></span>,
        ],
        [
          "Who takes up the 30 hours",
          a.take_up.ours,
          eff("take_up"),
          `As today (DfE, 2025): ${takeUp.bases.centax?.rates_text ?? "not stated"}`,
          "Not stated",
          <span key="t">
            DfE&apos;s January 2025 take-up by age. <Link href={a.take_up.source.url}>{a.take_up.source.label}</Link>
          </span>,
        ],
        [
          "One take-up rate for every family",
          a.take_up_contract.ours,
          eff("take_up_contract"),
          "",
          "Not stated",
          <span key="tc">{a.take_up_contract.source_says}. <Link href={a.take_up_contract.source.url}>{a.take_up_contract.source.label}</Link></span>,
        ],
        [
          "Who claims Tax-Free Childcare",
          a.tfc_take_up.ours,
          eff("tfc_take_up"),
          "Not costed: free hours only",
          "Not stated",
          <span key="tt">{a.tfc_take_up.source_says}. <Link href={a.tfc_take_up.source.url}>{a.tfc_take_up.source.label}</Link></span>,
        ],
        [
          "Income the limit tests",
          a.income_test.ours,
          eff("income_test"),
          "Adjusted net income after pension contributions, from tax records",
          "Not stated",
          <span key="i">
            After pension contributions (<Link href={a.income_test.source.url}>ITA 2007 s58</Link>); the income a parent
            expects (<Link href={SI_2022_1134_URL}>SI 2022/1134</Link>)
          </span>,
        ],
      ],
    },
  ];
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="comparison-table">
        <thead>
          <tr>
            <th />
            <th>PolicyEngine</th>
            <th>If we change it, {nb(last.year)}</th>
            <th>CenTax</th>
            <th>Conservatives</th>
            <th>Official sources and law</th>
          </tr>
        </thead>
        {groups.map((g) => (
          <tbody key={g.title}>
            <tr>
              <td colSpan={6} className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                {g.title}
              </td>
            </tr>
            {g.rows.map(([label, ...cells]) => (
              <tr key={label}>
                <td className="min-w-[150px] font-medium text-slate-800">{label}</td>
                {cells.map((c, i) => (
                  <td key={i} className={i === 1 ? "whitespace-nowrap tabular-nums" : "min-w-[150px]"}>
                    {c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
