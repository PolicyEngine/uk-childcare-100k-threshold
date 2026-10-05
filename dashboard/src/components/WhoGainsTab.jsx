"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { colors, schemeColors } from "../lib/colors";
import {
  fyLabel,
  getCountries,
  getDeciles,
  getDistributionYears,
  getRecipients,
  SCHEME_LABELS,
  SCHEMES,
} from "../lib/dataHelpers";
import { formatBn, formatCount, formatCurrency, formatPct } from "../lib/formatters";
import { axisDigits, niceAxis } from "../lib/ticks";
import ChartLogo from "./ChartLogo";
import { AXIS_STYLE, CustomTooltip, Section, Select, Unavailable } from "./ui";

export const DECILE_MEASURES = [
  { id: "mean_change_gbp", label: "Average gain, £ a year", format: (v) => formatCurrency(v), axis: (v) => `£${Math.round(v).toLocaleString("en-GB")}` },
  { id: "pct_change", label: "Gain as % of net income", format: (v) => formatPct(v, 2) },
  { id: "share_gaining_pct", label: "Share of households gaining", format: (v) => formatPct(v, 1) },
];

function DecileChart({ rows, measure }) {
  const m = DECILE_MEASURES.find((x) => x.id === measure);
  const values = rows.map((r) => r[measure]);
  const digits = axisDigits(values);
  const tick = m.axis ?? ((v) => `${v.toFixed(digits)}%`);
  return (
    <>
      <div style={{ height: 340 }} data-testid="decile-chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 10, right: 20, left: 10, bottom: 18 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} vertical={false} />
            <XAxis
              dataKey="decile"
              tick={AXIS_STYLE}
              label={{ value: "Household income decile (1 = lowest)", position: "insideBottom", offset: -12, style: AXIS_STYLE }}
            />
            <YAxis tick={AXIS_STYLE} tickFormatter={tick} {...niceAxis(values)} />
            <Tooltip
              cursor={{ fill: colors.gray[100] }}
              content={<CustomTooltip formatter={(v) => m.format(v)} labelFormatter={(d) => `Decile ${d}`} />}
            />
            <Bar dataKey={measure} name={m.label} fill={colors.primary[600]} isAnimationActive={false} maxBarSize={56} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartLogo />
    </>
  );
}

function CountryTable({ rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="country-table">
        <thead>
          <tr>
            <th>Nation</th>
            <th>Cost</th>
            <th>Families gaining</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.country}>
              <td>{r.country}</td>
              <td className="tabular-nums">{formatBn(r.total_change_bn, 2)}</td>
              <td className="tabular-nums">{formatCount(r.families_gaining)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SchemeTable({ recipients }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="scheme-table">
        <thead>
          <tr>
            <th>Scheme</th>
            <th>Families gaining</th>
          </tr>
        </thead>
        <tbody>
          {SCHEMES.map((s) => (
            <tr key={s}>
              <td>
                <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: schemeColors[s] }} />
                {SCHEME_LABELS[s]}
              </td>
              <td className="tabular-nums">{formatCount(recipients.by_scheme[s])}</td>
            </tr>
          ))}
          <tr>
            <td>Either or both</td>
            <td className="tabular-nums">{formatCount(recipients.families_gaining)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export default function WhoGainsTab({ data }) {
  const years = getDistributionYears(data);
  const [year, setYear] = useState(years.at(-1));
  const [measure, setMeasure] = useState(DECILE_MEASURES[0].id);
  if (!years.length) return <Unavailable what="The distribution of gains" />;
  const y = years.includes(year) ? year : years.at(-1);
  const deciles = getDeciles(data, y);
  const countries = getCountries(data, y);
  const recipients = getRecipients(data, y);
  const fy = fyLabel(y);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="who-gains-tab">
      <div className="mb-6" data-testid="year-select">
        <Select label="Year" options={years.map((v) => ({ id: v, label: fyLabel(v) }))} value={y} onChange={setYear} />
      </div>
      <Section
        id="deciles"
        title="By household income"
        lead="Only families with a parent above £100,000 gain, so the gains sit almost entirely in the top income deciles."
        details={
          <p>
            Households are ranked by net income adjusted for household size and split into ten equal groups. The
            average gain is across every household in the group, including the many with no young children, so it is
            far smaller than the gain to a family that benefits. Net income is after taxes and benefits, before
            housing costs.
          </p>
        }
      >
        <div className="mb-4">
          <Select label="Show" options={DECILE_MEASURES} value={measure} onChange={setMeasure} />
        </div>
        <DecileChart rows={deciles} measure={measure} />
      </Section>

      <Section id="recipients" title="Families gaining" lead={`Families who gain from each scheme in ${fy}; many gain from both.`}>
        <SchemeTable recipients={recipients} />
      </Section>

      <Section
        id="nations"
        title="By nation"
        lead="The 30 hours are an English scheme, so nearly all of the cost falls in England."
        details={
          <p>
            Families in Scotland, Wales and Northern Ireland gain only from Tax-Free Childcare. The devolved
            governments run their own early-years offers, which this reform does not change.
          </p>
        }
      >
        <CountryTable rows={countries} />
      </Section>
    </div>
  );
}
