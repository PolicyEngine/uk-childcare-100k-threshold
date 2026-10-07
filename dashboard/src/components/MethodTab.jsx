"use client";

import { fyLabel, getAssumptions, getLimitations, getMeta, getReform, getValidation, META_PROVENANCE } from "../lib/dataHelpers";
import { formatBn, formatCount, formatCurrency, formatPct } from "../lib/formatters";
import { Section } from "./ui";

/** A value in its stated unit: "£bn" -> £0.95bn, "£" -> £1,234, anything else a count followed by the unit. */
export function formatUnit(value, unit) {
  if (unit === "£bn") return formatBn(value, 2);
  if (unit === "£m") return `${formatCurrency(value)}m`;
  if (unit === "£") return formatCurrency(value);
  if (unit === "%") return formatPct(value, 1);
  if (unit === "£/hour") return `£${value.toFixed(2)}`;
  return formatCount(value);
}

function VersionsTable({ meta }) {
  const rows = [
    ["policyengine.py", meta.policyengine],
    ["PolicyEngine UK", meta.policyengine_uk],
    ["Dataset", `${meta.dataset} (revision ${meta.dataset_revision})`],
    ...META_PROVENANCE.filter(([k]) => k in meta).map(([k, label]) => [label, meta[k]]),
    ["Results generated", meta.generated_at],
    ["Code revision", meta.git_revision],
  ];
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="versions-table">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td className="font-medium text-slate-700">{k}</td>
              <td className="break-all">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ValidationTable({ rows }) {
  // One dataset in the file: the dataset column appears only if rows from more than one are present.
  const datasets = [...new Set(rows.filter((r) => "dataset" in r).map((r) => r.dataset))];
  const showDataset = datasets.length > 1;
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="validation-table">
        <thead>
          <tr>
            <th>Measure</th>
            {showDataset ? <th>Dataset</th> : null}
            <th>Year</th>
            <th>PolicyEngine</th>
            <th>Official</th>
            <th>Ratio</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.label}-${r.year}-${r.dataset}`}>
              <td>
                {r.label}
                {"note" in r ? <span className="mt-1 block text-xs leading-5 text-slate-500">{r.note}</span> : null}
              </td>
              {showDataset ? <td>{r.dataset}</td> : null}
              <td className="whitespace-nowrap">{fyLabel(r.year)}</td>
              <td className="tabular-nums">{formatUnit(r.model, r.unit)}</td>
              <td className="tabular-nums">{formatUnit(r.official, r.unit)}</td>
              <td className="tabular-nums">{r.official === 0 ? "n/a" : (r.model / r.official).toFixed(2)}</td>
              <td className="min-w-[220px]">
                <a href={r.url} target="_blank" rel="noreferrer">
                  {r.source}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Column heading for a dataset's assumptions: Microcosm is the only dataset the analysis now publishes. */
const DATASET_NAMES = { microcosm: "Microcosm" };
const datasetName = (id) => (id in DATASET_NAMES ? DATASET_NAMES[id] : id);

function AssumptionsTable({ rows }) {
  const lines = [
    ["Families with a child under 5 who would claim the 30 hours", (r) => r.would_claim_30_hours_pct.families_with_child_under_5],
    ["of which with a parent over £100,000", (r) => r.would_claim_30_hours_pct.of_which_parent_over_100k],
    ["Families with a child under 12 who would claim Tax-Free Childcare", (r) => r.would_claim_tfc_pct.families_with_child_under_12],
    ["of which with a parent over £100,000", (r) => r.would_claim_tfc_pct.of_which_parent_over_100k],
  ];
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="assumptions-table">
        <thead>
          <tr>
            <th>Take-up, {fyLabel(rows[0].year)}</th>
            {rows.map((r) => (
              <th key={r.id}>{datasetName(r.id)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map(([label, get]) => (
            <tr key={label + get.toString()}>
              <td className={label.startsWith("of which") ? "pl-8 text-slate-600" : ""}>{label}</td>
              {rows.map((r) => (
                <td key={r.id} className="tabular-nums">
                  {formatPct(get(r), 0)}
                </td>
              ))}
            </tr>
          ))}
          <tr>
            <td>Extended hours used a week, on average (of 30)</td>
            {rows.map((r) => (
              <td key={r.id} className="tabular-nums">
                {r.mean_extended_hours_usage.toFixed(1)}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export default function MethodTab({ data }) {
  const meta = getMeta(data);
  const reform = getReform(data);
  const validation = getValidation(data);
  const limitations = getLimitations(data);
  const assumptions = getAssumptions(data);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="method-tab">
      <Section
        id="model"
        title="Data and model"
        lead="Every figure comes from PolicyEngine UK, a microsimulation model of UK taxes and benefits, run on survey data reweighted to official totals."
      >
        <VersionsTable meta={meta} />
      </Section>

      <Section
        id="limits"
        title="How the limits work"
        lead="Both schemes are withdrawn when either parent's adjusted net income is above £100,000."
        details={
          <>
            <div className="overflow-x-auto">
                <table className="data-table" data-testid="parameters-table">
                  <thead>
                    <tr>
                      <th>Parameter</th>
                      <th>Today</th>
                      <th>Reform</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reform.parameters.map((p) => (
                      <tr key={p.name}>
                        <td className="break-all font-mono text-xs">{p.name}</td>
                        <td className="tabular-nums">{formatCurrency(p.baseline)}</td>
                        <td>Removed</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
          </>
        }
        detailsTitle="The parameters changed"
      >
        <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600" data-testid="limits-explainer">
          <li>
            The 30 hours for working parents (England) fund 30 hours a week of childcare, 38 weeks a year, for children
            from 9 months until they start school. Tax-Free Childcare (UK-wide) adds £2 for every £8 a family pays a
            childcare provider, up to £2,000 a year per child (£4,000 for a disabled child).
          </li>
          <li>
            Each parent must expect to earn at least the equivalent of 16 hours a week at the National Minimum or Living
            Wage, and neither may have adjusted net income above £100,000. The test is on each parent separately, so a
            couple both earning £95,000 qualify while a couple earning £101,000 and £20,000 do not.
          </li>
          <li>
            Adjusted net income is taxable income less pension contributions and Gift Aid, so parents just above the
            limit can get back under it by paying more into a pension.
          </li>
          <li>The reform removes only the £100,000 test. The minimum earnings test and every other condition stay.</li>
        </ul>
      </Section>

      <Section
        id="take-up"
        title="Take-up"
        lead="The dataset's existing take-up draws are held fixed for newly eligible families. The rates differ above and below £100,000, as the table shows."
      >
        <AssumptionsTable rows={assumptions} />
      </Section>

      <Section
        id="validation"
        title="Baseline validation"
        lead="How the model's take-up and spending under current policy compare with official statistics."
        details={
          <p>
            The two largest gaps against official statistics are spending through Tax-Free Childcare accounts, which
            the model takes to cover all of a family&apos;s childcare spending, and use of the funded hours, where
            families in the data use about half of the 30 hours. The low and high ends of the range adjust for each.
          </p>
        }
      >
        <ValidationTable rows={validation} />
      </Section>

      <Section id="limitations" title="Limitations" lead="What the costing does not capture.">
        <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600" data-testid="limitations">
          {limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
