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

export function BenchmarkNotes({ data, Heading = "h3" }) {
  const benchmark = getBenchmarks(data)[0];
  // Two short notes under the comparison table, each under its own heading.
  return (
    <>
      <Heading>The Conservatives&apos; figure</Heading>
      <p className="text-base leading-relaxed text-slate-700" data-testid="benchmark">
        About £700m a year, paid for by cutting staff at arm&apos;s-length public bodies. Their{" "}
        <a href={benchmark.announcement_url} target="_blank" rel="noopener noreferrer">
          announcement
        </a>{" "}
        covers both the free hours and Tax-Free Childcare but gives no method;{" "}
        <a href={benchmark.url} target="_blank" rel="noopener noreferrer">
          City AM
        </a>{" "}
        says it is based on{" "}
        <a href={benchmark.underlying_source_url} target="_blank" rel="noopener noreferrer">
          CenTax&apos;s report
        </a>
        , which costs the free hours only.
      </p>
      <Heading>Like-for-like</Heading>
      <p className="text-base leading-relaxed text-slate-700" data-testid="benchmark-like-for-like">
        Our 30 hours cost and CenTax&apos;s static cost are the like-for-like pair, both before any change in work. The
        party&apos;s £0.7bn is close to CenTax&apos;s central net figure plus a little for Tax-Free Childcare.
        CenTax&apos;s 2030 is our 2029-30.
      </p>
    </>
  );
}



/** £bn as a signed £m figure. */
const signedM = (v) => {
  const m = Math.round(v * 1000);
  return `${m > 0 ? "+" : m < 0 ? "-" : ""}£${Math.abs(m).toLocaleString("en-GB")}m`;
};

const Link = ({ href, children }) => (
  <a href={href} target="_blank" rel="noopener noreferrer">
    {children}
  </a>
);

/**
 * Our cost once parents change how much they work, in the final year. With the labour supply control off it shows
 * both margins at central elasticities with the low-high range; with it on, the margins and elasticities chosen. The
 * key figure and its detail come back separately, for the table's two lines.
 */
export function dynamicCell(data, setting) {
  const budget = getBudget(data);
  const li = budget.years.length - 1;
  const ls = getLabourSupply(data);
  if (isStatic(setting)) {
    const d = ls.dynamic;
    return {
      main: formatBn(d.central[li], 2),
      sub: `${formatBn(d.high[li], 2)} to ${formatBn(d.low[li], 2)}, an illustrative range; partners moving into work and hours, net of the income effect; bunching not modelled`,
    };
  }
  const cost = budget.rows[li].total - labourSupplyOffset(data, setting)[li];
  return { main: formatBn(cost, 2), sub: labourSupplyLabel(setting) };
}

const CENTAX_REPORT_URL =
  "https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf";
// Table 4.2 (static cost, both behavioural margins and the net cost) is on page 42; the ANI definition on page 6.
const CENTAX_TABLE_4_2_URL = `${CENTAX_REPORT_URL}#page=42`;
const CENTAX_ANI_URL = `${CENTAX_REPORT_URL}#page=6`;
const SI_2022_1134_REG_14_URL = "https://www.legislation.gov.uk/uksi/2022/1134/regulation/14";
const SI_2015_448_REG_15_URL = "https://www.legislation.gov.uk/uksi/2015/448/regulation/15";

/** Text before the first `sep` as the cell's line, the rest as its muted second line. */
function split(text, sep) {
  const k = text.indexOf(sep);
  return k < 0 ? { main: text } : { main: text.slice(0, k), sub: text.slice(k + sep.length) };
}

/** A table cell: the key point, and any detail on a smaller muted line under it. */
function Cell({ main, sub, testId }) {
  return (
    <span data-testid={testId}>
      {main}
      {sub ? <span className="mt-0.5 block text-xs leading-5 text-slate-500">{sub}</span> : null}
    </span>
  );
}

/**
 * One table: the cost and every modelling choice, PolicyEngine against CenTax, the Conservatives and the official
 * sources or the law. The effect column is what changing our choice to the tested alternative does to the cost in
 * the final year; on the cost rows it has nothing to show.
 */
