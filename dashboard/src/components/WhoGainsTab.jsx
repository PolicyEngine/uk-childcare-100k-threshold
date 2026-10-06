"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { colors, schemeColors } from "../lib/colors";
import {
  fyLabel,
  getChildrenByAge,
  getCountries,
  getDeciles,
  getDistributionYears,
  getRecipients,
  LEAD_YEAR,
  SCHEME_LABELS,
  yearHeading,
  SCHEMES,
} from "../lib/dataHelpers";
import { formatCount, formatCurrency, formatPct } from "../lib/formatters";
import { axisDigits, niceAxis } from "../lib/ticks";
import ChartLogo from "./ChartLogo";
import { AXIS_STYLE, CustomTooltip, Section, Select } from "./ui";

export const SUPPRESSED = "too few records";

/** £bn as £m, with a gain that rounds to nothing shown as "under £1m" rather than £0m. */
export function formatM(v) {
  if (typeof v !== "number" || !Number.isFinite(v)) throw new TypeError(`formatM: ${JSON.stringify(v)} is not a number`);
  const m = Math.round(v * 1000);
  if (m === 0 && v >= 0) return "under £1m";
  return `£${m.toLocaleString("en-GB")}m`;
}

export const DECILE_MEASURES = [
  { id: "mean_change_gbp", label: "Average gain, £ a year", format: (v) => formatCurrency(v), axis: (v) => `£${Math.round(v).toLocaleString("en-GB")}` },
  { id: "pct_change", label: "Gain as % of net income", format: (v) => formatPct(v, 2) },
  { id: "share_gaining_pct", label: "Share of households gaining", format: (v) => formatPct(v, 1) },
];

function DecileChart({ rows: raw, measure }) {
  const m = DECILE_MEASURES.find((x) => x.id === measure);
  // A suppressed decile has no bar at all, never a zero bar.
  const rows = raw.map((r) => ({ ...r, [measure]: r.suppressed ? null : r[measure] }));
  const values = rows.map((r) => r[measure]).filter((v) => v !== null);
  const hidden = raw.filter((r) => r.suppressed).map((r) => r.decile);
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
      {hidden.length ? (
        <p className="mt-2 text-center text-sm text-slate-500" data-testid="deciles-suppressed">
          {hidden.length === 1 ? "Decile" : "Deciles"} {listOf(hidden)}: {SUPPRESSED} to show.
        </p>
      ) : null}
      <ChartLogo />
    </>
  );
}

/** "5", "5 and 6", "5, 6 and 7". */
export function listOf(items) {
  if (items.length === 0) throw new Error("listOf: no items");
  return items.length === 1 ? String(items[0]) : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;
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
              <td className="tabular-nums">{r.suppressed ? SUPPRESSED : formatM(r.total_change_bn)}</td>
              <td className="tabular-nums">{r.suppressed ? SUPPRESSED : formatCount(r.families_gaining)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SchemeTable({ recipients }) {
  // children_by_scheme is optional in the schema; getRecipients checks it whenever it is present.
  const kids = recipients.children_by_scheme;
  const withKids = kids !== undefined;
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="scheme-table">
        <thead>
          <tr>
            <th>Scheme</th>
            <th>Families gaining</th>
            {withKids ? <th>Children gaining</th> : null}
          </tr>
        </thead>
        <tbody>
          {SCHEMES.map((sc) => (
            <tr key={sc}>
              <td>
                <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: schemeColors[sc] }} />
                {SCHEME_LABELS[sc]}
              </td>
              <td className="tabular-nums">{formatCount(recipients.by_scheme[sc])}</td>
              {withKids ? <td className="tabular-nums">{formatCount(kids[sc])}</td> : null}
            </tr>
          ))}
          <tr>
            <td>Either or both</td>
            <td className="tabular-nums">{formatCount(recipients.families_gaining)}</td>
            {withKids ? <td className="tabular-nums">{formatCount(recipients.children_gaining)}</td> : null}
          </tr>
          {"families_losing" in recipients ? (
            <tr>
              <td>Families losing (see below)</td>
              <td className="tabular-nums">{formatCount(recipients.families_losing)}</td>
              {withKids ? <td /> : null}
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function AgeTable({ rows }) {
  return (
    <div className="mt-6 overflow-x-auto">
      <table className="data-table" data-testid="age-table">
        <thead>
          <tr>
            <th>Child&apos;s age</th>
            <th>Children gaining</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.label}</td>
              <td className="tabular-nums">{formatCount(r.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function WhoGainsTab({ data }) {
  const years = getDistributionYears(data);
  const [y, setYear] = useState(LEAD_YEAR);
  const [measure, setMeasure] = useState(DECILE_MEASURES[0].id);
  const deciles = getDeciles(data, y);
  const countries = getCountries(data, y);
  const recipients = getRecipients(data, y);
  const ages = getChildrenByAge(data, y);
  const fy = fyLabel(y);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="who-gains-tab">
      <div className="mb-6" data-testid="year-select">
        <Select label="Year" options={years.map((v) => ({ id: v, label: yearHeading(v) }))} value={y} onChange={setYear} />
      </div>
      <Section
        id="deciles"
        title="By household income"
        lead="Only families with a parent above £100,000 gain, so the gains sit almost entirely in the top income deciles."
        details={
          <p>
            Households are ranked by net income adjusted for household size and split into ten equal groups. Deciles
            where fewer than ten survey records gain are not shown. The
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

      <Section
        id="recipients"
        title="Families gaining"
        lead={`Families and children who gain from each scheme in ${fy}; many gain from both.`}
        details={
          <>
            <p>
              Tax-Free Childcare covers children up to 11, so most children gaining are of school age. The 30 hours
              cover children from 9 months, but the model holds ages in whole years and gives no hours at age 0.
            </p>
            {"families_losing" in recipients ? (
              <p>
                A few families lose in the model: once they qualify for the extended hours it switches off the
                universal 15 hours for a 3- or 4-year-old, and the extended hours the data say they use can be fewer.
                In law the universal hours would stay.
              </p>
            ) : null}
          </>
        }
      >
        <SchemeTable recipients={recipients} />
        {ages ? <AgeTable rows={ages} /> : null}
      </Section>

      <Section
        id="nations"
        title="By nation"
        lead="The 30 hours are an English scheme, so nearly all of the cost falls in England."
        detailsTitle="More detail"
        details={
          <p>
            Families in Scotland, Wales and Northern Ireland gain only from Tax-Free Childcare. The devolved
            governments run their own early-years offers, which this reform does not change. Cells resting on fewer
            than ten gaining survey records are not shown.
          </p>
        }
      >
        <CountryTable rows={countries} />
      </Section>
    </div>
  );
}
