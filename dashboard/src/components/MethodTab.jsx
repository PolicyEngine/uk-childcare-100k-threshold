"use client";

import {
  fyLabel,
  getAssumptions,
  getLabourSupply,
  getLimitations,
  getMeta,
  getModellingAssumptions,
  getReform,
  getValidation,
  isNum,
  STATIC_SETTING,
} from "../lib/dataHelpers";
import { formatBn, formatCount, formatCurrency, formatMoneyBn, formatPct } from "../lib/formatters";
import { BenchmarkNotes, CENTAX, UnifiedComparison } from "./Comparison";
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

// £m to one decimal, signed: the entry sensitivities are a few £m.
const formatM = (x) => `${x < 0 ? "-" : "+"}£${Math.abs(x).toFixed(1)}m`;

function LabourSupplySection({ data }) {
  const ls = getLabourSupply(data);
  const a = ls.assumptions;
  const raw = data.labour_supply;
  const li = ls.years.length - 1;
  const year = fyLabel(ls.years[li]);
  const entrants = Math.round(ls.extensive.entrants.central[li] / 100) * 100;
  const oldRule = raw.extensive.non_worker_rule_entrants?.central?.[String(ls.years[li])];
  const extOffset = ls.extensive.offset.central[li];
  const disp = raw.intensive_displacement;
  const groupSum = (k) =>
    ["at_or_below_limit", "over_limit"].reduce((t, g) => t + (raw.intensive[g]?.[k]?.central?.[String(ls.years[li])] ?? 0), 0);
  const yKey = String(ls.years[li]);
  const byLevel = raw.extensive.allocated_by_cell_level;
  const fellBack = byLevel
    ? Object.entries(byLevel)
        .filter(([level]) => level !== "sex_couple_child_quintile")
        .reduce((t, [, v]) => t + (v.central?.[yKey] ?? 0), 0)
    : null;
  const incomeBasis = raw.intensive_income_basis;
  const entrySens = raw.extensive.entry_sensitivity;
  const covered = groupSum("workers_fully_covered");
  const paying = groupSum("workers_paying_for_childcare");
  const scale = (x) => (Math.abs(x - 1 / 3) < 0.001 ? "1/3" : String(x));
  return (
    <Section
      id="labour-supply"
      title="Labour supply"
      lead="The headline costs are static: nobody changes how much they work. A labour supply response can be switched on with the Labour supply control on Budget impact, which then shows a dynamic cost: the static cost less the change in tax, National Insurance and childcare support that follows the change in work."
    >
      <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600" data-testid="labour-supply-method">
        <li>
          <strong>Who responds.</strong> {raw.responding_population}
        </li>
        <li>
          <strong>Moving into work (extensive margin).</strong>{" "}
          The{" "}
          <a href="https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf" target="_blank" rel="noreferrer">
            OBR&apos;s participation elasticities
          </a>{" "}
          (
          {a.participation_elasticities}). An elasticity is the percentage change in the probability of working for a
          percentage change in the gain to work; it is converted from in-work income by the gain to work over in-work
          income, and the gain to work is net of the childcare a parent would then pay for, less the Tax-Free
          Childcare the scenario would pay on it. Because the probability change applies to the employed share, new
          employment is the sum over working adults of their own response (Adam and Phillips, Appendix E). It is
          shared among non-working adults like them, who are the ones entering: those in the same OBR group (sex,
          couple, age of the youngest child and earnings quintile), in proportion to their own response, or, where
          that group has no responding non-worker, the nearest broader group
          {isNum(fellBack) ? ` (about ${formatCount(fellBack)} of the entrants in ${year})` : ""}.
          {entrySens
            ? ` Those take the earnings and support of non-workers in other earnings quintiles; dropping them, the ${year} offset would be ${formatM(entrySens.same_cell_only.offset_m[yKey])}, and giving them the hourly wage of the workers who imply them, ${formatM(entrySens.worker_profile.offset_m[yKey])}, against ${formatM(entrySens.central_offset_m[yKey])}.`
            : ""}
          {isNum(oldRule) ? ` Applying the elasticity to each non-worker instead would give about ${formatCount(oldRule)} entrants in ${year}.` : ""}{" "}
          Entrants work {a.hours_for_new_entrants} hours a week. Results are expected values, not random draws.
        </li>
        <li>
          <strong>Hours (intensive margin).</strong>{" "}
          Every responding adult in work, at or below £100,000 and over it, in two parts. The model recomputes tax and benefits once, on everyone&apos;s combined change in earnings;
          the parts are an attribution that adds up to it (the price change alone, then the income effect as the
          remainder).{" "}
          <em>Price effect:</em> an assumed childcare-price elasticity of hours of {a.hours_price_elasticity}, an
          extrapolated scenario assumption, not an estimated price elasticity (
          <a
            href="https://ifs.org.uk/sites/default/files/output_url_files/WP202009-Does-more-free-childcare-help-parents-work-more.pdf#page=17"
            target="_blank"
            rel="noreferrer"
          >
            Brewer, Cattan, Crawford and Rabe, IFS WP20/09
          </a>{" "}
          estimate +0.6 weekly hours for mothers whose youngest child becomes eligible for full-time rather than
          part-time free care, which we treat as a 100% price fall; it is not measured on parents over £100,000).
          It applies to the change in the price of the family&apos;s next hour of paid childcare, for adults whose
          family pays for childcare. Tax-Free Childcare lowers that price where the reform newly pays it and the cap
          does not bind. The 30 funded hours are a fixed amount, given once both parents meet the minimum earnings
          test, so for a family that still buys paid care on top of them an extra hour costs what it did; they make it
          free only where they are worth more than all the paid care the family buys, judged on value with funded hours assumed to
          replace {formatPct(a.free_hours_displacement * 100, 1)} of their value in paid care (an assumption; IFS BN189
          supports {formatPct(a.free_hours_displacement_range.low * 100, 1)} to{" "}
          {formatPct(a.free_hours_displacement * 100, 1)}).{" "}
          <em>Income effect:</em> the{" "}
          <a href="https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf" target="_blank" rel="noreferrer">
            OBR&apos;s income elasticities
          </a>{" "}
          ({a.income_elasticities}) times the family&apos;s gain from the reform, before any response, as a percentage
          of its disposable income: a family made better off works slightly less. The gain is measured like that
          income: the change in cash income, Tax-Free Childcare included, plus the paid childcare the newly funded
          hours replace (at the same displacement rate, capped at what the family pays), less the Tax-Free Childcare
          top-up the family no longer gets on the care it stops buying; not what the funded hours cost the
          government. In {year}, at central elasticities, the price effect
          brings back {formatMoneyBn(ls.intensive.price.central[li])} (
          {formatMoneyBn(ls.intensive.at_or_below_limit.price.central[li])} from adults at or below £100,000,{" "}
          {formatMoneyBn(ls.intensive.over_limit.price.central[li])} from those over it) and the income effect costs{" "}
          {formatMoneyBn(-ls.intensive.income.central[li])} ({formatMoneyBn(-ls.intensive.at_or_below_limit.income.central[li])}{" "}
          and {formatMoneyBn(-ls.intensive.over_limit.income.central[li])}), a net{" "}
          {formatMoneyBn(ls.intensive.offset.central[li])} back. The funded hours fully cover the paid care of the
          families of about {formatCount(covered)} of the {formatCount(paying)} adults in work who pay for childcare
          {disp
            ? `; with displacement at ${formatPct(disp.displacement.low * 100, 1)} or ${formatPct(disp.displacement.high * 100, 0)} the net is ${formatBn(disp.offset_bn.low[yKey], 3)} or ${formatBn(disp.offset_bn.high[yKey], 3)} rather than ${formatBn(ls.intensive.offset.central[li], 3)}`
            : ""}
          {incomeBasis?.paid_care_fixed_spend
            ? `; keeping the top-up on the care the funded hours replace (spending held fixed), it would be ${formatBn(incomeBasis.paid_care_fixed_spend.offset_bn[yKey], 3)}`
            : ""}
          {incomeBasis?.government_cost
            ? `; counting the funded hours at their cost to government in the income effect, ${formatBn(incomeBasis.government_cost.offset_bn[yKey], 3)}`
            : ""}
          .
        </li>
        <li>
          <strong>Couples.</strong> {a.couples}{" "}
          <a href={a.couples_issue_url} target="_blank" rel="noreferrer">
            Reported to policyengine-uk
          </a>
          .
        </li>
        <li>
          <strong>Low and high elasticities.</strong> Every elasticity (participation, price and income) is multiplied by {scale(a.elasticity_scales.low)} for the
          low end and by {scale(a.elasticity_scales.high)} for the high end. The range is illustrative, not a sourced
          uncertainty interval: the factors are ratios of childcare-price elasticities of maternal employment,{" "}
          {a.price_elasticity_low} and {a.price_elasticity_high} against {a.price_elasticity_central}, a different outcome
          from the elasticities they scale.
        </li>
        <li>
          <strong>Why so few move into work.</strong>{" "}
          In a family where one parent is over £100,000, a partner&apos;s gain to
          work is small next to the household&apos;s in-work income, so the OBR elasticity converted to the gain to
          work is small; and the tax entrants pay is set against the childcare support their family then receives.
          The model finds about {formatCount(entrants)} entrants in {year}, and they{" "}
          {extOffset < 0 ? `add ${formatMoneyBn(-extOffset)} to the cost rather than bringing money back.` : `bring back ${formatMoneyBn(extOffset)}.`}
        </li>
        <li>
          <strong>Not modelled.</strong> {ls.notModelled}
        </li>
        <li>
          <strong>Against CenTax.</strong> CenTax&apos;s behavioural gain in {CENTAX.year} is{" "}
          {formatBn(CENTAX.parentsBn, 2)} from parents who stop holding their income below £100,000 and{" "}
          {formatBn(CENTAX.partnersBn, 2)} from partners entering work. The first is not modelled here; for the second we
          find {formatMoneyBn(extOffset)}, for the reasons above. Our hours response, of parents at any income working
          more or less as childcare prices and family income change, has no CenTax counterpart.
        </li>
      </ul>
    </Section>
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
            The headline costing is static: parents work, earn and pay for childcare exactly as they do today in both
            runs. A labour supply response can be added on Budget impact; the Labour supply section below explains it.
          </li>
          <li>
            Further runs change one uncertain assumption at a time (how many hours families use, babies under one, and
            the income the limit tests), and &quot;How do we compare with other estimates?&quot; below shows what each
            changes.
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
        <p className="text-sm leading-6 text-slate-600" data-testid="limits-explainer">
          What each scheme gives, who qualifies today and what the reform changes are set out side by side at the top
          of Budget impact. Adjusted net income is taxable income less pension contributions and Gift Aid, so a parent
          just over the limit can get back under it by paying more into a pension; the test is on each parent, so a
          couple both earning £95,000 qualify today while a couple earning £101,000 and £20,000 do not. The pledge names
          no nation: we read it as England&apos;s 30 hours plus Tax-Free Childcare, which is UK-wide, and the devolved
          governments&apos; own childcare offers, such as the Childcare Offer for Wales with its own £100,000 test, are
          unchanged. The model parameters the reform changes are below.
        </p>
      </Section>

      <LabourSupplySection data={data} />

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
            Tax-Free Childcare top-ups, children and families match HMRC within about 1%. The largest gap is in the
            funded hours: families in the data use about half of the 30 hours (PolicyEngine/microcosm#1126).
            &quot;How do we compare with other estimates?&quot; above shows what full use would do to the cost.
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
