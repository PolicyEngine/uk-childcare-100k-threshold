"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { colors, schemeColors } from "../lib/colors";
import {
  fyLabel,
  getBenchmarks,
  getBudget,
  getBudgetComparisons,
  getCrossCheck,
  getRange,
  getRecipients,
  getRecipientsCrossCheck,
  getSensitivities,
  getThirtyHoursComponents,
  getValidation,
  isNum,
  SCHEME_LABELS,
  SCHEMES,
} from "../lib/dataHelpers";
import { formatBn, formatCurrency, formatPct, formatThousands } from "../lib/formatters";
import { axisDigits, niceAxis } from "../lib/ticks";
import ChartLogo from "./ChartLogo";
import { AXIS_STYLE, CustomTooltip, Section, TopicPanel, Unavailable } from "./ui";

/** A non-breaking hyphen keeps "2026-27" on one line. */
const nb = (year) => fyLabel(year).replace("-", "‑");

/** £bn as a signed £m figure: -0.006 -> "-£6m", 0.362 -> "+£362m". */
export function formatSignedM(v) {
  if (!isNum(v)) return "unavailable";
  const m = Math.round(v * 1000);
  return `${m > 0 ? "+" : m < 0 ? "-" : ""}£${Math.abs(m).toLocaleString("en-GB")}m`;
}

/** The pound figure in a published estimate ("£0.7bn a year" -> 0.7), or null. */
export function parseBn(text) {
  const m = /£\s*([\d.]+)\s*(bn|billion|m|million)/i.exec(text ?? "");
  if (!m) return null;
  const v = Number(m[1]);
  if (!Number.isFinite(v)) return null;
  return /^m/i.test(m[2]) ? v / 1000 : v;
}

