"use client";

import { fyLabel, getAssumptions, getLimitations, getMeta, getModellingAssumptions, getReform, getValidation, STATIC_SETTING } from "../lib/dataHelpers";
import { formatBn, formatCount, formatCurrency, formatPct } from "../lib/formatters";
import { BenchmarkNotes, UnifiedComparison } from "./Comparison";
import { Expandable, Section } from "./ui";

/** A value in its stated unit: "£bn" -> £0.95bn, "£" -> £1,234, anything else a count followed by the unit. */
export function formatUnit(value, unit) {
  if (unit === "£bn") return formatBn(value, 2);
  if (unit === "£m") return `${formatCurrency(value)}m`;
  if (unit === "£") return formatCurrency(value);
  if (unit === "%") return formatPct(value, 1);
  if (unit === "£/hour") return `£${value.toFixed(2)}`;
  return formatCount(value);
}

const REPO_URL = "https://github.com/PolicyEngine/uk-childcare-100k-threshold";

function VersionsTable({ meta }) {
  const rows = [
    [
      "Model package",
      <>
        <a href={`https://pypi.org/project/policyengine/${meta.policyengine}/`} target="_blank" rel="noreferrer">
          policyengine.py {meta.policyengine}
        </a>
        , pinned exactly in the repository&apos;s pyproject.toml and uv.lock
      </>,
    ],
    [
      "Tax and benefit rules",
      `policyengine-uk ${meta.policyengine_uk}, the version certified by the policyengine.py ${meta.policyengine} release bundle`,
    ],
    ["Dataset", meta.dataset_label ?? meta.dataset],
    ...(meta.dataset_release ? [["Dataset release", meta.dataset_release]] : []),
    ["Dataset revision", `${meta.dataset_revision}${meta.dataset_repo ? ` (${meta.dataset_repo})` : ""}`],
    ...(meta.dataset_sha256 ? [["Dataset sha256, checked before every run", meta.dataset_sha256]] : []),
    ["Results generated", meta.generated_at],
    [
      "Code revision",
      <a key="rev" href={`${REPO_URL}/commit/${meta.git_revision}`} target="_blank" rel="noreferrer">
        {meta.git_revision}
      </a>,
    ],
  ];
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="versions-table">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td className="w-[260px] font-medium text-slate-700">{k}</td>
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
              <td className="tabular-nums">
                <a href={r.url} target="_blank" rel="noreferrer">
                  {formatUnit(r.official, r.unit)}
                </a>
              </td>
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

/** £bn as a signed £m figure: -0.015 -> "-£15m", 0.616 -> "+£616m". */
const signedM = (v) => {
  const m = Math.round(v * 1000);
  return `${m > 0 ? "+" : m < 0 ? "-" : ""}£${Math.abs(m).toLocaleString("en-GB")}m`;
};

/** Each tested alternative and how much it moves the cost in every year. */
function EffectsTable({ rows, years }) {
  const tested = rows.filter((r) => r.effects);
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="effects-table">
        <thead>
          <tr>
            <th>Alternative we test</th>
            {years.map((y) => (
              <th key={y} className="whitespace-nowrap">{fyLabel(y)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tested.map((r) => (
            <tr key={r.id} data-testid={`effect-${r.id}`}>
              <td>
                <span className="font-medium text-slate-800">{r.title}:</span> {r.alternative}
              </td>
              {r.effects.map((v, i) => (
                <td key={years[i]} className="whitespace-nowrap tabular-nums">{signedM(v)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AssumptionNotes({ rows, takeUp }) {
  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r.id}>
          <p>
            <span className="font-semibold text-slate-700">{r.title}. </span>
            {r.modelled}{" "}
            {(r.sources ?? []).map((x, i) => (
              <span key={x.url + x.label}>
                {i === 0 ? "Sources: " : "; "}
                <a href={x.url} target="_blank" rel="noreferrer">
                  {x.label}
                </a>
                {i === r.sources.length - 1 ? "." : ""}
              </span>
            ))}
          </p>
          {r.id === "take_up" ? <div className="mt-2">{takeUp}</div> : null}
        </div>
      ))}
    </div>
  );
}

export default function MethodTab({ data, setting = STATIC_SETTING }) {
  const meta = getMeta(data);
  const reform = getReform(data);
  const validation = getValidation(data);
  const limitations = getLimitations(data);
  const assumptions = getAssumptions(data);
  const modelling = getModellingAssumptions(data);

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="method-tab">
      <Section
        id="model"
        title="How we cost it"
        lead="Every figure comes from PolicyEngine UK, a microsimulation model of UK taxes and benefits, run on Microcosm, PolicyEngine's survey-based dataset of UK households reweighted to official totals."
        detailsTitle="Exact versions"
        details={<VersionsTable meta={meta} />}
      >
        <ol className="list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-600" data-testid="method-steps">
          <li>
            For each year from {fyLabel(meta.years[0])} to {fyLabel(meta.years.at(-1))}, we run the model twice on the
            same households: once with today&apos;s rules, and once with the £100,000 limit removed from both the 30
            hours and Tax-Free Childcare.
          </li>
          <li>
            The cost is the extra government spending on funded hours and Tax-Free Childcare top-ups between the two
            runs. Families gaining, and how much, come from the same comparison, household by household.
          </li>
          <li>
            The costing is static: parents work, earn and pay for childcare exactly as they do today in both runs.
          </li>
          <li>
            Further runs change one uncertain assumption at a time (how many hours families use, babies under one, and
            the income the limit tests), and the Assumptions section below shows what each changes.
          </li>
          <li>
            Every version is pinned, so the results can be rebuilt exactly: the model package and the dataset release
            are fixed, and the dataset file&apos;s checksum is verified before each run. The exact versions are below.
          </li>
        </ol>
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
          <li>
            The pledge names no nation. We read it as England&apos;s 30 hours plus Tax-Free Childcare, which is
            UK-wide. The devolved governments&apos; own childcare offers, such as the Childcare Offer for Wales with its
            own £100,000 test, are unchanged.
          </li>
        </ul>
      </Section>

      <Section
        id="assumptions"
        title="How do we compare with other estimates?"
        lead={`Our costing set against CenTax's, the Conservatives' figure, and the official sources and law, first on the cost and then on each modelling choice. The "If we change it" column shows how much the cost moves in ${fyLabel(meta.years.at(-1))} when we rerun with the alternative described under More detail; each change is separate and they do not add up.`}
        details={
          <>
            <AssumptionNotes rows={modelling} takeUp={<AssumptionsTable rows={assumptions} />} />
            <EffectsTable rows={modelling} years={meta.years} />
            <BenchmarkNotes data={data} />
          </>
        }
        detailsTitle="Each choice in full, the effect in every year, and sources"
      >
        <Expandable title="Show the comparison table" testId="comparison-expandable">
          <UnifiedComparison data={data} setting={setting} />
        </Expandable>
      </Section>

      <Section
        id="validation"
        title="Baseline validation"
        lead="How the model's picture of today, before any reform, compares with official statistics."
        details={
          <p>
            The two largest gaps against official statistics are spending through Tax-Free Childcare accounts, which
            the model takes to cover all of a family&apos;s childcare spending, and use of the funded hours, where
            families in the data use about half of the 30 hours. The low and high ends of the range adjust for each.
          </p>
        }
      >
        <Expandable title="Show the validation table" testId="validation-expandable">
          <ValidationTable rows={validation} />
        </Expandable>
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
