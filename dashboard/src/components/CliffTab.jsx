"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { colors, policyColors } from "../lib/colors";
import { cliffSummary, fyLabel, getCliff } from "../lib/dataHelpers";
import { formatCurrency } from "../lib/formatters";
import { niceAxis } from "../lib/ticks";
import ChartLogo from "./ChartLogo";
import { AXIS_STYLE, CustomTooltip, LegendSwatches, Section, Unavailable } from "./ui";

const LIMIT = 100000;
const k = (v) => `£${Math.round(v / 1000)}k`;

function CliffChart({ rows }) {
  const values = rows.flatMap((r) => [r.baseline, r.reform]);
  const xTicks = niceAxis(rows.map((r) => r.earnings), { includeZero: false }).ticks?.filter(
    (t) => t >= rows[0].earnings && t <= rows.at(-1).earnings,
  );
  return (
    <>
      <div style={{ height: 380 }} data-testid="cliff-chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 16, right: 20, left: 10, bottom: 18 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} />
            <XAxis
              dataKey="earnings"
              type="number"
              domain={["dataMin", "dataMax"]}
              ticks={xTicks}
              interval={0}
              tick={AXIS_STYLE}
              tickFormatter={k}
              label={{ value: "Earnings of the higher earner", position: "insideBottom", offset: -12, style: AXIS_STYLE }}
            />
            <YAxis tick={AXIS_STYLE} tickFormatter={k} width={56} {...niceAxis(values, { includeZero: false })} />
            <ReferenceLine x={LIMIT} stroke={colors.gray[400]} strokeDasharray="4 4" label={{ value: "£100,000", position: "top", style: AXIS_STYLE }} />
            <Tooltip
              content={<CustomTooltip formatter={(v) => formatCurrency(v)} labelFormatter={(e) => `Earnings ${formatCurrency(e)}`} />}
            />
            <Line dataKey="baseline" name="With the £100,000 limit" type="linear" stroke={policyColors.baseline} strokeWidth={2.5} dot={false} isAnimationActive={false} />
            <Line dataKey="reform" name="Without the limit" type="linear" stroke={policyColors.reform} strokeWidth={2.5} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <LegendSwatches
        items={[
          { label: "With the £100,000 limit (today)", color: policyColors.baseline },
          { label: "Without the limit", color: policyColors.reform, dashed: true },
        ]}
      />
      <ChartLogo />
    </>
  );
}

export default function CliffTab({ data }) {
  const cliff = getCliff(data);
  if (!cliff) return <Unavailable what="The example household" />;
  const s = cliffSummary(cliff, LIMIT);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="cliff-tab">
      <Section
        id="example"
        title="One family's income"
        lead={`Household net income as one parent's earnings rise, in ${fyLabel(cliff.year)}, with and without the limit.`}
        details={
          <>
            <p>{cliff.description}</p>
            {cliff.notes ? <p>{cliff.notes}</p> : null}
          </>
        }
      >
        <CliffChart rows={cliff.rows} />
      </Section>

      <Section id="what-changes" title="What the reform changes" lead="Why income falls at £100,000 today, and what happens without the limit.">
        <div className="space-y-3 text-sm leading-6 text-slate-600" data-testid="cliff-explainer">
          <p>
            Today a family loses both the 30 funded hours and Tax-Free Childcare in full as soon as either parent&apos;s
            adjusted net income goes above £100,000, even by £1. Nothing tapers: the support stops all at once.
          </p>
          {s && s.drop > 0 ? (
            <p data-testid="cliff-drop">
              For this family, going from {formatCurrency(s.before.earnings)} to {formatCurrency(s.after.earnings)} of
              earnings cuts household net income by {formatCurrency(s.drop)}.{" "}
              {s.recoverAt
                ? `They need earnings of about ${formatCurrency(s.recoverAt)} to get back to the income they had at ${formatCurrency(s.before.earnings)}.`
                : `Even at ${formatCurrency(cliff.rows.at(-1).earnings)} of earnings they have not got back to the income they had at ${formatCurrency(s.before.earnings)}.`}
            </p>
          ) : null}
          <p>
            Without the limit, the support continues at every income, so the dashed line rises smoothly through
            £100,000. Above £100,000 the family still faces the high marginal tax rate from the withdrawal of the
            Personal Allowance, which this reform does not change.
          </p>
        </div>
      </Section>
    </div>
  );
}
