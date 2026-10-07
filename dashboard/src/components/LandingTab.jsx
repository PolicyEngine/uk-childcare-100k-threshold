"use client";

import { useState } from "react";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { colors, schemeColors } from "../lib/colors";
import {
  fyLabel,
  getBudget,
  getBudgetComparisons,
  getRecipients,
  isNum,
  isStatic,
  labourSupplyLabel,
  labourSupplyOffset,
  LEAD_YEAR,
  STATIC_SETTING,
  SCHEME_LABELS,
  SCHEMES,
  yearHeading,
} from "../lib/dataHelpers";
import { formatBn, formatCurrency, formatMoneyBn, formatPct, formatThousands } from "../lib/formatters";
import { axisDigits, niceAxis } from "../lib/ticks";
import ChartLogo from "./ChartLogo";
import { AXIS_STYLE, CustomTooltip, Section } from "./ui";

/** A non-breaking hyphen keeps "2026-27" on one line. */
const nb = (year) => fyLabel(year).replace("-", "‑");

/**
 * CenTax, Removing the childcare cliff-edge: impacts and cost of reform (September 2026), Table 4.2, central case,
 * 2030: removing the £100,000 limit on the free childcare hours only (not Tax-Free Childcare). The figure City AM
 * reports as the party's is based on this report.
 */

/** £bn as a signed £m figure: -0.006 -> "-£6m", 0.362 -> "+£362m". */
export function formatSignedM(v) {
  if (!isNum(v)) throw new TypeError(`formatSignedM: ${JSON.stringify(v)} is not a number`);
  const m = Math.round(v * 1000);
  return `${m > 0 ? "+" : m < 0 ? "-" : ""}£${Math.abs(m).toLocaleString("en-GB")}m`;
}

function Card({ label, value, detail, testId, children }) {
  return (
    <div className="metric-card flex flex-col" data-testid={testId}>
      <p className="eyebrow text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
      {detail ? <div className="mt-1 text-sm text-slate-600">{detail}</div> : null}
      {children}
    </div>
  );
}

