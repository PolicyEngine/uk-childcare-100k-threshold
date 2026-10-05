"use client";

import { getLimitations, getMeta, getReform, getValidation } from "../lib/dataHelpers";
import { formatBn, formatCount, formatCurrency, formatPct } from "../lib/formatters";
import { Section, Unavailable } from "./ui";

/** A value in its stated unit: "£bn" -> £0.95bn, "£" -> £1,234, anything else a count followed by the unit. */
export function formatUnit(value, unit) {
  if (unit === "£bn") return formatBn(value, 2);
  if (unit === "£m") return `${formatCurrency(value)}m`;
  if (unit === "£") return formatCurrency(value);
  if (unit === "%") return formatPct(value, 1);
  return formatCount(value);
}

function VersionsTable({ meta }) {
  const rows = [
    ["policyengine.py", meta.policyengine],
    ["PolicyEngine UK", meta.policyengine_uk],
    ["Dataset", `${meta.dataset} (revision ${meta.dataset_revision})`],
    ["Cross-check dataset", meta.cross_check_dataset],
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
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="validation-table">
        <thead>
          <tr>
            <th>Measure</th>
            <th>Year</th>
            <th>PolicyEngine</th>
            <th>Official</th>
            <th>Ratio</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.label}-${r.year}`}>
              <td>{r.label}</td>
              <td>{r.year}</td>
              <td className="tabular-nums">{formatUnit(r.model, r.unit)}</td>
              <td className="tabular-nums">{formatUnit(r.official, r.unit)}</td>
              <td className="tabular-nums">{r.official ? (r.model / r.official).toFixed(2) : "n/a"}</td>
              <td>
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

export default function MethodTab({ data }) {
  const meta = getMeta(data);
  const reform = getReform(data);
  const validation = getValidation(data);
  const limitations = getLimitations(data);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="method-tab">
      <Section
        id="model"
        title="Data and model"
        lead="Every figure comes from PolicyEngine UK, a microsimulation model of UK taxes and benefits, run on survey data reweighted to official totals."
      >
        {meta ? <VersionsTable meta={meta} /> : <Unavailable what="The model and data versions" plural />}
      </Section>

      <Section
        id="limits"
        title="How the limits work"
        lead="Both schemes are withdrawn when either parent's adjusted net income is above £100,000."
        details={
          reform ? (
            <>
              <p>{reform.description}</p>
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
          ) : (
            <Unavailable what="The reform's parameters" plural />
          )
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
        id="validation"
        title="Baseline validation"
        lead="How the model's take-up and spending under current policy compare with official statistics."
      >
        {validation ? <ValidationTable rows={validation} /> : <Unavailable what="The baseline validation" />}
      </Section>

      <Section id="limitations" title="Limitations" lead="What the costing does not capture.">
        {limitations ? (
          <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600" data-testid="limitations">
            {limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        ) : (
          <Unavailable what="The limitations" plural />
        )}
      </Section>
    </div>
  );
}