/** How far a dataset's count of people on £100,000 or more is from HMRC's, as a % (from the validation rows). */
export function highEarnerGap(data, datasetPattern) {
  const row = getValidation(data)?.find((r) => /£100,000/.test(r.label) && datasetPattern.test(r.dataset));
  return row && row.official ? (100 * (row.model - row.official)) / row.official : null;
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
function MiniBars({ items, label, highlight = 0 }) {
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

/** Our low-high range as a band with the central estimate, and a published figure marked against it. */
function RangeStrip({ low, central, high, theirs, caption }) {
  const W = 240;
  const H = 30;
  const max = Math.max(high, theirs) * 1.08;
  const x = (v) => (Math.max(0, v) / max) * W;
  return (
    <div className="mt-auto pt-4" data-testid="mini-strip">
      <svg viewBox={`0 -4 ${W} ${H + 8}`} className="h-auto w-full" role="img" aria-label="The published figure against our range">
        <line x1={0} x2={W} y1={H / 2} y2={H / 2} stroke={colors.gray[200]} strokeWidth={2} />
        <rect x={x(low)} y={H / 2 - 7} width={x(high) - x(low)} height={14} rx={3} fill={colors.primary[200]} />
        <line x1={x(central)} x2={x(central)} y1={H / 2 - 9} y2={H / 2 + 9} stroke={colors.primary[800]} strokeWidth={3} />
        <line x1={x(theirs)} x2={x(theirs)} y1={0} y2={H} stroke={colors.gray[500]} strokeWidth={2} strokeDasharray="3 2" />
      </svg>
      {caption ? <p className="mt-1 text-xs text-slate-500">{caption}</p> : null}
      <StripLegend
        items={[
          { label: "Our range", color: colors.primary[200] },
          { label: "Our central", swatch: <span className="inline-block h-3 w-[3px]" style={{ backgroundColor: colors.primary[800] }} /> },
          { label: "Party's figure", swatch: <span className="inline-block h-3 border-l-2 border-dashed" style={{ borderColor: colors.gray[500] }} /> },
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
            <Bar dataKey="range" name="Low to high" xAxisId="range" fill={colors.gray[800]} barSize={3} isAnimationActive={false} />
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
          Low to high range
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
              <th key={y} className="whitespace-nowrap">{fyLabel(y)}</th>
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

function SensitivityTable({ sens }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="sensitivity-table">
        <thead>
          <tr>
            <th>Adjustment</th>
            <th className="whitespace-nowrap">Range end</th>
            {sens.years.map((y) => (
              <th key={y} className="whitespace-nowrap">{fyLabel(y)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sens.rows.map((r) => (
            <tr key={r.id}>
              <td className="min-w-[260px]">
                <span className="font-medium text-slate-800">{SENSITIVITY_LABELS[r.id] ?? r.id.replace(/_/g, " ")}</span>
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

function ComparisonTopics({ data, range }) {
  const benchmark = getBenchmarks(data)?.[0];
  const cross = getCrossCheck(data);
  const comps = getThirtyHoursComponents(data);
  const years = range.years;
  const theirs = parseBn(benchmark?.figure);
  // CenTax's estimate, which the reported figure is based on, is for 2030: compare with our last year.
  const last = range.years.length - 1;
  const first = { low: range.low[last], central: range.central[last], high: range.high[last] };
  const microGap = highEarnerGap(data, /microcosm|populace/i);
  const efrsGap = highEarnerGap(data, /enhanced/i);
  const where = !isNum(theirs)
    ? null
    : theirs < first.low
      ? "below our whole range"
      : theirs > first.high
        ? "above our whole range"
        : theirs > first.central
          ? "within our range, above our central estimate"
          : "within our range, below our central estimate";
  const crossFamilies = cross ? years.map((y) => getRecipientsCrossCheck(data, y)?.families_gaining) : null;

  const topics = [
    {
      id: "conservatives",
      title: "The Conservatives' figure",
      summary: benchmark ? `${benchmark.figure}, as reported` : "Unavailable",
      testId: "topic-conservatives",
      content: benchmark ? (
        <div className="space-y-3 text-sm leading-6 text-slate-600" data-testid="benchmark">
          <p>
            <a href={benchmark.url} target="_blank" rel="noreferrer">
              City AM
            </a>{" "}
            reports the cost of the party&apos;s plan as about £700m a year and says it is based on{" "}
            {benchmark.underlying_source_url ? (
              <a href={benchmark.underlying_source_url} target="_blank" rel="noreferrer">
                CenTax&apos;s report
              </a>
            ) : (
              "CenTax's report"
            )}
            . The party&apos;s{" "}
            {benchmark.announcement_url ? (
              <a href={benchmark.announcement_url} target="_blank" rel="noreferrer">
                announcement
              </a>
            ) : (
              "announcement"
            )}{" "}
            gives no figure, year or method.
          </p>
          <p data-testid="benchmark-centax">
            CenTax estimate a net cost of £640m in 2030 for removing the limit on the free childcare hours only: a
            static cost of £980m, less £340m of tax from parents who stop holding their income below £100,000. Their
            figure does not include Tax-Free Childcare.
          </p>
          <p data-testid="benchmark-where">
            Ours is the static cost of both schemes, before any change in how much parents work and before the civil
            service savings the party proposes to pay for it, so the figures are not like for like.
            {where ? ` Against our range for ${nb(years[last])}, the year nearest 2030, £0.7bn sits ${where}.` : ""}
          </p>
        </div>
      ) : (
        <Unavailable what="The Conservatives' figure" />
      ),
    },
    {
      id: "cross-check",
      title: "Microcosm cross-check",
      summary: "A second dataset, higher because it holds more high earners",
      testId: "topic-cross-check",
      content: cross ? (
        <div className="space-y-4">
          <p className="text-sm leading-6 text-slate-600" data-testid="cross-check-reason">
            {isNum(microGap)
              ? `Microcosm holds ${formatPct(Math.abs(microGap), 0)} ${microGap >= 0 ? "more" : "fewer"} people on £100,000 or more than HMRC projects${isNum(efrsGap) ? ` (the Enhanced FRS ${formatPct(Math.abs(efrsGap), 0)} ${efrsGap >= 0 ? "more" : "fewer"})` : ""}, so it reaches more families and costs more.`
              : "The same reform run on Microcosm, a second dataset."}
          </p>
          <SeriesTable
            years={years}
            testId="cross-check-table"
            rows={[
              { label: "Microcosm cost", values: cross.total },
              { label: "of which 30 hours", values: cross.thirty_hours },
              { label: "of which Tax-Free Childcare", values: cross.tax_free_childcare },
              ...(crossFamilies?.every(isNum) ? [{ label: "Families gaining", values: crossFamilies, format: formatThousands }] : []),
            ]}
          />
        </div>
      ) : (
        <Unavailable what="The cross-check" />
      ),
    },
    {
      id: "thirty-hours",
      title: "Inside the 30 hours cost",
      summary: "Extra hours gained, less universal hours switched off",
      testId: "topic-thirty-hours",
      content: comps ? (
        <div className="space-y-4">
          <p className="text-sm leading-6 text-slate-600">
            The model switches off the universal 15 hours for a 3- or 4-year-old once the family qualifies for the
            extended hours, so part of the gain is offset. The two rows add up to the 30 hours cost in the chart.
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
      ) : (
        <Unavailable what="The 30 hours breakdown" />
      ),
    },
  ];
  return <TopicPanel topics={topics} testId="comparisons" />;
}

const ASSUMPTIONS = [
  { title: "No change in work", text: "Parents work and earn the same with or without the limit." },
  { title: "30 hours in England only", text: "The funded hours are an English scheme; Scotland, Wales and Northern Ireland have their own." },
  { title: "Tax-Free Childcare UK-wide", text: "The government top-up of 20% of childcare costs is open to families across the UK." },
  { title: "Enhanced FRS data", text: "The headline uses the Enhanced FRS, with Microcosm as a cross-check of the totals." },
];

/** True when two series match to within rounding in every year. */
const same = (a, b) => a && b && a.every((v, i) => Math.abs(v - b[i]) < 0.0015);

export default function LandingTab({ data }) {
  const budget = getBudget(data);
  const range = getRange(data);
  if (!budget || !range) return <Unavailable what="The budget impact" />;
  const first = budget.rows[0];
  const recipients = getRecipients(data, first.year);
  const benchmark = getBenchmarks(data)?.[0];
  const theirs = parseBn(benchmark?.figure);
  const sens = getSensitivities(data);
  const cmp = getBudgetComparisons(data);
  const rows = budget.rows.map((r, i) => ({ ...r, low: range.low[i], high: range.high[i], range: [range.low[i], range.high[i]] }));
  const fy = nb(first.year);
  const thirty = budget.rows.map((r) => r.thirty_hours);
  const tfc = budget.rows.map((r) => r.tax_free_childcare);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="landing-tab">
      <Section
        id="at-a-glance"
        title="The cost at a glance"
        lead={`What removing the £100,000 limit on both schemes adds to government spending in ${fyLabel(first.year)}, the first year, and who gains.`}
        boxed={false}
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card
            label={`Cost in ${fy}`}
            value={formatBn(first.total, 2)}
            detail={`Range ${formatBn(range.low[0], 2)} to ${formatBn(range.high[0], 2)}`}
            testId="card-cost"
          >
            <MiniBars items={budget.rows.map((r) => ({ label: fyLabel(r.year), value: r.total }))} label="Central cost each year" />
          </Card>
          <Card
            label="By scheme"
            value={`${formatBn(first.thirty_hours, 2)} and ${formatBn(first.tax_free_childcare, 2)}`}
            detail={`30 hours and Tax-Free Childcare, ${fy}`}
            testId="card-split"
          >
            <SplitBar thirty={first.thirty_hours} tfc={first.tax_free_childcare} />
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
            label="The Conservatives' figure"
            value={benchmark ? benchmark.figure : "unavailable"}
            detail={
              benchmark ? (
                <>
                  The party&apos;s estimate as reported by{" "}
                  <a href={benchmark.url} target="_blank" rel="noreferrer">
                    City AM
                  </a>
                  , based on CenTax&apos;s net cost of the free hours alone in 2030; not like for like
                </>
              ) : null
            }
            testId="card-benchmark"
          >
            {isNum(theirs) ? (
              <RangeStrip
                low={range.low.at(-1)}
                central={range.central.at(-1)}
                high={range.high.at(-1)}
                theirs={theirs}
                caption={`Against our range for ${nb(range.years.at(-1))}, the year nearest 2030`}
              />
            ) : null}
          </Card>
        </div>
      </Section>

      <Section
        id="each-year"
        title="The cost each year"
        lead="Central cost by scheme on the Enhanced FRS, with the low-to-high range around it."
        detailsTitle="How to read this chart"
        details={
          <>
            <p>
              Each bar is the extra government spending in that fiscal year when neither the 30 hours nor Tax-Free
              Childcare is withdrawn above £100,000 of adjusted net income, with the policy in force for the whole
              year. The line through each bar runs from the low to the high end of the range, built from the
              adjustments below.
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
        lead="The adjustments that build the low and high ends of the range, each added to the central cost."
      >
        {sens ? <SensitivityTable sens={sens} /> : <Unavailable what="The sensitivities" plural />}
      </Section>

      <Section id="assumptions" title="What these figures assume" lead="The main choices behind every cost on this page." boxed={false}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="assumptions">
          {ASSUMPTIONS.map((a) => (
            <div key={a.title} className="panel !p-4">
              <p className="text-sm font-semibold text-slate-800">{a.title}</p>
              <p className="mt-1 text-sm leading-6 text-slate-600">{a.text}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section
        id="comparisons"
        title="Comparisons"
        lead="The Conservatives' figure, the Microcosm cross-check, and what makes up the 30 hours cost."
        boxed={false}
      >
        <ComparisonTopics data={data} range={range} />
      </Section>
    </div>
  );
}

