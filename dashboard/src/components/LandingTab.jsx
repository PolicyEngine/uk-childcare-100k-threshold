"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { colors, schemeColors } from "../lib/colors";
import {
  fyLabel,
  getBenchmarks,
  getBudget,
  getBudgetComparisons,
  getMeta,
  getRecipients,
  isNum,
  SCHEME_LABELS,
  SCHEMES,
} from "../lib/dataHelpers";
import { formatBn, formatCurrency, formatPct, formatThousands } from "../lib/formatters";
import { axisDigits, niceAxis } from "../lib/ticks";
import ChartLogo from "./ChartLogo";
import { AXIS_STYLE, CustomTooltip, Section, TopicPanel, Unavailable } from "./ui";

/** A non-breaking hyphen keeps "2029-30" on one line. */
const nb = (year) => fyLabel(year).replace("-", "‑");

/** The pound figure in a published estimate ("£0.7bn a year" -> 0.7), or null. */
export function parseBn(text) {
  const m = /£\s*([\d.]+)\s*(bn|billion|m|million)/i.exec(text ?? "");
  if (!m) return null;
  const v = Number(m[1]);
  if (!Number.isFinite(v)) return null;
  return /^m/i.test(m[2]) ? v / 1000 : v;
}

function Card({ label, value, detail, testId, children }) {
  return (
    <div className="metric-card flex flex-col" data-testid={testId}>
      <p className="eyebrow text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
      {detail ? <p className="mt-1 text-sm text-slate-600">{detail}</p> : null}
      {children}
    </div>
  );
}

function StripLegend({ items }) {
  return (
    <div className="mt-1 flex flex-wrap justify-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
      {items.map((l) => (
        <span key={l.label} className="flex items-center gap-1">
          <span className="inline-block h-2 w-3 rounded-sm" style={{ backgroundColor: l.color }} />
          {l.label}
        </span>
      ))}
    </div>
  );
}

