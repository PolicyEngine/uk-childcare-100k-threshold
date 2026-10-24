"use client";

import { useState } from "react";

import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, LabelList, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { colors, schemeColors } from "../lib/colors";
import {
  fyLabel,
  getBenchmarks,
  getBudget,
  getTakeUp,
  getUncertainty,
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
import { Expandable, AXIS_STYLE, CustomTooltip, openDetails, Section, TAKE_UP_OPTIONS_ID } from "./ui";

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
            <YAxis tick={AXIS_STYLE} tickFormatter={(v) => (v === 0 ? "£0" : formatBn(v, digits))} {...axis} />
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
const bnRange = (lo, hi) => `${formatBn(lo, 2)} to ${formatBn(hi, 2)}`;
// In a narrow table cell a range breaks after "to", never inside a figure.
const bnRangeCell = (lo, hi) => (
  <>
    <span className="whitespace-nowrap">{formatBn(lo, 2)} to</span> <span className="whitespace-nowrap">{formatBn(hi, 2)}</span>
  </>
);

/** The bootstrap's standard deviation and 5th-95th percentile on the take-up basis chosen, and the single draw. */
export function UncertaintyTable({ data, basis }) {
  const u = getUncertainty(data, basis);
  const rows = [
    ["30 hours: standard deviation", (r) => formatBn(r.chosen.thirty_hours.sd_bn, 2)],
    ["30 hours: 5th to 95th percentile", (r) => bnRangeCell(r.chosen.thirty_hours.p5_bn, r.chosen.thirty_hours.p95_bn)],
    ["Both schemes: standard deviation", (r) => formatBn(r.chosen.total.sd_bn, 2)],
    ["Both schemes: 5th to 95th percentile", (r) => bnRangeCell(r.chosen.total.p5_bn, r.chosen.total.p95_bn)],
    ["30 hours on the dataset's single take-up draw", (r) => formatBn(r.singleThirty, 2)],
  ];
  return (
    <div className="overflow-x-auto">
      <table className="data-table compact" data-testid="uncertainty-table">
        <thead>
          <tr>
            <th className="text-left font-normal text-slate-500">Take-up: {u.basis.short_label}</th>
            {u.rows.map((r) => (
              <th key={r.year} className="text-right">
                {nb(r.year)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, cell]) => (
            <tr key={label}>
              <td className="font-medium text-slate-800 sm:min-w-[180px]">{label}</td>
              {u.rows.map((r) => (
                <td key={r.year} className="text-right tabular-nums sm:whitespace-nowrap">
                  {cell(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// The marks of the range chart, used by the chart and its legend alike.
const RANGE_MARKS = {
  thirty_hours: { band: colors.primary[200], dot: schemeColors.thirty_hours },
  total: { band: colors.gray[300], dot: colors.gray[700] },
  centax: colors.gray[900],
  single: colors.primary[600],
};

/** The range chart's rows: per year, the 30 hours and both schemes, each a 5th-95th percentile band and the central cost. */
export function rangeChartRows(u, centax) {
  return u.rows.flatMap((r) => [
    {
      key: `${r.year}-thirty`,
      year: nb(r.year),
      part: "30 hours",
      scheme: "thirty_hours",
      range: [r.chosen.thirty_hours.p5_bn, r.chosen.thirty_hours.p95_bn],
      central: r.thirty,
      centax: isNum(centax[String(r.year)]) ? centax[String(r.year)] : null,
      single: r.singleThirty,
    },
    {
      key: `${r.year}-total`,
      year: nb(r.year),
      part: "Both schemes",
      scheme: "total",
      range: [r.chosen.total.p5_bn, r.chosen.total.p95_bn],
      central: r.total,
      centax: null,
      single: null,
    },
  ]);
}

function RangeTick({ x, y, payload, rows }) {
  const row = rows.find((r) => r.key === payload.value);
  if (!row) return null;
  return (
    <g transform={`translate(${x},${y})`}>
      <text x={-6} y={-3} textAnchor="end" fontSize={12} fontWeight={600} fill={colors.gray[800]}>
        {row.year}
      </text>
      <text x={-6} y={11} textAnchor="end" fontSize={11} fill={colors.gray[500]}>
        {row.part}
      </text>
    </g>
  );
}

/** The band's two ends labelled under it. */
function RangeEnds({ x, y, width, height, value }) {
  if (!Array.isArray(value) || !isNum(x) || !isNum(width)) return null;
  const ty = y + height + 11;
  return (
    <g fontSize={10.5} fill={colors.gray[600]}>
      <text x={x} y={ty} textAnchor="start">{formatBn(value[0], 2)}</text>
      <text x={x + width} y={ty} textAnchor="end">{formatBn(value[1], 2)}</text>
    </g>
  );
}

function CentralDot({ cx, cy, payload }) {
  if (!isNum(cx) || !isNum(cy)) return null;
  return <circle cx={cx} cy={cy} r={5.5} fill={RANGE_MARKS[payload.scheme].dot} stroke="#fff" strokeWidth={1.5} />;
}

function CentaxMark({ cx, cy }) {
  if (!isNum(cx) || !isNum(cy)) return null;
  const d = 5.5;
  return <path d={`M${cx},${cy - d} L${cx + d},${cy} L${cx},${cy + d} L${cx - d},${cy} Z`} fill={RANGE_MARKS.centax} stroke="#fff" strokeWidth={1} />;
}

function SingleMark({ cx, cy }) {
  if (!isNum(cx) || !isNum(cy)) return null;
  return <circle cx={cx} cy={cy} r={5} fill="#fff" stroke={RANGE_MARKS.single} strokeWidth={2} />;
}

function RangeTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const lines = [
    ["Central", formatBn(row.central, 2)],
    ["5th to 95th percentile", bnRange(row.range[0], row.range[1])],
    ...(isNum(row.centax) ? [["CenTax, static", formatBn(row.centax, 2)]] : []),
    ...(isNum(row.single) ? [["Single take-up draw", formatBn(row.single, 2)]] : []),
  ];
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-lg">
      <div className="mb-2 font-semibold text-slate-800">
        {row.part}, {row.year}
      </div>
      {lines.map(([k, v]) => (
        <div key={k} className="flex items-center justify-between gap-4">
          <span className="text-slate-600">{k}</span>
          <span className="font-medium tabular-nums text-slate-800">{v}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * The bootstrap's 5th-95th percentile range for each year, for the 30 hours and both schemes, with the central cost
 * on the take-up option chosen, CenTax's static cost of the free hours and the 30 hours on the single take-up draw.
 */
export function RangeChart({ data, basis }) {
  const u = getUncertainty(data, basis);
  const centax = getBenchmarks(data)[0]?.underlying_static_by_year_bn ?? {};
  const rows = rangeChartRows(u, centax);
  const values = rows.flatMap((r) => [...r.range, r.central, r.centax, r.single].filter(isNum));
  const lo = Math.floor(Math.min(...values) * 10) / 10;
  const hi = Math.ceil(Math.max(...values) * 10) / 10;
  const ticks = [];
  for (let v = lo; v <= hi + 1e-9; v += 0.2) ticks.push(Math.round(v * 10) / 10);
  const years = u.rows.map((r) => fyLabel(r.year)).join(" and ");
  const description = rows
    .map(
      (r) =>
        `${r.part}, ${r.year}: central ${formatBn(r.central, 2)}, 5th to 95th percentile ${bnRange(r.range[0], r.range[1])}` +
        (isNum(r.centax) ? `, CenTax static ${formatBn(r.centax, 2)}` : "") +
        (isNum(r.single) ? `, single take-up draw ${formatBn(r.single, 2)}` : ""),
    )
    .join("; ");
  const legend = [
    { id: "band", label: "5th to 95th percentile", swatch: <span className="inline-block h-2.5 w-5 rounded-sm" style={{ backgroundColor: RANGE_MARKS.thirty_hours.band }} /> },
    { id: "central", label: `Central (${u.basis.short_label})`, swatch: <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: RANGE_MARKS.thirty_hours.dot }} /> },
    { id: "centax", label: "CenTax, static (30 hours)", swatch: <span className="inline-block h-2.5 w-2.5 rotate-45" style={{ backgroundColor: RANGE_MARKS.centax }} /> },
    { id: "single", label: "Single take-up draw (30 hours)", swatch: <span className="inline-block h-3 w-3 rounded-full border-2 bg-white" style={{ borderColor: RANGE_MARKS.single }} /> },
  ];
  return (
    <figure data-testid="range-chart">
      <div
        role="img"
        aria-labelledby="range-chart-title"
        aria-describedby="range-chart-desc"
        style={{ height: 64 * rows.length + 40 }}
      >
        <p id="range-chart-title" className="sr-only">
          Sampling range of the static cost, {years}, on take-up {u.basis.short_label}
        </p>
        <p id="range-chart-desc" className="sr-only">
          {description}.
        </p>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} layout="vertical" margin={{ top: 4, right: 16, left: 0, bottom: 4 }} barCategoryGap="38%">
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} horizontal={false} />
            <XAxis type="number" domain={[lo, hi]} ticks={ticks} tick={AXIS_STYLE} tickFormatter={(v) => formatBn(v, 1)} />
            <YAxis type="category" dataKey="key" width={96} tickLine={false} axisLine={false} tick={<RangeTick rows={rows} />} />
            <Tooltip cursor={{ fill: colors.gray[50] }} content={<RangeTooltip />} />
            <Bar dataKey="range" isAnimationActive={false} radius={4}>
              {rows.map((r) => (
                <Cell key={r.key} fill={RANGE_MARKS[r.scheme].band} />
              ))}
              <LabelList dataKey="range" content={<RangeEnds />} />
            </Bar>
            <Line dataKey="central" stroke="none" isAnimationActive={false} dot={<CentralDot />} activeDot={false} legendType="none" />
            <Line dataKey="centax" stroke="none" isAnimationActive={false} dot={<CentaxMark />} activeDot={false} legendType="none" />
            <Line dataKey="single" stroke="none" isAnimationActive={false} dot={<SingleMark />} activeDot={false} legendType="none" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-3 flex flex-wrap justify-center gap-x-5 gap-y-2 text-sm text-slate-600">
        {legend.map((l) => (
          <span key={l.id} className="flex items-center gap-2" data-testid={`range-legend-${l.id}`}>
            {l.swatch}
            {l.label}
          </span>
        ))}
      </figcaption>
      <ChartLogo />
    </figure>
  );
}

/** A link to the take-up options box above, opening it first. */
function OptionsLink({ children }) {
  return (
    <a href={`#${TAKE_UP_OPTIONS_ID}`} onClick={() => openDetails(TAKE_UP_OPTIONS_ID)}>
      {children}
    </a>
  );
}

/** The notes under the range chart, each topic in its own closed box of short points. */
export function UncertaintyNotes({ data, basis }) {
  const u = getUncertainty(data, basis);
  const t = getTakeUp(data);
  const b = u.basis;
  const lead = u.rows.find((r) => r.year === LEAD_YEAR) ?? u.rows[0];
  const share = u.age.share_over_limit_by_age_pct;
  const others = [0, 2, 3, 4].map((k) => share[String(k)]);
  const pct = (v) => `${Math.round(v)}%`;
  const centax = getBenchmarks(data)[0]?.underlying_static_by_year_bn ?? {};
  const centaxInside = u.rows.every((r) => {
    const c = centax[String(r.year)];
    return isNum(c) && r.chosen.thirty_hours.p5_bn <= c && c <= r.chosen.thirty_hours.p95_bn;
  });
  const [lo, hi] = [Math.min(u.age.even_spread_bn, u.age.centax_gradient_bn), Math.max(u.age.even_spread_bn, u.age.centax_gradient_bn)];
  const family = b.unit === "family";
  return (
    <div className="mt-4 space-y-2" data-testid="uncertainty-notes">
      <Expandable title="How wide is the range?" testId="note-range" compact>
        <ul className="list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate-700">
          <li>
            A floor on the sampling uncertainty: {u.draws.toLocaleString("en-GB")} resamples of the FRS households
            behind the release, each with all its Microcosm copies.
          </li>
          <li>The weights and calibration are held fixed, and the survey&apos;s clustering is ignored.</li>
          <li>
            The 30 hours&apos; cost in {nb(lead.year)} rests on about {lead.sourceHouseholds} FRS households, an
            effective number of about {lead.effectiveSourceHouseholds} (on the single take-up draw).
          </li>
          <li>
            {centaxInside ? "CenTax's static costs lie inside the range in both years. " : ""}On the single draw the
            bootstrap reproduces{" "}
            <a href={u.sourceUrl} target="_blank" rel="noreferrer">
              the Microcosm team&apos;s
            </a>
            .
          </li>
        </ul>
      </Expandable>
      <Expandable title="Why expected take-up?" testId="take-up-note" compact>
        <ul className="list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate-700">
          {family ? (
            <li>
              On {b.short_label}, the cost is each newly eligible family&apos;s cost if it claims, times{" "}
              <OptionsLink>the flat rate</OptionsLink>.
            </li>
          ) : (
            <li>
              On {b.short_label}, the cost is each newly entitled child&apos;s cost if its family claims and it uses the
              hours, times <OptionsLink>the take-up for its age</OptionsLink>. The rates count both, so they replace the
              dataset&apos;s own draw of who claims.
            </li>
          )}
          <li>
            The single draw is higher: the dataset&apos;s heavily weighted newly eligible families drew a claim more
            often than its rate.
          </li>
          {family ? (
            <li>
              Each percentage point of the rate moves the 30 hours&apos; cost by about £{b.per_point_m[String(lead.year)]}m in{" "}
              {nb(lead.year)}.
            </li>
          ) : null}
          <li>
            {b.id === t.headline ? `${b.short_label} is the headline; ` : `The headline is ${t.bases[t.headline].short_label}; `}
            why, and how it compares with the flat rate by age, is under{" "}
            <a href="?tab=method#assumptions">Who takes up the 30 hours</a> on Methodology.
          </li>
        </ul>
      </Expandable>
      <Expandable title="Age profile: can only push the cost up" testId="note-age" compact>
        <ul className="list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate-700">
          <li>
            The release has few 1-year-olds in families with a parent over £100,000: {pct(share["1"])}, against{" "}
            {pct(Math.min(...others))} to {pct(Math.max(...others))} at the other ages under 5.
          </li>
          <li>No source independent of the survey crosses income with a child&apos;s age.</li>
          <li>
            Spreading the newly entitled 1-to-4-year-olds evenly across those ages, or on CenTax&apos;s gradient between
            under-3s and 3-to-4s, adds about {formatBn(lo, 2)} to {formatBn(hi, 2)} to the 30 hours&apos; cost in{" "}
            {nb(u.age.year)} (on the single take-up draw).
          </li>
        </ul>
      </Expandable>
    </div>
  );
}

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

export default function LandingTab({ data, setting = STATIC_SETTING, basis }) {
  const takeUp = getTakeUp(data);
  const chosen = takeUp.bases[basis ?? takeUp.headline];
  const budget = getBudget(data, chosen.id);
  const dynamic = !isStatic(setting);
  const offsets = labourSupplyOffset(data, setting);
  const cost = budget.rows.map((r, i) => r.total - offsets[i]);
  const [li, setLi] = useState(budget.years.indexOf(LEAD_YEAR));
  const [scheme, setScheme] = useState(null);
  const lead = budget.rows[li];
  // Families and children gaining on the chosen take-up basis (totals only; the breakdowns are on Who gains).
  const recipients = chosen.recipients[lead.year];
  const cmp = { net: chosen.net };
  const chart = costChartData(budget, offsets, dynamic);
  const gapM = netGrossGapM(cmp.net, budget.rows.map((r) => r.total));
  const fy = nb(lead.year);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="landing-tab">
      <Section
        id="at-a-glance"
        title="The cost at a glance"
        lead={`What removing the limit adds to government spending and who gains, opening on ${fyLabel(LEAD_YEAR)}, the first full year, with take-up of the 30 hours on the option chosen above (${chosen.short_label}${chosen.id === takeUp.headline ? ", the headline" : ""}). Click a year's bar to change the year, or a scheme to show it alone.`}
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
        <Expandable title="Show the table" testId="schemes-expandable">
          <SchemesTable />
        </Expandable>
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
            Labour supply on ({labourSupplyLabel(setting)}), an illustrative scenario rather than a forecast (see
            Methodology):{" "}
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

      <Section
        id="uncertainty"
        title="How certain is the cost?"
        lead={`The static cost rests on a small number of survey households, so it carries sampling uncertainty. The chart shows the range for the first full year and the last, on take-up ${chosen.short_label}. Hover over a row for its figures.`}
        boxed={false}
      >
        <div className="panel">
          <RangeChart data={data} basis={chosen.id} />
        </div>
        <div className="mt-4">
          <Expandable title="Show the numbers" testId="uncertainty-expandable" compact>
            <UncertaintyTable data={data} basis={chosen.id} />
          </Expandable>
        </div>
        <UncertaintyNotes data={data} basis={chosen.id} />
      </Section>

    </div>
  );
}