export function UnifiedComparison({ data, setting = STATIC_SETTING }) {
  // Always on the headline take-up basis: the effect column is measured from it, so another basis's cost here would
  // not match the rows below. The take-up toggle is on Budget impact.
  const takeUp = getTakeUp(data);
  const headline = takeUp.bases[takeUp.headline];
  const budget = getBudget(data);
  const last = budget.rows.at(-1);
  const li = budget.years.length - 1;
  const a = Object.fromEntries(getModellingAssumptions(data).map((r) => [r.id, r]));
  const [central, high, low] = ["central", "high", "low"].map((id) => CENTAX_SCENARIOS.find((c) => c.id === id));
  const net = (v) => (v < 0 ? `raises ${formatBn(-v, 2)}` : formatBn(v, 2));
  const eff = (id) => (a[id]?.effects ? signedM(a[id].effects[li]) : "Not tested");
  const benchmark = getBenchmarks(data)[0];
  const centaxBeforeBunching = benchmark?.underlying_static_before_bunching_by_year_bn?.[String(last.year)];
  const none = "—";
  const official = (r) => (
    <>
      {r.source_says}. <Link href={r.source.url}>{r.source.label}</Link>
    </>
  );
  const dyn = dynamicCell(data, setting);
  const groups = [
    {
      title: "Cost",
      rows: [
        [
          "Which schemes are costed?",
          "30 hours and Tax-Free Childcare",
          none,
          <Link key="c" href={CENTAX_REPORT_URL}>Free hours only</Link>,
          <Link key="k" href={benchmark.announcement_url}>30 hours and Tax-Free Childcare</Link>,
          none,
        ],
        [
          `Static cost, ${nb(last.year)}`,
          <Cell
            key="s"
            testId="static-cell"
            main={formatBn(last.total, 2)}
            sub={`30 hours ${formatBn(last.thirty_hours, 2)}; take-up: ${headline.label}`}
          />,
          none,
          <Cell
            key="cs"
            main={<Link href={CENTAX_TABLE_4_2_URL}>{formatBn(central.staticBn, 2)}</Link>}
            sub={`Range ${formatBn(low.staticBn, 2)} to ${formatBn(high.staticBn, 2)}; ${formatBn(centaxBeforeBunching, 2)} before their deduction for parents keeping income just under £100,000`}
          />,
          "Not given",
          none,
        ],
        [
          `Cost after parents change how much they work, ${nb(last.year)}`,
          <Cell key="d" testId="dynamic-cell" main={dyn.main} sub={dyn.sub} />,
          none,
          <Cell
            key="cn"
            main={<Link href={CENTAX_TABLE_4_2_URL}>{formatBn(central.netBn, 2)}</Link>}
            sub={`Range ${net(low.netBn)} to ${net(high.netBn)}`}
          />,
          <Cell key="kn" main={<Link href={benchmark.url}>About £0.7bn a year</Link>} sub="Basis not stated" />,
          none,
        ],
      ],
    },
    {
      title: "How it is modelled",
      rows: [
        [
          "Do parents change how much they work?",
          a.static.ours,
          eff("static"),
          <Link key="c" href={CENTAX_TABLE_4_2_URL}>
            Yes: parents stop keeping income below £100,000; partners move into work
          </Link>,
          "Not stated",
          none,
        ],
        ["How many hours of childcare are used?", a.hours.ours, eff("hours"), "Full entitlement: 30 hours x 38 weeks", "Not stated", official(a.hours)],
        ["Are babies aged 9 to 11 months included?", a.under_ones.ours, eff("under_ones"), "Included, as in the law", "Not stated", official(a.under_ones)],
        [
          "What share take up the 30 hours?",
          <Cell key="p" {...split(a.take_up.ours, ": ")} />,
          eff("take_up"),
          <Cell
            key="c"
            main={<Link href={takeUp.bases.centax?.source_url ?? CENTAX_REPORT_URL}>As today (DfE, 2025)</Link>}
            sub={takeUp.bases.centax?.rates_text ?? "Not stated"}
          />,
          "Not stated",
          <span key="t">
            DfE&apos;s January 2025 take-up by age. <Link href={a.take_up.source.url}>{a.take_up.source.label}</Link>
          </span>,
        ],
        [
          "Same take-up rate for every family?",
          a.take_up_contract.ours,
          eff("take_up_contract"),
          "No: one rate under 3, one at 3 and 4",
          "Not stated",
          official(a.take_up_contract),
        ],
        [
          "Who gets a Tax-Free Childcare top-up?",
          <Cell key="p" {...split(a.tfc_take_up.ours, "; ")} />,
          eff("tfc_take_up"),
          "Not costed: free hours only",
          "Not stated",
          official(a.tfc_take_up),
        ],
        [
          "What income does the £100,000 test use?",
          <Cell key="p" {...split(a.income_test.ours, "; ")} />,
          eff("income_test"),
          <Link key="c" href={CENTAX_ANI_URL}>
            Adjusted net income after pension contributions, from tax records
          </Link>,
          "Not stated",
          <span key="i">
            After pension contributions (<Link href={a.income_test.source.url}>ITA 2007 s58</Link>); the income a parent
            expects (<Link href={SI_2022_1134_REG_14_URL}>SI 2022/1134 reg 14</Link>,{" "}
            <Link href={SI_2015_448_REG_15_URL}>SI 2015/448 reg 15</Link>)
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
            <th>
              If we change it, {nb(last.year)}
              <span className="mt-1 block text-[11px] font-normal normal-case tracking-normal text-slate-500">
                How much our {nb(last.year)}{" "}
                cost moves if we use the other approach (each on its own; they don&apos;t add up)
              </span>
            </th>
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
                  <td key={i} className={i === 1 ? "min-w-[150px] tabular-nums" : "min-w-[150px]"}>
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
