"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { colors, policyColors, schemeColors } from "../lib/colors";
import {
  cliffSummary,
  fyLabel,
  getChildrenByAge,
  getCliff,
  getDeciles,
  getDistributionYears,
  getGroups,
  getHouseholdGrid,
  getRecipients,
  householdRows,
  LEAD_YEAR,
  SCHEME_LABELS,
  yearHeading,
  SCHEMES,
} from "../lib/dataHelpers";
import { formatCount, formatCurrency, formatPct } from "../lib/formatters";
import { axisDigits, niceAxis } from "../lib/ticks";
import ChartLogo from "./ChartLogo";
import { AXIS_STYLE, CustomTooltip, LegendSwatches, Section, Select } from "./ui";

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
            <Bar dataKey={measure} name={m.label} fill={colors.primary[600]} radius={[4, 4, 0, 0]} isAnimationActive={false} maxBarSize={56} />
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

const LIMIT = 100000;
const k = (v) => `£${Math.round(v / 1000)}k`;

function CliffChart({ rows }) {
  const values = rows.flatMap((r) => [r.baseline, r.reform]);
  // A tick every £10,000, so the earnings around the limit can be read off the axis.
  const xTicks = Array.from({ length: Math.floor(rows.at(-1).earnings / 10000) + 1 }, (_, i) => i * 10000);
  return (
    <>
      <div style={{ height: 380 }} data-testid="cliff-chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 16, right: 20, left: 10, bottom: 18 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} />
            <XAxis
              dataKey="earnings"
              type="number"
              domain={[0, "dataMax"]}
              ticks={xTicks}
              interval={0}
              tick={AXIS_STYLE}
              tickFormatter={k}
              label={{ value: "Earnings of the higher earner", position: "insideBottom", offset: -12, style: AXIS_STYLE }}
            />
            <YAxis tick={AXIS_STYLE} tickFormatter={k} width={56} {...niceAxis([0, ...values])} />
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

function HouseholdSection({ data }) {
  const grid = getHouseholdGrid(data);
  const cliff = getCliff(data);
  const [choice, setChoice] = useState(grid.default);
  const family = householdRows(grid, choice);
  const s = cliffSummary(family, LIMIT);
  const set = (key) => (id) => setChoice((c) => ({ ...c, [key]: id }));
  return (
    <Section
      id="household"
      title="How does the limit affect your family?"
      lead={`Choose the parents, the children and how much the family spends on childcare. The chart shows the family's net income after paying for childcare in ${fyLabel(grid.year)}, as the higher earner's pay rises from £0 to £140,000. The solid line is today's rules: once pay passes £100,000 the family loses the 30 funded hours and Tax-Free Childcare at once, so its income falls. The dashed line removes the limit, so the support continues and income keeps rising. Where the two lines meet, the limit makes no difference to this family. It opens on a couple with two young children, who hit the cliff.`}
      details={
        <>
        <p data-testid="cliff-drop">
          {s.drop > 0
            ? `Going from ${formatCurrency(s.before.earnings)} to ${formatCurrency(s.after.earnings)} of earnings cuts this family's net income, after childcare costs, by ${formatCurrency(s.drop)}. ${
                s.recoverAt
                  ? `They need earnings of about ${formatCurrency(s.recoverAt)} to get back to where they were.`
                  : `Even at ${formatCurrency(family.rows.at(-1).earnings)} they have not got back to where they were.`
              } Without the limit there is no drop.`
            : "This family does not lose income at £100,000: it gets no support that the limit withdraws."}
        </p>
          <p>
            Today a family loses the working-parent funded hours and Tax-Free Childcare in full as soon as either
            parent&apos;s adjusted net income goes above £100,000, even by £1: nothing tapers. A child under 3 loses up
            to 30 funded hours (a 2-year-old who also qualifies for the targeted 15 hours keeps those). A 3- or
            4-year-old loses the additional 15 hours and keeps the universal 15, which have no income test. Tax-Free
            Childcare covers children up to 11, so a school-age child loses only that.
          </p>
          <p>
            Without the limit the support continues at every income. Above £100,000 the family still faces the high
            marginal tax rate from the withdrawal of the Personal Allowance, which this reform does not change.
          </p>
          {cliff.notes ? <p>{cliff.notes}</p> : null}
        </>
      }
    >
      <div className="mb-5 flex flex-wrap gap-x-6 gap-y-3" data-testid="household-form">
        <Select label="Parents" options={grid.options.parents} value={choice.parent} onChange={set("parent")} />
        <Select label="Children" options={grid.options.children} value={choice.children} onChange={set("children")} />
        <Select label="Childcare spending" options={grid.options.spend_per_child} value={choice.spend_per_child} onChange={set("spend_per_child")} />
      </div>
      <CliffChart rows={family.rows} />
    </Section>
  );
}

/** A breakdown's lead: what the chart shows, the largest group's share of the published total, and why. */
function groupLead(rows, fy, noun, why) {
  if (!rows) return "";
  const shown = rows.filter((r) => !r.suppressed);
  const total = shown.reduce((t, r) => t + r.total_change_bn, 0);
  const top = sortGroups(shown, "total_change_bn")[0];
  const share = total > 0 ? Math.round((100 * top.total_change_bn) / total) : 0;
  return `Extra spending on the two schemes in ${fy}, and the families gaining, by ${noun}, largest first. ${why(top)} ${top.name}: ${formatM(top.total_change_bn)}, ${share}% of the spending shown. Switch between spending and families gaining with Show.`;
}

const BREAKDOWNS = [
  { id: "income", label: "Household income" },
  { id: "family_type", label: "Family type" },
  { id: "region", label: "Region" },
];

const GROUP_MEASURES = [
  { id: "total_change_bn", label: "Extra spending", format: (v) => formatM(v), axis: (v) => `£${Math.round(v * 1000)}m` },
  { id: "families_gaining", label: "Families gaining", format: (v) => formatCount(v), axis: (v) => `${Math.round(v / 1000)}k` },
];

/** Largest first; suppressed cells last, in their original order. */
export function sortGroups(rows, measure) {
  return [...rows].sort((a, b) => (a.suppressed - b.suppressed) || ((b[measure] ?? 0) - (a[measure] ?? 0)));
}

function GroupChart({ rows: raw, measure }) {
  const m = GROUP_MEASURES.find((x) => x.id === measure);
  const rows = sortGroups(raw, measure).map((r) => ({ ...r, [measure]: r.suppressed ? null : r[measure] }));
  const hidden = raw.filter((r) => r.suppressed).map((r) => r.name);
  const values = rows.map((r) => r[measure]).filter((v) => v !== null);
  return (
    <>
      <div style={{ height: Math.max(220, rows.length * 34 + 40) }} data-testid="group-chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 24, left: 10, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} horizontal={false} />
            <XAxis type="number" tick={AXIS_STYLE} tickFormatter={m.axis} {...niceAxis(values)} />
            <YAxis type="category" dataKey="name" tick={AXIS_STYLE} width={190} interval={0} />
            <Tooltip cursor={{ fill: colors.gray[100] }} content={<CustomTooltip formatter={(v) => m.format(v)} />} />
            <Bar dataKey={measure} name={m.label} fill={colors.primary[600]} radius={[0, 4, 4, 0]} isAnimationActive={false} maxBarSize={22} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {hidden.length ? (
        <p className="mt-2 text-center text-sm text-slate-500" data-testid="groups-suppressed">
          {listOf(hidden)}: {SUPPRESSED} to show.
        </p>
      ) : null}
      <ChartLogo />
    </>
  );
}

function GroupTable({ rows, header }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="group-table">
        <thead>
          <tr>
            <th>{header}</th>
            <th>Extra spending</th>
            <th>Families gaining</th>
          </tr>
        </thead>
        <tbody>
          {sortGroups(rows, "total_change_bn").map((r) => (
            <tr key={r.name}>
              <td>{r.name}</td>
              <td className="tabular-nums">{r.suppressed ? SUPPRESSED : formatM(r.total_change_bn)}</td>
              <td className="tabular-nums">{r.suppressed ? SUPPRESSED : formatCount(r.families_gaining)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BreakdownSection({ data, year, yearSelect }) {
  const [by, setBy] = useState("income");
  const [decileMeasure, setDecileMeasure] = useState(DECILE_MEASURES[0].id);
  const [groupMeasure, setGroupMeasure] = useState(GROUP_MEASURES[0].id);
  const groupRows = by === "income" ? null : getGroups(data, year, by);
  const fy = fyLabel(year);
  const leads = {
    income:
      `The average gain per household in ${fy} in each tenth of households, ranked from the lowest to the highest income. Only families where a parent earns over £100,000 gain, so the gains sit almost entirely in the highest-income tenth, with a little in the two below it. The averages include every household in the group, most of which have no young children, so they are far smaller than the gain to a family that benefits. Switch to see the gain as a share of net income, or the share of households that gain.`,
    family_type: groupLead(groupRows, fy, "family type",
      (top) => `${top.name} receive the largest share. To gain, a family must have a parent over £100,000 and pass the minimum earnings test, so almost all the gains go to couples; lone parents earning over £100,000 are few.`),
    region: groupLead(groupRows, fy, "region",
      (top) => `${top.name} receives the largest share, because more parents there earn over £100,000. The 30 hours are an English scheme, so families in Scotland, Wales and Northern Ireland gain only from Tax-Free Childcare.`),
  };
  const details = {
    income: (
      <p>
        Households are ranked by net income adjusted for household size and split into ten equal groups. The average
        gain is across every household in the group, including the many with no young children, so it is far smaller
        than the gain to a family that benefits. Net income is after taxes and benefits, before housing costs.
      </p>
    ),
    family_type: (
      <p>
        Families are benefit units: one adult or a couple and their children. Children are those the model counts as
        dependent. &ldquo;Other family&rdquo; covers anything else, such as a benefit unit whose children the model does not
        hold with it.
      </p>
    ),
    region: (
      <p>
        Regions are the twelve ITL1 regions and nations. The devolved governments run their own early-years offers,
        which this reform does not change.
      </p>
    ),
  };
  return (
    <Section
      id="breakdown"
      title="Where do the gains go?"
      lead={leads[by]}
      details={
        <>
          {details[by]}
          <p>Cells resting on fewer than ten gaining survey records are not shown, and a second cell is hidden with a lone one so it cannot be worked out from the total.</p>
          {groupRows ? <GroupTable rows={groupRows} header={by === "region" ? "Region" : "Family type"} /> : null}
        </>
      }
    >
      <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-3">
        <Select label="Break down by" options={BREAKDOWNS} value={by} onChange={setBy} />
        {yearSelect}
        {by === "income" ? (
          <Select label="Show" options={DECILE_MEASURES} value={decileMeasure} onChange={setDecileMeasure} />
        ) : (
          <Select label="Show" options={GROUP_MEASURES} value={groupMeasure} onChange={setGroupMeasure} />
        )}
      </div>
      {by === "income" ? (
        <DecileChart rows={getDeciles(data, year)} measure={decileMeasure} />
      ) : (
        <GroupChart rows={groupRows} measure={groupMeasure} />
      )}
    </Section>
  );
}

const RECIPIENT_VIEWS = [
  { id: "families", label: "Families, by scheme" },
  { id: "children", label: "Children, by scheme" },
  { id: "ages", label: "Children, by age" },
];

function RecipientsChart({ recipients, view }) {
  const kids = recipients.children_by_scheme;
  const key = view === "families" ? "families" : "children";
  const rows = [
    ...SCHEMES.map((sc) => ({
      name: SCHEME_LABELS[sc],
      value: key === "families" ? recipients.by_scheme[sc] : kids[sc],
      color: schemeColors[sc],
    })),
    {
      name: "Either or both",
      value: key === "families" ? recipients.families_gaining : recipients.children_gaining,
      color: colors.gray[500],
    },
  ];
  const label = key === "families" ? "Families gaining" : "Children gaining";
  return (
    <>
      <div style={{ height: 220 }} data-testid="recipients-chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 24, left: 10, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} horizontal={false} />
            <XAxis type="number" tick={AXIS_STYLE} tickFormatter={(v) => `${Math.round(v / 1000)}k`} {...niceAxis(rows.map((r) => r.value))} />
            <YAxis type="category" dataKey="name" tick={AXIS_STYLE} width={150} interval={0} />
            <Tooltip cursor={{ fill: colors.gray[100] }} content={<CustomTooltip formatter={(v) => formatCount(v)} />} />
            <Bar dataKey="value" name={label} radius={[0, 4, 4, 0]} isAnimationActive={false} maxBarSize={28}>
              {rows.map((r) => (
                <Cell key={r.name} fill={r.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartLogo />
    </>
  );
}

function AgeChart({ rows }) {
  return (
    <>
      <div style={{ height: 260 }} data-testid="age-chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 10, right: 20, left: 10, bottom: 18 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} vertical={false} />
            <XAxis dataKey="label" tick={AXIS_STYLE} interval={0} label={{ value: "Child's age", position: "insideBottom", offset: -12, style: AXIS_STYLE }} />
            <YAxis tick={AXIS_STYLE} tickFormatter={(v) => `${Math.round(v / 1000)}k`} {...niceAxis(rows.map((r) => r.value))} />
            <Tooltip cursor={{ fill: colors.gray[100] }} content={<CustomTooltip formatter={(v) => formatCount(v)} />} />
            <Bar dataKey="value" name="Children gaining" fill={colors.primary[600]} radius={[4, 4, 0, 0]} isAnimationActive={false} maxBarSize={56} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartLogo />
    </>
  );
}

function AgeTable({ rows }) {
  return (
    <div className="overflow-x-auto">
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
  const recipients = getRecipients(data, y);
  const ages = getChildrenByAge(data, y);
  const fy = fyLabel(y);
  const [view, setView] = useState("families");
  // The children views need children_by_scheme, which the schema leaves optional.
  const views = RECIPIENT_VIEWS.filter((v) => v.id === "families" || recipients.children_by_scheme !== undefined);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="who-gains-tab">
      <HouseholdSection data={data} />

      <BreakdownSection data={data} year={y} yearSelect={
        <div data-testid="year-select">
          <Select label="Year" options={years.map((v) => ({ id: v, label: yearHeading(v) }))} value={y} onChange={setYear} />
        </div>
      } />

      <Section
        id="recipients"
        title="How many families and children gain?"
        lead={`Families and children who gain from each scheme in ${fy}, the year chosen above. A family gains if its support rises by more than £1 a year. Many gain from both schemes, so the two scheme bars add up to more than "either or both". Use Show to count children instead, or to see the children gaining by age: Tax-Free Childcare covers children up to 11, so many of them are of school age.`}
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
            <SchemeTable recipients={recipients} />
            {ages ? <div className="mt-4"><AgeTable rows={ages} /></div> : null}
          </>
        }
      >
        <div className="mb-4">
          <Select label="Show" options={views} value={view} onChange={setView} />
        </div>
        {view === "ages" ? <AgeChart rows={ages} /> : <RecipientsChart recipients={recipients} view={view} />}
      </Section>
    </div>
  );
}
