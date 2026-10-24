"use client";

import {
  fyLabel,
  getAssumptions,
  getLabourSupply,
  getLimitations,
  getMeta,
  getModellingAssumptions,
  getReform,
  getTakeUp,
  getUncertainty,
  getValidation,
  LEAD_YEAR,
  isNum,
  isText,
  STATIC_SETTING,
} from "../lib/dataHelpers";
import { formatBn, formatCount, formatCurrency, formatMoneyBn, formatPct } from "../lib/formatters";
import { BenchmarkNotes, CENTAX, UnifiedComparison } from "./Comparison";
import { Expandable, ExpandableGroup, ExpandableRow, RichText, Section } from "./ui";

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
const MICROCOSM_URL = "https://github.com/PolicyEngine/microcosm";

function VersionsTable({ meta }) {
  const rows = [
    [
      "Model package",
      <>
        <a href={`https://pypi.org/project/policyengine/${meta.policyengine}/`} target="_blank" rel="noopener noreferrer">
          policyengine.py {meta.policyengine}
        </a>
        , pinned exactly in the repository&apos;s pyproject.toml and uv.lock
      </>,
    ],
    [
      "Tax and benefit rules",
      <>
        <a href={`https://github.com/PolicyEngine/policyengine-uk/tree/${meta.policyengine_uk}`} target="_blank" rel="noopener noreferrer">
          policyengine-uk {meta.policyengine_uk}
        </a>
        {`, the version the Microcosm release pins, pinned exactly in pyproject.toml${
          meta.policyengine_bundle_model_version ? ` (the policyengine.py bundle carries ${meta.policyengine_bundle_model_version})` : ""
        }`}
      </>,
    ],
    ["Dataset", meta.dataset_label ?? meta.dataset],
    ...(meta.dataset_status ? [["Dataset status", <RichText key="status" text={meta.dataset_status} />]] : []),
    ...(meta.dataset_release ? [["Dataset release", meta.dataset_release]] : []),
    ["Dataset revision", `${meta.dataset_revision}${meta.dataset_repo ? ` (${meta.dataset_repo})` : ""}`],
    ...(meta.dataset_sha256 ? [["Dataset sha256, checked before every run", meta.dataset_sha256]] : []),
    ["Results generated", meta.generated_at],
    [
      "Code revision",
      <a key="rev" href={`${REPO_URL}/commit/${meta.git_revision}`} target="_blank" rel="noopener noreferrer">
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
                {"note" in r ? <span className="mt-1 block text-xs leading-5 text-slate-500"><RichText text={r.note} /></span> : null}
              </td>
              {showDataset ? <td>{r.dataset}</td> : null}
              <td className="whitespace-nowrap">{fyLabel(r.year)}</td>
              <td className="tabular-nums">{formatUnit(r.model, r.unit)}</td>
              <td className="tabular-nums">
                <a href={r.url} target="_blank" rel="noopener noreferrer">
                  {formatUnit(r.official, r.unit)}
                </a>
              </td>
              <td className="tabular-nums">{r.official === 0 ? "n/a" : (r.model / r.official).toFixed(2)}</td>
              <td className="min-w-[220px]">
                <a href={r.url} target="_blank" rel="noopener noreferrer">
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
    ["Families with a child under 12 reporting paid registered childcare", (r) => r.reports_childcare_spend_pct?.families_with_child_under_12],
    ["of which with a parent over £100,000", (r) => r.reports_childcare_spend_pct?.of_which_parent_over_100k],
    ["Families with a child under 12 receiving a Tax-Free Childcare top-up", (r) => r.uses_tfc_pct?.families_with_child_under_12],
  ];
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="assumptions-table">
        <thead>
          <tr>
            <th>Take-up and use, {fyLabel(rows[0].year)}</th>
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
        <div key={r.id} id={r.id === "take_up" ? "take-up-rates" : undefined}>
          <p>
            <span className="font-semibold text-slate-700">{r.title}. </span>
            <RichText text={r.modelled} />{" "}
            {(r.sources ?? []).map((x, i) => (
              <span key={x.url + x.label}>
                {i === 0 ? "Sources: " : "; "}
                <a href={x.url} target="_blank" rel="noopener noreferrer">
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

const OBR_NOTE_URL = "https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf";
const BREWER_URL =
  "https://ifs.org.uk/sites/default/files/output_url_files/WP202009-Does-more-free-childcare-help-parents-work-more.pdf#page=41";
const BN189_URL = "https://ifs.org.uk/sites/default/files/output_url_files/BN189.pdf#page=12";
const CENTAX_TABLE_URL =
  "https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf#page=42";

const Ext = ({ href, children }) => (
  <a href={href} target="_blank" rel="noopener noreferrer">
    {children}
  </a>
);

/** A box's content as prose, across the full width of the box. */
function Prose({ children }) {
  return <div className="space-y-2 text-sm leading-6 text-slate-600">{children}</div>;
}

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
  const priceBasis = raw.intensive_price_basis;
  const entrySens = raw.extensive.entry_sensitivity;
  const covered = groupSum("workers_fully_covered");
  const paying = groupSum("workers_paying_for_childcare");
  const scale = (x) => (Math.abs(x - 1 / 3) < 0.001 ? "1/3" : String(x));
  const extText = extOffset < 0 ? `add ${formatMoneyBn(-extOffset)} to the cost` : `bring back ${formatMoneyBn(extOffset)}`;
  const sensitivities = [
    disp
      ? `with displacement at ${formatPct(disp.displacement.low * 100, 1)} or ${formatPct(disp.displacement.high * 100, 0)}, the net is ${formatBn(disp.offset_bn.low[yKey], 3)} or ${formatBn(disp.offset_bn.high[yKey], 3)}`
      : null,
    priceBasis?.original_spend ? `reading the reform's price at today's spend, ${formatBn(priceBasis.original_spend.offset_bn[yKey], 3)}` : null,
    priceBasis?.tfc_only ? `counting only Tax-Free Childcare in the price, ${formatBn(priceBasis.tfc_only.offset_bn[yKey], 3)}` : null,
    incomeBasis?.paid_care_fixed_spend
      ? `keeping the cash support on the care the funded hours replace (spending held fixed), ${formatBn(incomeBasis.paid_care_fixed_spend.offset_bn[yKey], 3)}`
      : null,
    incomeBasis?.government_cost
      ? `counting the funded hours at their cost to government in the income effect, ${formatBn(incomeBasis.government_cost.offset_bn[yKey], 3)}`
      : null,
  ].filter(Boolean);
  return (
    <Section
      id="labour-supply"
      title="Labour supply"
      boxed={false}
      lead={
        <>
          Our headline assumes nobody changes how much they work. The Labour supply switches on{" "}
          <a href="?tab=budget">Budget impact</a> add a work response; the cost then shown is the static cost less the
          change in tax, National Insurance and childcare support that follows.
        </>
      }
    >
      <ExpandableGroup className="mt-5" testId="labour-supply-details">
        <Expandable title={`What we find, ${year}`} testId="ls-findings" compact defaultOpen>
          <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600" data-testid="labour-supply-method">
            <li>
              <strong>Partners moving into work:</strong> about {formatCount(entrants)}, who {extText}.
              {extOffset < 0
                ? " Both parents must work for the family to qualify, so a partner starting work unlocks the 30 hours and Tax-Free Childcare."
                : ""}
            </li>
            <li>
              <strong>Parents changing their hours:</strong> a net {formatMoneyBn(ls.intensive.offset.central[li])} back,
              at central elasticities. The price effect brings back {formatMoneyBn(ls.intensive.price.central[li])}, as
              cheaper childcare pulls hours up; the income effect costs {formatMoneyBn(-ls.intensive.income.central[li])},
              as being better off pulls them down.
            </li>
          </ul>
        </Expandable>
        <Expandable title="Not modelled" testId="ls-not-modelled" compact>
          <Prose>
            <p>{ls.notModelled}</p>
          </Prose>
        </Expandable>
        <Expandable title="Compared with CenTax" testId="ls-centax" compact>
          <Prose>
            <p>
              CenTax&apos;s behavioural gain in {CENTAX.year} is{" "}
              <Ext href={CENTAX_TABLE_URL}>
                {formatBn(CENTAX.parentsBn, 2)} from parents who stop holding their income below £100,000 and{" "}
                {formatBn(CENTAX.partnersBn, 2)} from partners entering work
              </Ext>
              . Our hours response has no CenTax counterpart.
            </p>
          </Prose>
        </Expandable>
        <Expandable title="Who responds" testId="ls-who" compact>
          <Prose>
            <p>
              <RichText text={raw.responding_population} />
            </p>
          </Prose>
        </Expandable>
        <Expandable title="Moving into work: method" testId="ls-extensive" compact>
          <Prose>
            <p>
              The <Ext href={OBR_NOTE_URL}>OBR&apos;s participation elasticities</Ext> (
              <RichText text={a.participation_elasticities} />
              ). An elasticity is the percentage change in the probability of working for a percentage change in the
              gain to work; it is converted from in-work income by the gain to work over in-work income, and the gain
              to work is net of the childcare a parent would then pay for, less the Tax-Free Childcare the scenario
              would pay on it.
            </p>
            <p>
              Because the probability change applies to the employed share, new employment is the sum over working
              adults of their own response. It is shared among non-working adults like
              them, who are the ones entering: those in the same OBR group (sex, couple, age of the youngest child and
              earnings quintile), in proportion to their own response, or, where that group has no responding
              non-worker, the nearest broader group
              {isNum(fellBack) ? ` (about ${formatCount(fellBack)} of the entrants in ${year})` : ""}. Entrants work{" "}
              {a.hours_for_new_entrants} hours a week. Results are expected values, not random draws.
            </p>
            <p>
              Why so few: in a family where one parent is over £100,000, a partner&apos;s gain to work is small next to
              the household&apos;s in-work income, so the OBR elasticity converted to the gain to work is small; and the
              tax entrants pay is set against the childcare support their family then receives. The hours response, of
              parents already in work and already eligible, changes earnings without unlocking support, so it brings
              money back.
            </p>
          </Prose>
        </Expandable>
        <Expandable title="Hours: method" testId="ls-intensive" compact>
          <Prose>
            <p>
              Every responding adult in work, at or below £100,000 and over it, in two parts. The model recomputes tax
              and benefits once, on everyone&apos;s combined change in earnings; the parts are an attribution that adds
              up to it (the price change alone, then the income effect as the remainder).
            </p>
            <p>
              <em>Price effect:</em> an assumed childcare-price elasticity of hours of {a.hours_price_elasticity}, an
              extrapolated scenario assumption, not an estimated price elasticity (
              <Ext href={BREWER_URL}>Brewer, Cattan, Crawford and Rabe, IFS WP20/09</Ext>{" "}
              estimate +0.6 weekly hours
              for mothers whose youngest child becomes eligible for full-time rather than part-time free care, which we
              treat as a 100% price fall; it is not measured on parents over £100,000). It applies to the change in the
              price of the family&apos;s next hour of paid childcare, for adults whose family pays for childcare. That
              price is net of all the cash support tied to the next pound of care (Tax-Free Childcare, the Universal
              Credit childcare element), measured on one more pound of spending so that near a cap it is the support on
              that pound, read today and, under the reform, on the paid care the family still buys once the funded
              hours replace some of it: Tax-Free Childcare lowers it where the reform newly pays it below the cap, and
              the Universal Credit childcare element (85p per pound) where the replaced care takes a family below its
              cap.
            </p>
            <p>
              The 30 funded hours are a fixed amount, given once both parents meet the minimum earnings test, so for a
              family that still buys paid care on top of them an extra hour costs what it did; they make it free only
              where they are worth more than all the paid care the family buys, judged on value with funded hours
              assumed to replace {formatPct(a.free_hours_displacement * 100, 1)} of their value in paid care (an
              assumption; <Ext href={BN189_URL}>IFS BN189</Ext> supports{" "}
              {formatPct(a.free_hours_displacement_range.low * 100, 1)} to {formatPct(a.free_hours_displacement * 100, 1)}).
              The funded hours fully cover the paid care of the families of about {formatCount(covered)} of the{" "}
              {formatCount(paying)} adults in work who pay for childcare.
            </p>
            <p>
              <em>Income effect:</em> the <Ext href={OBR_NOTE_URL}>OBR&apos;s income elasticities</Ext> (
              <RichText text={a.income_elasticities} />) times the family&apos;s gain from the reform, before any
              response, as a percentage of its disposable income: a family made better off works slightly less. The
              gain is measured like that income: the paid childcare the newly funded hours replace (at the same
              displacement rate, capped at what the family pays) plus the change in cash income, recomputed on the care
              the family still buys, so the Tax-Free Childcare and Universal Credit childcare element it no longer gets
              on the care it stops buying come off; not what the funded hours cost the government.
            </p>
            <p>
              Of the price effect in {year}, {formatMoneyBn(ls.intensive.at_or_below_limit.price.central[li])} comes
              from adults at or below £100,000 and {formatMoneyBn(ls.intensive.over_limit.price.central[li])} from those
              over it; of the income effect, {formatMoneyBn(-ls.intensive.at_or_below_limit.income.central[li])} and{" "}
              {formatMoneyBn(-ls.intensive.over_limit.income.central[li])}.
            </p>
          </Prose>
        </Expandable>
        <Expandable title="Sensitivities" testId="ls-sensitivities" compact>
          <Prose>
            <p>
              <strong>Low and high.</strong> Every elasticity is multiplied by {scale(a.elasticity_scales.low)} and by{" "}
              {scale(a.elasticity_scales.high)}: an illustrative range, not a sourced uncertainty interval. The factors are ratios of childcare-price elasticities of maternal
              employment, {a.price_elasticity_low} and {a.price_elasticity_high} against {a.price_elasticity_central}, a
              different outcome from the elasticities they scale (participation, price and income).
            </p>
            {entrySens || isNum(oldRule) ? (
              <p>
                <strong>Moving into work.</strong>
                {entrySens
                  ? ` Some entrants take the earnings and support of non-workers in other earnings quintiles; dropping them, the ${year} offset would be ${formatM(entrySens.same_cell_only.offset_m[yKey])}, and giving them the hourly wage of the workers who imply them, ${formatM(entrySens.worker_profile.offset_m[yKey])}, against ${formatM(entrySens.central_offset_m[yKey])}.`
                  : ""}
                {isNum(oldRule) ? ` Applying the elasticity to each non-worker instead would give about ${formatCount(oldRule)} entrants in ${year}.` : ""}
              </p>
            ) : null}
            {sensitivities.length ? (
              <p>
                <strong>Hours.</strong> Against the central net of {formatBn(ls.intensive.offset.central[li], 3)} in{" "}
                {year}: {sensitivities.join("; ")}.
              </p>
            ) : null}
          </Prose>
        </Expandable>
        <Expandable title="Checks and known issues" testId="ls-checks" compact>
          <Prose>
            <p>
              <strong>Couples.</strong> <RichText text={a.couples} />{" "}
              <Ext href={a.couples_issue_url}>Reported to policyengine-uk</Ext>.
            </p>
            {isText(raw.notes?.at(-1)) ? (
              <p data-testid="moved-outside-note">
                <strong>A check on who responds.</strong> <RichText text={raw.notes.at(-1)} />
                {Object.values(raw.population ?? {}).some((p) => p.adults_moved_outside_population > 0) ? (
                  <>
                    {" "}
                    The build allows up to 0.2% of the responding adults here; bringing them into the population is{" "}
                    <Ext href="https://github.com/PolicyEngine/uk-childcare-100k-threshold/issues/11">issue #11</Ext>.
                  </>
                ) : null}
              </p>
            ) : null}
          </Prose>
        </Expandable>
      </ExpandableGroup>
    </Section>
  );
}

/** One step of the costing: a one-line summary, and its detail in a closed box when it has one. */
function Step({ n, title, children, detail, id, testId }) {
  const line = (
    <span className="flex gap-3 font-normal text-slate-700">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[color:var(--pe-color-primary-50)] text-xs font-semibold text-[color:var(--pe-color-primary-700)]">
        {n}
      </span>
      <span>
        <strong className="font-semibold text-slate-800">{title}.</strong> {children}
      </span>
    </span>
  );
  return detail ? (
    <Expandable title={line} id={id} testId={testId} compact>
      <Prose>{detail}</Prose>
    </Expandable>
  ) : (
    <ExpandableRow compact testId={testId}>
      <div id={id}>{line}</div>
    </ExpandableRow>
  );
}

/** The limitation on take-up among newly eligible families: its one home is the Take-up step, not Limitations. */
const TAKE_UP_LIMITATION = "Take-up among newly eligible families";

/** Why the central cost averages over take-up, how each option applies its rates, and what is uncertain about them. */
function TakeUpDetail({ data, limitation }) {
  const t = getTakeUp(data);
  const flat = t.order.map((id) => t.bases[id]).find((b) => b.unit === "family");
  return (
    <>
      <p>
        Nobody over £100,000 is eligible today, so the data cannot say how many newly eligible families would take up
        the 30 hours, and the dataset&apos;s single random draw of who claims leaves a few heavily weighted families
        deciding much of the cost.
      </p>
      <ul className="list-disc space-y-1.5 pl-5">
        <li>
          So another pair of runs has every family claiming and every child using its hours. On DfE&apos;s and
          CenTax&apos;s rates, the cost is each newly entitled child&apos;s cost there times the take-up for its age:
          the rates count both claiming and using the hours, so they replace the dataset&apos;s own draw of who claims.
        </li>
        {flat ? (
          <li>
            On the dataset&apos;s flat rate ({formatPct(flat.rate * 100, 1)}{" "}
            of families), it is each newly eligible
            family&apos;s cost if it claims, times the rate: each
            percentage point of the rate moves the 30 hours&apos; cost by about £{flat.per_point_m[String(LEAD_YEAR)]}m in{" "}
            {fyLabel(LEAD_YEAR)}.
          </li>
        ) : null}
        <li>
          The single draw is higher: the dataset&apos;s heavily weighted newly eligible families drew a claim more often
          than its rate.
        </li>
        <li>
          The rates, why DfE&apos;s rates by age are the headline, and how they compare with the flat rate by age
          are under <a href="#take-up-rates">Who takes up the 30 hours</a> in the comparison below.
        </li>
      </ul>
      {limitation ? (
        <p data-testid="take-up-limitation">
          <strong className="font-semibold text-slate-700">What is uncertain.</strong> <RichText text={limitation.detail} />
        </p>
      ) : (
        <p>
          <a href="?tab=budget#take-up-options">Budget impact</a> switches between the options.
        </p>
      )}
    </>
  );
}

/** The age-profile sensitivity as a limitation: one-sided, so it can only push the cost up. */
function ageProfileLimitation(data) {
  const u = getUncertainty(data);
  const share = u.age.share_over_limit_by_age_pct;
  const others = [0, 2, 3, 4].map((k) => share[String(k)]);
  const pct = (v) => `${Math.round(v)}%`;
  const [lo, hi] = [Math.min(u.age.even_spread_bn, u.age.centax_gradient_bn), Math.max(u.age.even_spread_bn, u.age.centax_gradient_bn)];
  return {
    id: "age-profile",
    title: "Age profile: can only push the cost up",
    summary: `The release has few 1-year-olds in families with a parent over £100,000: ${pct(share["1"])}, against ${pct(Math.min(...others))} to ${pct(Math.max(...others))} at the other ages under 5.`,
    detail: `No source independent of the survey crosses income with a child's age. Spreading the newly entitled 1-to-4-year-olds evenly across those ages, or on CenTax's gradient between under-3s and 3-to-4s, adds about ${formatBn(lo, 2)} to ${formatBn(hi, 2)} to the 30 hours' cost in ${fyLabel(u.age.year)} (on the single take-up draw).`,
  };
}

export default function MethodTab({ data, setting = STATIC_SETTING }) {
  const meta = getMeta(data);
  const reform = getReform(data);
  const validation = getValidation(data);
  const takeUp = getTakeUp(data);
  const fileLimitations = getLimitations(data);
  const takeUpLimitation = fileLimitations.find((l) => l.title === TAKE_UP_LIMITATION);
  const limitations = [...fileLimitations.filter((l) => l !== takeUpLimitation), ageProfileLimitation(data)];
  const assumptions = getAssumptions(data);
  const modelling = getModellingAssumptions(data);
  const years = `${fyLabel(meta.years[0])} to ${fyLabel(meta.years.at(-1))}`;
  const dataset = (meta.dataset_label ?? meta.dataset).replace(/\s*\(.*\)$/, "");

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="method-tab">
      <Section id="model" title="How we cost it" lead="Five steps, from the data to the published figures. Open a step for its detail." boxed={false}>
        <ExpandableGroup testId="method-steps">
          <Step n={1} title="Data" testId="method-step-data">
            <Ext href={MICROCOSM_URL}>{dataset}</Ext>: PolicyEngine&apos;s survey-based dataset of UK households,
            reweighted to official totals.
          </Step>
          <Step
            n={2}
            title="Two runs and the cost"
            testId="method-step-runs"
            detail={
              <>
                <p>
                  The £100,000 test is on each parent, so a couple both earning £95,000 qualify today while a couple
                  earning £101,000 and £20,000 do not.
                </p>
                <p>
                  The pledge names no nation: we read it as England&apos;s 30 hours plus Tax-Free Childcare, which is
                  UK-wide. The devolved governments&apos; own offers, such as the Childcare Offer for Wales with its own
                  £100,000 test, are unchanged.
                </p>
                <p>
                  Families gaining, and how much, come from the same comparison, household by household. What each
                  scheme gives and who qualifies are side by side on <a href="?tab=budget#schemes">Budget impact</a>.
                </p>
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
          >
            For each year, {years}, the model runs on the same households with today&apos;s rules and with the
            £100,000 limit removed from both schemes. The cost is the extra spending on funded hours and Tax-Free
            Childcare top-ups between the two runs.
          </Step>
          <Step
            n={3}
            title="Take-up"
            id="take-up-method"
            testId="method-take-up"
            detail={<TakeUpDetail data={data} limitation={takeUpLimitation} />}
          >
            Each newly eligible child takes up the 30 hours with{" "}
            <Ext href={takeUp.bases[takeUp.headline].source_url}>DfE&apos;s take-up for its age</Ext>, the headline.
          </Step>
          <Step
            n={4}
            title="Sensitivities"
            testId="method-step-sensitivities"
            detail={
              <p>
                How many hours families use, how much childcare spending goes through Tax-Free Childcare, and
                Tax-Free Childcare take-up among newly eligible families. The sampling uncertainty, a bootstrap over the
                survey&apos;s households, is on <a href="?tab=budget#uncertainty">Budget impact</a>.
              </p>
            }
          >
            Further runs change one uncertain assumption at a time; <a href="#assumptions">the comparison below</a>{" "}
            shows what each changes.
          </Step>
          <Step n={5} title="Pinned versions" testId="method-step-versions" detail={<VersionsTable meta={meta} />}>
            The model package and the dataset release are fixed, and the dataset file&apos;s checksum is verified
            before each run, so the results can be rebuilt exactly.
          </Step>
        </ExpandableGroup>
      </Section>

      <LabourSupplySection data={data} />

      <Section
        id="assumptions"
        grouped
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
        grouped
        title="Baseline validation"
        lead="How the model's picture of today, before any reform, compares with official statistics."
        details={
          <p>
            Tax-Free Childcare and the number of people over £100,000 match HMRC closely. The working-parent counts are
            measured as the dataset&apos;s calibration counts them, children funded in the January term by their age on
            31 December, and compared with DfE&apos;s January 2025 census, which the dataset is calibrated to: the 3-
            and 4-year-olds match, and under-3s are a little above. Funded-hours spending is close to DfE&apos;s
            illustrative total for 2026-27. Each official figure links to its source in the table.
          </p>
        }
      >
        <Expandable title="Show the validation table" testId="validation-expandable">
          <ValidationTable rows={validation} />
        </Expandable>
      </Section>

      <Section id="limitations" title="Limitations" lead="What the costing does not capture. Open one for its detail." boxed={false}>
        <ExpandableGroup testId="limitations">
          {limitations.map((l) => {
            const line = (
              <span className="font-normal text-slate-700">
                <strong className="font-semibold text-slate-800">{l.title}.</strong> <RichText text={l.summary} />
              </span>
            );
            const testId = `limitation-${l.id ?? l.title}`;
            return l.detail ? (
              <Expandable key={l.title} title={line} id={l.id} testId={testId} compact>
                <Prose>
                  <p>
                    <RichText text={l.detail} />
                  </p>
                </Prose>
              </Expandable>
            ) : (
              <ExpandableRow key={l.title} compact testId={testId}>
                {line}
              </ExpandableRow>
            );
          })}
        </ExpandableGroup>
      </Section>
    </div>
  );
}
