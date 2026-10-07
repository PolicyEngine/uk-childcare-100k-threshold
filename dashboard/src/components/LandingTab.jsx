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
  LEAD_YEAR,
  SCHEME_LABELS,
  SCHEMES,
  yearHeading,
} from "../lib/dataHelpers";
import { formatBn, formatCurrency, formatPct, formatThousands } from "../lib/formatters";
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

function CostChart({ rows }) {
  const values = rows.map((r) => r.total);
  const digits = axisDigits(values);
  const axis = niceAxis(values);
  return (
    <>
      <div style={{ height: 340 }} data-testid="cost-chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} vertical={false} />
            <XAxis dataKey="label" tick={AXIS_STYLE} />
            <YAxis tick={AXIS_STYLE} tickFormatter={(v) => formatBn(v, digits)} {...axis} />
            <Tooltip
              cursor={{ fill: colors.gray[100] }}
              content={<CustomTooltip formatter={(v) => formatBn(v, 2)} totalLabel="Total" />}
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
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex flex-wrap justify-center gap-x-5 gap-y-2 text-sm text-slate-600">
        {SCHEMES.map((s) => (
          <span key={s} className="flex items-center gap-2">
            <span className="inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: schemeColors[s] }} />
            {SCHEME_LABELS[s]}
          </span>
        ))}
      </div>
      <ChartLogo />
    </>
  );
}

/** True when two series match to within rounding in every year. */
const same = (a, b) => a.every((v, i) => Math.abs(v - b[i]) < 0.0015);

export default function LandingTab({ data }) {
  const budget = getBudget(data);
  const [li, setLi] = useState(budget.years.indexOf(LEAD_YEAR));
  const [scheme, setScheme] = useState(null);
  const lead = budget.rows[li];
  const recipients = getRecipients(data, lead.year);
  const cmp = getBudgetComparisons(data);
  const rows = budget.rows.map((r) => ({ ...r, label: yearHeading(r.year) }));
  const fy = nb(lead.year);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="landing-tab">
      <Section
        id="at-a-glance"
        title="The cost at a glance"
        lead={`Today a family loses the 30 funded hours (England) and Tax-Free Childcare (UK-wide) as soon as either parent's adjusted net income goes over £100,000. The reform removes that limit from both schemes, so families keep the support however much a parent earns; every other condition, including the minimum earnings test, stays. These cards show what that adds to government spending and who gains, opening on ${fyLabel(LEAD_YEAR)}, the first full year. Click a year's bar to change the year, or a scheme to show it alone.`}
        boxed={false}
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card
            label={`Cost in ${fy}`}
            value={formatBn(lead.total, 2)}
            detail="Extra government spending on both schemes"
            testId="card-cost"
          >
            <MiniBars
              items={budget.rows.map((r) => ({ label: fyLabel(r.year), value: r.total }))}
              label="Central cost each year: click a year to show it"
              highlight={li}
              onSelect={setLi}
              format={(v) => formatBn(v, 2)}
            />
          </Card>
          <Card
            label={scheme ? SCHEME_LABELS[scheme] : "By scheme"}
            value={scheme ? formatBn(lead[scheme], 2) : `${formatBn(lead.thirty_hours, 2)} and ${formatBn(lead.tax_free_childcare, 2)}`}
            detail={scheme ? `Cost of this scheme, ${fy}` : `30 hours and Tax-Free Childcare, ${fy}`}
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
            {same(cmp.net, budget.rows.map((r) => r.total)) ? (
              <p data-testid="net-note">The cost is the same net of other taxes and benefits: nothing else changes for these families.</p>
            ) : null}
          </>
        }
      >
        <CostChart rows={rows} />
      </Section>

    </div>
  );
}
