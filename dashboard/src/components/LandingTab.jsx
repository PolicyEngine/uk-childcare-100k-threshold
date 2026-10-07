"use client";

import { useState } from "react";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { colors, schemeColors } from "../lib/colors";
import {
  fyLabel,
  getBenchmarks,
  getBudget,
  getBudgetComparisons,
  getRange,
  getRecipients,
  getSensitivities,
  getThirtyHoursComponents,
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
export const CENTAX = { year: 2030, staticBn: 0.98, netBn: 0.64 };

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

function StripLegend({ items }) {
  return (
    <div className="mt-1 flex flex-wrap justify-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
      {items.map((l) => (
        <span key={l.label} className="flex items-center gap-1">
          {l.swatch ?? <span className="inline-block h-2 w-3 rounded-sm" style={{ backgroundColor: l.color }} />}
          {l.label}
        </span>
      ))}
    </div>
  );
}

/** Small vertical bars, one per item, the first (or `highlight`) darkest. */
function MiniBars({ items, label, highlight = 0, onSelect, format }) {
  const W = 240;
  const H = 46;
  const max = Math.max(...items.map((d) => d.value), 0) || 1;
  const gap = 8;
  const bw = (W - gap * (items.length - 1)) / items.length;
  return (
    <div className="mt-auto pt-4" data-testid="mini-strip">
      <svg viewBox={`0 0 ${W} ${H + 14}`} className="h-auto w-full" role="img" aria-label={label}>
        {items.map((d, i) => {
          const h = (Math.max(0, d.value) / max) * H;
          return (
            <g
              key={d.label}
              className={onSelect ? "cursor-pointer [&:hover>rect.bar]:opacity-80" : undefined}
              onClick={onSelect ? () => onSelect(i) : undefined}
              role={onSelect ? "button" : undefined}
              aria-label={onSelect ? `${d.label}${format ? `: ${format(d.value)}` : ""}` : undefined}
              aria-pressed={onSelect ? i === highlight : undefined}
            >
              <title>{format ? `${d.label}: ${format(d.value)}` : d.label}</title>
              {/* A full-height hit area, so a short bar is as easy to click as a tall one. */}
              {onSelect ? <rect x={i * (bw + gap)} y={0} width={bw} height={H + 14} fill="transparent" /> : null}
              <rect className="bar" x={i * (bw + gap)} y={H - h} width={bw} height={h} rx={2} fill={d.color ?? (i === highlight ? colors.primary[600] : colors.primary[200])} />
              <text x={i * (bw + gap) + bw / 2} y={H + 12} textAnchor="middle" fontSize={10} fill={i === highlight && onSelect ? colors.gray[800] : colors.gray[500]} fontWeight={i === highlight && onSelect ? 600 : 400}>
                {d.label}
              </text>
            </g>
          );
        })}
        <line x1={0} x2={W} y1={H + 0.5} y2={H + 0.5} stroke={colors.gray[300]} />
      </svg>
    </div>
  );
}

/** One horizontal bar split between the two schemes. */
function SplitBar({ thirty, tfc }) {
  const total = thirty + tfc || 1;
  const share = Math.max(0, Math.min(1, thirty / total));
  return (
    <div className="mt-auto pt-4" data-testid="mini-strip">
      <svg viewBox="0 0 240 18" className="h-auto w-full" role="img" aria-label="Split of the cost between the two schemes">
        <rect x={0} y={0} width={240 * share} height={18} rx={3} fill={schemeColors.thirty_hours} />
        <rect x={240 * share} y={0} width={240 * (1 - share)} height={18} rx={3} fill={schemeColors.tax_free_childcare} />
      </svg>
      <StripLegend
        items={[
          { label: `30 hours ${formatPct(100 * share, 0)}`, color: schemeColors.thirty_hours },
          { label: `Tax-Free Childcare ${formatPct(100 * (1 - share), 0)}`, color: schemeColors.tax_free_childcare },
        ]}
      />
    </div>
  );
}

function CostChart({ rows }) {
  const values = rows.flatMap((r) => [r.total, r.high]);
  const digits = axisDigits(values);
  const axis = niceAxis(values);
  return (
    <>
      <div style={{ height: 340 }} data-testid="cost-chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} vertical={false} />
            <XAxis dataKey="label" tick={AXIS_STYLE} />
            {/* A second, hidden axis on the same years lets the range sit over the stacked bars rather than beside them. */}
            <XAxis dataKey="label" xAxisId="range" hide />
            <YAxis tick={AXIS_STYLE} tickFormatter={(v) => formatBn(v, digits)} {...axis} />
            <Tooltip
              cursor={{ fill: colors.gray[100] }}
              content={<CustomTooltip formatter={(v) => (Array.isArray(v) ? `${formatBn(v[0], 2)} to ${formatBn(v[1], 2)}` : formatBn(v, 2))} />}
            />
            {SCHEMES.map((s) => (
              <Bar key={s} dataKey={s} name={SCHEME_LABELS[s]} stackId="cost" fill={schemeColors[s]} isAnimationActive={false} maxBarSize={80} />
            ))}
            <Bar dataKey="range" name="Range (low to high estimate)" xAxisId="range" fill={colors.gray[800]} barSize={3} isAnimationActive={false} />
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
        <span className="flex items-center gap-2">
          <span className="inline-block h-3 w-[3px]" style={{ backgroundColor: colors.gray[800] }} />
          Range: low to high estimate
        </span>
      </div>
      <ChartLogo />
    </>
  );
}

/** A table of figures by year, one row per series and one column per year. */
function SeriesTable({ years, rows, testId, format = (v) => formatBn(v, 2) }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid={testId}>
        <thead>
          <tr>
            <th />
            {years.map((y) => (
              <th key={y} className="whitespace-nowrap">{yearHeading(y)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <td>{r.label}</td>
              {r.values.map((v, i) => (
                <td key={years[i]} className="whitespace-nowrap tabular-nums">
                  {(r.format ?? format)(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const SENSITIVITY_LABELS = {
  full_30_hour_usage: "Full use of the 30 hours",
  under_ones: "Children aged 9 to 11 months",
  ani_net_of_pension_contributions: "Income net of pension contributions",
  tfc_routed_share: "Less spending through Tax-Free Childcare",
};

/** A sensitivity's name: a known label, or its id written out. */
function sensitivityLabel(id) {
  return id in SENSITIVITY_LABELS ? SENSITIVITY_LABELS[id] : id.replace(/_/g, " ");
}

function SensitivityTable({ sens }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="sensitivity-table">
        <thead>
          <tr>
            <th>Adjustment</th>
            <th className="whitespace-nowrap">Range end</th>
            {sens.years.map((y) => (
              <th key={y} className="whitespace-nowrap">{yearHeading(y)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sens.rows.map((r) => (
            <tr key={r.id}>
              <td className="min-w-[260px]">
                <span className="font-medium text-slate-800">{sensitivityLabel(r.id)}</span>
                <br />
                <span className="text-xs leading-5 text-slate-500">{r.description}</span>
              </td>
              <td className="whitespace-nowrap">{r.side === "low" ? "Low" : "High"}</td>
              {r.values.map((v, i) => (
                <td key={sens.years[i]} className="whitespace-nowrap tabular-nums">
                  {formatSignedM(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BenchmarkComparison({ data }) {
  const benchmark = getBenchmarks(data)[0];
  // CenTax's estimate is for 2030: compare with our last year, 2029-30.
  const last = getBudget(data).rows.at(-1);
  return (
    <div className="space-y-3 text-sm leading-6 text-slate-600" data-testid="benchmark">
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
      <p data-testid="benchmark-centax">
        CenTax estimate a static cost of {formatBn(CENTAX.staticBn, 2)} in {CENTAX.year} for the free hours, and a
        net cost of {formatBn(CENTAX.netBn, 2)}{" "}
        after £0.34bn of extra revenue: £0.21bn of tax from parents who no
        longer keep their income below £100,000, and £0.13bn of tax and National Insurance from partners who enter
        work. CenTax&apos;s {CENTAX.year} is the 2029-30 tax year. The £0.7bn is close to this net figure plus a small
        addition for Tax-Free Childcare.
      </p>
      <div className="max-w-sm">
        <MiniBars
          items={[
            { label: `Ours ${fyLabel(last.year)}`, value: last.thirty_hours, color: schemeColors.thirty_hours },
            { label: `CenTax ${CENTAX.year}`, value: CENTAX.staticBn, color: colors.gray[400] },
          ]}
          label="Our 30 hours cost against CenTax's static cost of the free hours"
          format={(v) => formatBn(v, 2)}
        />
      </div>
      <p data-testid="benchmark-like-for-like">
        Like for like, the comparison is our 30 hours cost with CenTax&apos;s static cost, both before any change
        in how much parents work: {formatBn(last.thirty_hours, 2)} in {nb(last.year)} against{" "}
        {formatBn(CENTAX.staticBn, 2)} in {CENTAX.year}. Our total for both schemes is {formatBn(last.total, 2)}
        in {nb(last.year)}, on the same static basis.
      </p>
    </div>
  );
}

function ThirtyHoursComponents({ data }) {
  const years = getBudget(data).years;
  const comps = getThirtyHoursComponents(data);
  return (
    <div className="space-y-4">
      <p className="text-sm leading-6 text-slate-600">
        The model switches off the universal 15 hours for a 3- or 4-year-old once the family qualifies for the
        extended hours, so part of the gain is offset. The rows add up to the 30 hours cost in the chart.
      </p>
      <SeriesTable
        years={years}
        testId="components-table"
        format={formatSignedM}
        rows={[
          { label: "Extended hours gained", values: comps.extended },
          { label: "Universal hours switched off", values: comps.universal },
          ...(comps.targeted.some((v) => Math.abs(v) >= 0.0005) ? [{ label: "Targeted 2-year-old hours", values: comps.targeted }] : []),
        ]}
      />
    </div>
  );
}

/** True when two series match to within rounding in every year. */
const same = (a, b) => a.every((v, i) => Math.abs(v - b[i]) < 0.0015);

export default function LandingTab({ data }) {
  const budget = getBudget(data);
  const range = getRange(data);
  const [li, setLi] = useState(budget.years.indexOf(LEAD_YEAR));
  const lead = budget.rows[li];
  const recipients = getRecipients(data, lead.year);
  const sens = getSensitivities(data);
  const cmp = getBudgetComparisons(data);
  const rows = budget.rows.map((r, i) => ({ ...r, label: yearHeading(r.year), low: range.low[i], high: range.high[i], range: [range.low[i], range.high[i]] }));
  const fy = nb(lead.year);
  const thirty = budget.rows.map((r) => r.thirty_hours);
  const tfc = budget.rows.map((r) => r.tax_free_childcare);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="landing-tab">
      <Section
        id="at-a-glance"
        title="The cost at a glance"
        lead={`What removing the £100,000 limit on both schemes adds to government spending, and who gains. It opens on ${fyLabel(LEAD_YEAR)}, the first full year; click a year's bar to change it.`}
        boxed={false}
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card
            label={`Cost in ${fy}`}
            value={formatBn(lead.total, 2)}
            detail={`Range ${formatBn(range.low[li], 2)} to ${formatBn(range.high[li], 2)}`}
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
            label="By scheme"
            value={`${formatBn(lead.thirty_hours, 2)} and ${formatBn(lead.tax_free_childcare, 2)}`}
            detail={`30 hours and Tax-Free Childcare, ${fy}`}
            testId="card-split"
          >
            <SplitBar thirty={lead.thirty_hours} tfc={lead.tax_free_childcare} />
          </Card>
          <Card
            label="Families gaining"
            value={formatThousands(recipients.families_gaining)}
            detail={`${formatThousands(recipients.children_gaining)} children${recipients.mean_gain_gbp === null ? "" : `; ${formatCurrency(recipients.mean_gain_gbp)} a year on average`}, ${fy}`}
            testId="card-families"
          >
            <MiniBars
              items={SCHEMES.map((sc) => ({ label: sc === "thirty_hours" ? "30 hours" : "Tax-Free Childcare", value: recipients.by_scheme[sc], color: schemeColors[sc] }))}
              label="Families gaining by scheme"
            />
          </Card>
        </div>
      </Section>

      <Section
        id="each-year"
        title="The cost each year"
        lead="Each bar is our central estimate, split by scheme. The thin black line through it shows how far the cost could move if our main uncertain assumptions are wrong: its bottom is the low estimate and its top the high estimate. The next section shows what sets each end."
        detailsTitle="How to read this chart"
        details={
          <>
            <p>
              Each bar is the extra government spending in that fiscal year when neither the 30 hours nor Tax-Free
              Childcare is withdrawn above £100,000 of adjusted net income, with the policy in force for the whole
              year. {fyLabel(budget.years[0])} is more than half over, so its full-year cost is illustrative. The thin
              line through each bar runs from the low estimate to the high estimate.
            </p>
            {same(cmp.net, budget.rows.map((r) => r.total)) ? (
              <p data-testid="net-note">The cost is the same net of other taxes and benefits: nothing else changes for these families.</p>
            ) : null}
            {same(cmp.thirtyOnly, thirty) && same(cmp.tfcOnly, tfc) ? (
              <p data-testid="variants-note">
                Removing either limit on its own costs the same as that scheme&apos;s part of the bar: the two do not
                interact.
              </p>
            ) : null}
          </>
        }
      >
        <CostChart rows={rows} />
      </Section>

      <Section
        id="sensitivities"
        title="What moves the cost"
        lead="Each row is one assumption we are unsure of, and how much changing it moves the central cost. Adding the rows that lower the cost gives the low estimate; adding the rows that raise it gives the high estimate."
      >
        <SensitivityTable sens={sens} />
      </Section>

      <Section
        id="comparisons"
        title="How our cost compares with the £0.7bn"
        lead="The Conservative plan has been reported as costing about £0.7bn a year. This traces that figure to its source and sets it against our estimate on the same basis."
      >
        <BenchmarkComparison data={data} />
      </Section>

      <Section
        id="thirty-hours"
        title="What makes up the 30 hours cost"
        lead="Newly eligible families gain the extended hours, but the model stops their universal 15 hours at the same time, so the net cost is the first row less the second."
      >
        <ThirtyHoursComponents data={data} />
      </Section>
    </div>
  );
}