/** Small vertical bars, one per item, the last (or `highlight`) darkest. */
function MiniBars({ items, label, highlight = items.length - 1 }) {
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
            <g key={d.label}>
              <rect x={i * (bw + gap)} y={H - h} width={bw} height={h} rx={2} fill={d.color ?? (i === highlight ? colors.primary[600] : colors.primary[200])} />
              <text x={i * (bw + gap) + bw / 2} y={H + 12} textAnchor="middle" fontSize={10} fill={colors.gray[500]}>
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
function SplitBar({ row }) {
  const total = row.thirty_hours + row.tax_free_childcare || 1;
  const share = Math.max(0, Math.min(1, row.thirty_hours / total));
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
  const values = rows.map((r) => r.total);
  const digits = axisDigits(values);
  return (
    <>
      <div style={{ height: 340 }} data-testid="cost-chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} vertical={false} />
            <XAxis dataKey="label" tick={AXIS_STYLE} />
            <YAxis tick={AXIS_STYLE} tickFormatter={(v) => formatBn(v, digits)} {...niceAxis(values)} />
            <Tooltip cursor={{ fill: colors.gray[100] }} content={<CustomTooltip formatter={(v) => formatBn(v, 2)} />} />
            {SCHEMES.map((s) => (
              <Bar key={s} dataKey={s} name={SCHEME_LABELS[s]} stackId="cost" fill={schemeColors[s]} isAnimationActive={false} maxBarSize={80} />
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

/** A table of figures by year, one row per year and one column per series. */
function YearTable({ years, columns, testId }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid={testId}>
        <thead>
          <tr>
            <th>Year</th>
            {columns.map((c) => (
              <th key={c.label}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {years.map((y, i) => (
            <tr key={y}>
              <td>{fyLabel(y)}</td>
              {columns.map((c) => (
                <td key={c.label} className="tabular-nums">
                  {c.format ? c.format(c.values[i]) : formatBn(c.values[i], 2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ComparisonTopics({ data, budget }) {
  const { years, rows } = budget;
  const total = rows.map((r) => r.total);
  const c = getBudgetComparisons(data);
  const meta = getMeta(data);
  const benchmarks = getBenchmarks(data);
  const last = years.length - 1;
  const fy = nb(years[last]);

  const topics = [
    {
      id: "conservatives",
      title: "The Conservatives' estimate",
      summary: benchmarks ? `${benchmarks[0].figure} against our ${formatBn(benchmarks[0].ours, 2)}` : "Unavailable",
      testId: "topic-conservatives",
      content: benchmarks ? (
        <div className="space-y-4 text-sm leading-6 text-slate-600">
          {benchmarks.map((b) => (
            <div key={b.source} data-testid="benchmark">
              <p>
                The {b.source} put the cost at {b.figure}{" "}
                (<a href={b.url} target="_blank" rel="noreferrer">source</a>). We estimate {formatBn(b.ours, 2)} in {nb(b.year)}.
              </p>
              <p className="mt-2">{b.like_for_like}</p>
            </div>
          ))}
        </div>
      ) : (
        <Unavailable what="The comparison with the Conservatives' estimate" />
      ),
    },
    {
      id: "variants",
      title: "One scheme at a time",
      summary: c.thirtyOnly && c.tfcOnly ? `Lifting each limit alone, ${fy}` : "Unavailable",
      testId: "topic-variants",
      content:
        c.thirtyOnly && c.tfcOnly ? (
          <div className="space-y-4">
            <p className="text-sm leading-6 text-slate-600">
              The cost of removing the limit on one scheme and keeping it on the other. Families can use both schemes
              together, so the two costs need not add up exactly to the cost of removing both limits.
            </p>
            <YearTable
              years={years}
              testId="variants-table"
              columns={[
                { label: "30 hours only", values: c.thirtyOnly },
                { label: "Tax-Free Childcare only", values: c.tfcOnly },
                { label: "Both limits removed", values: total },
              ]}
            />
          </div>
        ) : (
          <Unavailable what="The single-scheme costs" plural />
        ),
    },
    {
      id: "cross-check",
      title: "Another dataset",
      summary: c.crossCheck ? `The cost on ${meta?.cross_check_dataset ?? "a second dataset"}` : "Unavailable",
      testId: "topic-cross-check",
      content: c.crossCheck ? (
        <div className="space-y-4">
          <p className="text-sm leading-6 text-slate-600">
            The same reform run on {meta?.cross_check_dataset ?? "a second dataset"} instead of{" "}
            {meta?.dataset ?? "the main dataset"}. Few survey households earn over £100,000, so a second dataset shows
            how much the estimate depends on which ones are sampled.
          </p>
          <YearTable
            years={years}
            testId="cross-check-table"
            columns={[
              { label: "Main estimate", values: total },
              { label: "Cross-check", values: c.crossCheck },
              {
                label: "Difference",
                values: c.crossCheck.map((v, i) => (total[i] ? (100 * (v - total[i])) / total[i] : NaN)),
                format: (v) => (isNum(v) ? `${v > 0 ? "+" : ""}${formatPct(v, 0)}` : "n/a"),
              },
            ]}
          />
        </div>
      ) : (
        <Unavailable what="The cross-check" />
      ),
    },
    {
      id: "net",
      title: "After other taxes and benefits",
      summary: c.net ? `${formatBn(c.net[last], 2)} net in ${fy}` : "Unavailable",
      testId: "topic-net",
      content: c.net ? (
        <div className="space-y-4">
          <p className="text-sm leading-6 text-slate-600">
            The cost to the government once any knock-on change in other taxes and benefits is included, such as
            Universal Credit childcare support that families stop claiming.
          </p>
          <YearTable
            years={years}
            testId="net-table"
            columns={[
              { label: "Childcare support", values: total },
              { label: "Net of other taxes and benefits", values: c.net },
            ]}
          />
        </div>
      ) : (
        <Unavailable what="The net cost" />
      ),
    },
  ];
  return <TopicPanel topics={topics} testId="comparisons" />;
}

const ASSUMPTIONS = [
  { title: "No change in work", text: "Parents work and earn the same with or without the limit." },
  { title: "30 hours in England only", text: "The funded hours are an English scheme; Scotland, Wales and Northern Ireland have their own." },
  { title: "Tax-Free Childcare UK-wide", text: "The government top-up of 20% of childcare costs is open to families across the UK." },
];

export default function LandingTab({ data }) {
  const budget = getBudget(data);
  const meta = getMeta(data);
  if (!budget) return <Unavailable what="The budget impact" />;
  const final = budget.rows.at(-1);
  const recipients = getRecipients(data, final.year);
  const benchmark = getBenchmarks(data)?.[0];
  const ourAtBenchmark = benchmark ? budget.rows.find((r) => r.year === benchmark.year)?.total : null;
  const theirs = parseBn(benchmark?.figure);
  const fy = nb(final.year);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="landing-tab">
      <Section
        id="at-a-glance"
        title="The cost at a glance"
        lead={`What removing the £100,000 limit on both schemes adds to government spending in ${fyLabel(final.year)}, and who gains.`}
        boxed={false}
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card label={`Cost in ${fy}`} value={formatBn(final.total, 2)} detail="Extra government spending a year" testId="card-cost">
            <MiniBars items={budget.rows.map((r) => ({ label: fyLabel(r.year), value: r.total }))} label="Cost each year" />
          </Card>
          <Card
            label="By scheme"
            value={`${formatBn(final.thirty_hours, 2)} and ${formatBn(final.tax_free_childcare, 2)}`}
            detail={`30 hours and Tax-Free Childcare, ${fy}`}
            testId="card-split"
          >
            <SplitBar row={final} />
          </Card>
          <Card
            label="Families gaining"
            value={recipients ? formatThousands(recipients.families_gaining) : "unavailable"}
            detail={recipients ? `${formatThousands(recipients.children_gaining)} children; ${formatCurrency(recipients.mean_gain_gbp)} a year on average, ${fy}` : null}
            testId="card-families"
          >
            {recipients ? (
              <MiniBars
                items={SCHEMES.map((s) => ({ label: s === "thirty_hours" ? "30 hours" : "Tax-Free Childcare", value: recipients.by_scheme[s], color: schemeColors[s] }))}
                label="Families gaining by scheme"
              />
            ) : null}
          </Card>
          <Card
            label={benchmark ? `Against the ${benchmark.figure.replace(/ a year$/, "")} estimate` : "Against other estimates"}
            value={isNum(ourAtBenchmark) ? formatBn(ourAtBenchmark, 2) : "unavailable"}
            detail={benchmark ? `Our cost in ${nb(benchmark.year)}; the ${benchmark.source} say ${benchmark.figure}` : null}
            testId="card-benchmark"
          >
            {isNum(ourAtBenchmark) && isNum(theirs) ? (
              <MiniBars
                items={[
                  { label: "Conservatives", value: theirs, color: colors.gray[400] },
                  { label: "PolicyEngine", value: ourAtBenchmark, color: colors.primary[600] },
                ]}
                label="Our cost against the published estimate"
              />
            ) : null}
          </Card>
        </div>
      </Section>

      <Section
        id="each-year"
        title="The cost each year"
        lead="Extra spending on each scheme from removing the limit, by fiscal year."
        detailsTitle="How to read this chart"
        details={
          <p>
            Each bar is the extra government spending in that fiscal year when neither the 30 hours nor Tax-Free
            Childcare is withdrawn above £100,000 of adjusted net income. A positive figure is a cost. The 30 hours are
            costed at the hourly rates paid to providers; Tax-Free Childcare at the government top-up families claim.
          </p>
        }
      >
        <CostChart rows={budget.rows} />
      </Section>

      <Section id="assumptions" title="What these figures assume" lead="The main choices behind every cost on this page." boxed={false}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="assumptions">
          {ASSUMPTIONS.map((a) => (
            <div key={a.title} className="panel !p-4">
              <p className="text-sm font-semibold text-slate-800">{a.title}</p>
              <p className="mt-1 text-sm leading-6 text-slate-600">{a.text}</p>
            </div>
          ))}
          <div className="panel !p-4">
            <p className="text-sm font-semibold text-slate-800">Survey data</p>
            <p className="mt-1 text-sm leading-6 text-slate-600" data-testid="assumption-data">
              {meta ? `PolicyEngine UK ${meta.policyengine_uk} on ${meta.dataset}.` : "The dataset is unavailable in this results file."}
            </p>
          </div>
        </div>
      </Section>

      <Section
        id="comparisons"
        title="Comparisons"
        lead="Our cost against the Conservatives' figure, each scheme alone, a second dataset and other taxes and benefits."
        boxed={false}
      >
        <ComparisonTopics data={data} budget={budget} />
      </Section>
    </div>
  );
}