/** Small vertical bars, one per item, the first (or `highlight`) darkest. */
/** A tooltip shown above its trigger on hover or keyboard focus, styled like the charts' tooltips. */
function Tip({ text, children, className = "", style }) {
  return (
    <span className={`group/tip relative ${className}`} style={style}>
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-800 opacity-0 shadow-lg transition-opacity group-hover/tip:opacity-100 group-focus-within/tip:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}

/** Small vertical bars, one per item, the selected one darkest; hover shows the value, click selects. */
function MiniBars({ items, label, highlight = 0, onSelect, format }) {
  const max = Math.max(...items.map((d) => d.value), 0) || 1;
  return (
    <div className="mt-auto pt-4" data-testid="mini-strip" aria-label={label}>
      <div className="flex h-12 items-end gap-2 border-b border-slate-300">
        {items.map((d, i) => (
          <Tip key={d.label} text={format ? `${d.label}: ${format(d.value)}` : d.label} className="flex h-full flex-1 items-end">
            <button
              type="button"
              aria-label={`${d.label}${format ? `: ${format(d.value)}` : ""}`}
              aria-pressed={i === highlight}
              onClick={onSelect ? () => onSelect(i) : undefined}
              className="w-full rounded-t-sm transition-opacity hover:opacity-80"
              style={{
                height: `${(100 * Math.max(0, d.value)) / max}%`,
                backgroundColor: d.color ?? (i === highlight ? colors.primary[600] : colors.primary[200]),
              }}
            />
          </Tip>
        ))}
      </div>
      <div className="mt-1 flex gap-2">
        {items.map((d, i) => (
          <span key={d.label} className={`flex-1 text-center text-[11px] ${i === highlight ? "font-semibold text-slate-800" : "text-slate-500"}`}>
            {d.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/** One bar split between the two schemes, each part labelled with its cost; hover for detail, click one to show it alone. */
function SplitBar({ thirty, tfc, selected, onSelect }) {
  const total = thirty + tfc || 1;
  const share = Math.max(0, Math.min(1, thirty / total));
  const parts = [
    { id: "thirty_hours", short: "30 hours", grow: share, value: thirty, pct: 100 * share, ink: "#fff" },
    { id: "tax_free_childcare", short: "Tax-Free Childcare", grow: 1 - share, value: tfc, pct: 100 * (1 - share), ink: colors.gray[900] },
  ];
  return (
    <div className="mt-auto pt-4" data-testid="mini-strip" aria-label="Split of the cost between the two schemes">
      <div className="flex gap-0.5">
      {parts.map((p) => (
        <Tip key={p.id} text={`${SCHEME_LABELS[p.id]}: ${formatBn(p.value, 2)} (${formatPct(p.pct, 0)})`} className="flex min-w-0" style={{ flexGrow: p.grow, flexBasis: 0 }}>
        <button
          type="button"
          aria-label={`${SCHEME_LABELS[p.id]}: ${formatBn(p.value, 2)}`}
          aria-pressed={selected === p.id}
          onClick={() => onSelect(selected === p.id ? null : p.id)}
          className="w-full min-w-0 overflow-hidden rounded-md px-2 py-1.5 text-left text-xs transition-opacity hover:opacity-90"
          style={{ backgroundColor: schemeColors[p.id], color: p.ink, opacity: selected && selected !== p.id ? 0.35 : 1 }}
        >
          <span className="block truncate font-semibold">{formatPct(p.pct, 0)}</span>
        </button>
        </Tip>
      ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
        {parts.map((p) => (
          <span key={p.id} className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: schemeColors[p.id] }} />
            {p.short}
          </span>
        ))}
      </div>
    </div>
  );
}

/** A short list of labelled horizontal bars with their values; hover for detail, click a row to select it. */
function BarList({ items, selected, onSelect, format }) {
  const max = Math.max(...items.map((d) => d.value), 0) || 1;
  return (
    <div className="mt-auto space-y-2 pt-4" data-testid="mini-strip">
      {items.map((d) => (
        <Tip key={d.id} text={`${d.label}: ${format(d.value)} families`} className="block">
        <button
          type="button"
          aria-label={`${d.label}: ${format(d.value)}`}
          aria-pressed={selected === d.id}
          onClick={() => onSelect(selected === d.id ? null : d.id)}
          className="grid w-full grid-cols-[minmax(0,7.5rem)_1fr_auto] items-center gap-2 text-left text-xs text-slate-600 hover:text-slate-900"
          style={{ opacity: selected && selected !== d.id ? 0.45 : 1 }}
        >
          <span className="truncate">{d.label}</span>
          <span className="h-3 rounded-sm bg-slate-100">
            <span className="block h-3 rounded-sm" style={{ width: `${(100 * d.value) / max}%`, backgroundColor: d.color }} />
          </span>
          <span className="tabular-nums font-medium text-slate-800">{format(d.value)}</span>
        </button>
        </Tip>
      ))}
    </div>
  );
}

export const OFFSET_KEY = "labour_supply";

/**
 * The labour supply series' name, by its sign: money back when the response lowers the cost in every year, an
 * extra cost when it raises it in every year (moving into work alone does), and neutral wording when the sign varies.
 */
export function offsetLabel(offsets) {
  if (offsets.every((v) => v >= 0)) return "Back from parents working more";
  if (offsets.every((v) => v <= 0)) return "Added by the labour supply response";
  return "Labour supply response";
}

/**
 * The yearly chart's rows and series. With a margin on, the chart carries the labour supply response as a signed
 * series (below zero when it brings money back), so each year's series add up to the cost after the response.
 */
export function costChartData(budget, offsets, dynamic) {
  const rows = budget.rows.map((r, i) => ({ ...r, label: yearHeading(r.year), [OFFSET_KEY]: -offsets[i] }));
  return { rows, series: dynamic ? [...SCHEMES, OFFSET_KEY] : [...SCHEMES], offsetName: offsetLabel(offsets) };
}

/** What the tooltip's total adds up for one row: every series the chart draws. */
export function chartRowTotal(row, series) {
  return series.reduce((t, s) => t + row[s], 0);
}

function CostChart({ rows, series, offsetName }) {
  const withOffset = series.includes(OFFSET_KEY);
  const fills = { ...schemeColors, [OFFSET_KEY]: colors.gray[400] };
  const names = { ...SCHEME_LABELS, [OFFSET_KEY]: offsetName };
  const values = rows.flatMap((r) => [r.thirty_hours + r.tax_free_childcare, ...(withOffset ? [r[OFFSET_KEY], chartRowTotal(r, series)] : [])]);
  const digits = axisDigits(values);
  const axis = niceAxis(values);
  return (
    <>
      <div style={{ height: 340 }} data-testid="cost-chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 10, right: 20, left: 10, bottom: 0 }} stackOffset="sign">
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} vertical={false} />
            <XAxis dataKey="label" tick={AXIS_STYLE} />
            <YAxis tick={AXIS_STYLE} tickFormatter={(v) => formatBn(v, digits)} {...axis} />
            <Tooltip
              cursor={{ fill: colors.gray[100] }}
              content={<CustomTooltip formatter={(v) => formatMoneyBn(v)} totalLabel={withOffset ? "Cost after the response" : "Total"} />}
            />
            {SCHEMES.map((s) => (
              <Bar
                key={s}
                dataKey={s}
                name={SCHEME_LABELS[s]}
                stackId="cost"
                fill={schemeColors[s]}
                // Only the top of the stack is rounded; a white edge separates the two schemes.
                radius={s === SCHEMES.at(-1) ? [4, 4, 0, 0] : 0}
                stroke="#fff"
                strokeWidth={1}
                isAnimationActive={false}
                maxBarSize={80}
              />
            ))}
            {withOffset ? (
              <Bar
                dataKey={OFFSET_KEY}
                name={offsetName}
                stackId="cost"
                fill={fills[OFFSET_KEY]}
                stroke="#fff"
                strokeWidth={1}
                isAnimationActive={false}
                maxBarSize={80}
              />
            ) : null}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex flex-wrap justify-center gap-x-5 gap-y-2 text-sm text-slate-600">
        {series.map((s) => (
          <span key={s} className="flex items-center gap-2" data-testid={`legend-${s}`}>
            <span className="inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: fills[s] }} />
            {names[s]}
          </span>
        ))}
      </div>
      <ChartLogo />
    </>
  );
}

/** The largest gap between the net and gross cost in any year, £m. */
export function netGrossGapM(net, gross) {
  return Math.max(...net.map((v, i) => Math.round(Math.abs(v - gross[i]) * 1000)));
}

/** Each scheme side by side: where it applies, what it gives, who qualifies today and what the reform changes. */
function SchemesTable() {
  const rows = [
    ["Where", "England", "UK-wide"],
    ["What it is", "Free childcare hours (for 3- and 4-year-olds, 15 on top of the universal 15)", "20% top-up on childcare bills (£2 for every £8)"],
    ["Children's ages", "9 months to school age", "Up to 11 (16 if disabled)"],
    ["Most per child", "30 hours a week, 38 weeks a year", "£2,000 a year (£4,000 if disabled)"],
    ["Earnings floor", "Each parent earns at least 16 hours a week at the minimum wage", "Same"],
    ["Income limit today", "Neither parent over £100,000", "Same"],
    ["After the reform", "No income limit; everything else unchanged", "Same"],
  ];
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="schemes-table">
        <thead>
          <tr>
            <th />
            <th>
              <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: schemeColors.thirty_hours }} />
              {SCHEME_LABELS.thirty_hours}
            </th>
            <th>
              <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: schemeColors.tax_free_childcare }} />
              {SCHEME_LABELS.tax_free_childcare}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, a, b]) => (
            <tr key={label}>
              <td className="min-w-[140px] font-medium text-slate-800">{label}</td>
              <td className="min-w-[220px]">{a}</td>
              <td className="min-w-[220px]">{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function LandingTab({ data, setting = STATIC_SETTING }) {
  const budget = getBudget(data);
  const dynamic = !isStatic(setting);
  const offsets = labourSupplyOffset(data, setting);
  const cost = budget.rows.map((r, i) => r.total - offsets[i]);
  const [li, setLi] = useState(budget.years.indexOf(LEAD_YEAR));
  const [scheme, setScheme] = useState(null);
  const lead = budget.rows[li];
  const recipients = getRecipients(data, lead.year);
  const cmp = getBudgetComparisons(data);
  const chart = costChartData(budget, offsets, dynamic);
  const gapM = netGrossGapM(cmp.net, budget.rows.map((r) => r.total));
  const fy = nb(lead.year);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="landing-tab">
      <Section
        id="at-a-glance"
        title="The cost at a glance"
        lead={`What removing the limit adds to government spending and who gains, opening on ${fyLabel(LEAD_YEAR)}, the first full year. Click a year's bar to change the year, or a scheme to show it alone.`}
        boxed={false}
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card
            label={`Cost in ${fy}`}
            value={formatBn(cost[li], 2)}
            detail={
              dynamic
                ? `After the labour supply response (${labourSupplyLabel(setting)}): ${formatBn(lead.total, 2)} static, ${
                    offsets[li] >= 0 ? `${formatMoneyBn(offsets[li])} back from parents working more` : `${formatMoneyBn(-offsets[li])} more, as the response raises the cost`
                  }`
                : "Extra government spending on both schemes"
            }
            testId="card-cost"
          >
            <MiniBars
              items={budget.rows.map((r, i) => ({ label: fyLabel(r.year), value: cost[i] }))}
              label="Central cost each year: click a year to show it"
              highlight={li}
              onSelect={setLi}
              format={(v) => formatBn(v, 2)}
            />
          </Card>
          <Card
            label={scheme ? SCHEME_LABELS[scheme] : "By scheme"}
            value={scheme ? formatBn(lead[scheme], 2) : `${formatBn(lead.thirty_hours, 2)} and ${formatBn(lead.tax_free_childcare, 2)}`}
            detail={`${scheme ? `Cost of this scheme, ${fy}` : `30 hours and Tax-Free Childcare, ${fy}`}${dynamic ? "; static: the labour supply response applies to the total only" : ""}`}
            testId="card-split"
          >
            <SplitBar thirty={lead.thirty_hours} tfc={lead.tax_free_childcare} selected={scheme} onSelect={setScheme} />
          </Card>
          <Card
            label={scheme ? `Families gaining from ${SCHEME_LABELS[scheme]}` : "Families gaining"}
            value={formatThousands(scheme ? recipients.by_scheme[scheme] : recipients.families_gaining)}
            detail={
              scheme
                ? `${recipients.children_by_scheme ? `${formatThousands(recipients.children_by_scheme[scheme])} children, ` : ""}${fy}`
                : `${formatThousands(recipients.children_gaining)} children${recipients.mean_gain_gbp === null ? "" : `; ${formatCurrency(recipients.mean_gain_gbp)} a year on average`}, ${fy}`
            }
            testId="card-families"
          >
            <BarList
              items={SCHEMES.map((sc) => ({ id: sc, label: sc === "thirty_hours" ? "30 hours" : "Tax-Free Childcare", value: recipients.by_scheme[sc], color: schemeColors[sc] }))}
              selected={scheme}
              onSelect={setScheme}
              format={formatThousands}
            />
          </Card>
        </div>
      </Section>

      <Section
        id="schemes"
        title="What changes for each scheme?"
        lead="Both schemes are withdrawn in full when either parent's adjusted net income goes over £100,000. The reform removes that test from both; nothing else changes."
      >
        <SchemesTable />
      </Section>

      <Section
        id="each-year"
        title="How much does it cost each year?"
        lead="Extra government spending in each fiscal year from removing the limit, split between the 30 funded hours and Tax-Free Childcare. The £100,000 limit is not uprated, so as pay rises more parents pass it each year and the cost of removing it grows. Hover over a bar for its figures. The assumptions behind these figures, and what each one changes, are on the Methodology tab."
        detailsTitle="How to read this chart"
        details={
          <>
            <p>
              Each bar is the extra government spending in that fiscal year when neither the 30 hours nor Tax-Free
              Childcare is withdrawn above £100,000 of adjusted net income, with the policy in force for the whole
              year. {fyLabel(budget.years[0])} is more than half over, so its full-year cost is illustrative.
            </p>
            {!dynamic && gapM <= 2 ? (
              <p data-testid="net-note">
                {gapM === 0
                  ? "The static cost is the same net of other taxes and benefits."
                  : `Net of other taxes and benefits, the static cost is within £${gapM}m of these figures in every year: no other tax or benefit in the model depends on the limits, so the gap is rounding.`}
              </p>
            ) : null}
          </>
        }
      >
        {dynamic ? (
          <p className="mb-3 text-sm text-slate-600" data-testid="chart-setting">
            Labour supply on ({labourSupplyLabel(setting)}):{" "}
            {offsets.every((v) => v >= 0)
              ? "the grey bars below zero are the money back from parents working more"
              : offsets.every((v) => v <= 0)
                ? "the grey bars on top are the extra cost the response adds"
                : "the grey bars are the labour supply response, below zero where it brings money back and on top where it adds to the cost"}
            , not split by scheme; hover for the cost after the response.
          </p>
        ) : null}
        <CostChart rows={chart.rows} series={chart.series} offsetName={chart.offsetName} />
      </Section>

    </div>
  );
}
