"use client";

import {
  fyLabel,
  getLabourSupply,
  getLimitations,
  getMeta,
  getTakeUp,
  getUncertainty,
  getValidation,
  LEAD_YEAR,
  STATIC_SETTING,
} from "../lib/dataHelpers";
import { formatBn, formatCount, formatCurrency, formatMoneyBn, formatPct } from "../lib/formatters";
import { BenchmarkNotes, CENTAX, UnifiedComparison } from "./Comparison";
import { BulletList, Expandable, ListItem, RichText } from "./ui";

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
const METHOD_URL = `${REPO_URL}/blob/main/docs/METHOD.md`;
const MICROCOSM_URL = "https://github.com/PolicyEngine/microcosm";


function ValidationTable({ rows }) {
  // One dataset in the file: the dataset column appears only if rows from more than one are present.
  // The model's parameter rows ("parameters") are not a dataset.
  const datasets = [...new Set(rows.filter((r) => "dataset" in r && r.dataset !== "parameters").map((r) => r.dataset))];
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

const OBR_NOTE_URL = "https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf";
const BREWER_URL =
  "https://ifs.org.uk/sites/default/files/output_url_files/WP202009-Does-more-free-childcare-help-parents-work-more.pdf#page=41";
const CENTAX_TABLE_URL =
  "https://centax.org.uk/wp-content/uploads/2026/09/AdvaniFlewPepin-HallSummers2026_Removing-the-childcare-cliff-edge.pdf#page=42";

const Ext = ({ href, children }) => (
  <a href={href} target="_blank" rel="noopener noreferrer">
    {children}
  </a>
);

function LabourSupplySection({ data }) {
  const ls = getLabourSupply(data);
  const a = ls.assumptions;
  const raw = data.labour_supply;
  const li = ls.years.length - 1;
  const year = fyLabel(ls.years[li]);
  const entrants = Math.round(ls.extensive.entrants.central[li] / 100) * 100;
  const extOffset = ls.extensive.offset.central[li];
  const scale = (x) => (Math.abs(x - 1 / 3) < 0.001 ? "1/3" : String(x));
  const extText = extOffset < 0 ? `add ${formatMoneyBn(-extOffset)} to the cost` : `bring back ${formatMoneyBn(extOffset)}`;
  return (
    <Card
      id="labour-supply"
      title="Labour supply"
      lead={
        <>
          Our headline assumes nobody changes how much they work. The Labour supply switches on{" "}
          <a href="?tab=budget">Budget impact</a> add a work response: the cost then shown is the static cost less the
          extra tax and National Insurance, net of the extra childcare support and benefits the response brings.
        </>
      }
    >
      <Subhead>What we find, {year}</Subhead>
      <BulletList testId="labour-supply-details">
        <li data-testid="labour-supply-method">
          <strong className="font-semibold text-slate-900">Partners moving into work:</strong> about{" "}
          {formatCount(entrants)}, who {extText}.
          {extOffset < 0
            ? " Both parents must work for the family to qualify, so a partner starting work unlocks the 30 hours and Tax-Free Childcare."
            : ""}
        </li>
        <li>
          <strong className="font-semibold text-slate-900">Parents changing their hours:</strong> a net{" "}
          {formatMoneyBn(ls.intensive.offset.central[li])} back, at central elasticities. The price effect brings back{" "}
          {formatMoneyBn(ls.intensive.price.central[li])}, as cheaper childcare pulls hours up; the income effect costs{" "}
          {formatMoneyBn(-ls.intensive.income.central[li])}, as being better off pulls them down.
        </li>
      </BulletList>
      <Subhead>How it compares</Subhead>
      <BulletList>
        <ListItem title="Not modelled" summary={ls.notModelled} testId="ls-not-modelled" />
        <ListItem
          title="Compared with CenTax"
          testId="ls-centax"
          summary={
            <>
              CenTax&apos;s{" "}
              <Ext href={CENTAX_TABLE_URL}>
                {formatBn(CENTAX.parentsBn, 2)} from parents who stop holding their income below £100,000
              </Ext>{" "}
              is bunching, which we do not model; their {formatBn(CENTAX.partnersBn, 2)} from partners entering work
              in {CENTAX.year} compares with our figure above. Our hours response has no CenTax counterpart.
            </>
          }
        />
      </BulletList>
      <Subhead>Method</Subhead>
      <BulletList>
        <ListItem title="Who responds" testId="ls-who" summary={<RichText text={raw.responding_population} />} />
        <ListItem
          title="Moving into work"
          testId="ls-extensive"
          summary={
            <>
              The <Ext href={OBR_NOTE_URL}>OBR&apos;s participation elasticities</Ext>, applied to the gain from
              working after childcare costs; entrants work {a.hours_for_new_entrants}{" "}
              hours a week. Few move because a partner&apos;s gain is small next to the family&apos;s income, and their
              tax is set against the support the family then gets.
            </>
          }
        />
        <ListItem
          title="Hours"
          testId="ls-intensive"
          summary={
            <>
              It follows the price of childcare, not marginal tax rates: parents already in work become eligible
              however many hours they work. The price elasticity is an assumed {a.hours_price_elasticity} (
              <Ext href={BREWER_URL}>Brewer et al.</Ext>, extrapolated); the income response uses the{" "}
              <Ext href={OBR_NOTE_URL}>OBR&apos;s income elasticities</Ext>. Of the price effect,{" "}
              {formatMoneyBn(ls.intensive.at_or_below_limit.price.central[li])} comes from adults at or below
              £100,000 and {formatMoneyBn(ls.intensive.over_limit.price.central[li])} from those over it; of the
              income effect, {formatMoneyBn(-ls.intensive.at_or_below_limit.income.central[li])} and{" "}
              {formatMoneyBn(-ls.intensive.over_limit.income.central[li])}.
            </>
          }
        />
        <ListItem
          title="Sensitivities"
          testId="ls-sensitivities"
          summary={
            <>
              Low and high multiply every elasticity by {scale(a.elasticity_scales.low)} and by{" "}
              {scale(a.elasticity_scales.high)}, an illustrative range; more tests are in the{" "}
              <Ext href={METHOD_URL}>method notes on GitHub</Ext>.
            </>
          }
        />
        <ListItem title="Couples" testId="ls-checks" summary={<RichText text={a.couples} />} />
      </BulletList>
    </Card>
  );
}

/** One section of the tab as a card: a title, a one-line muted intro, then its content. */
function Card({ id, title, lead, children }) {
  return (
    <section id={id} className="mt-8 scroll-mt-16 first:mt-0" data-testid={`section-${id}`}>
      {/* Narrower padding on a phone so the text keeps a readable width. */}
      <div className="panel max-sm:px-4 max-sm:py-5">
        <h2 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h2>
        {lead ? <p className="mt-1 text-base leading-relaxed text-slate-600">{lead}</p> : null}
        <div className="mt-5">{children}</div>
      </div>
    </section>
  );
}

/** A small heading for a group of bullets inside a card. */
function Subhead({ children }) {
  return <h3 className="mb-2 mt-6 text-sm font-semibold uppercase tracking-wide text-slate-600 first:mt-0">{children}</h3>;
}

/** One step of the costing, an item of a numbered list, all inline. */
function Step({ title, children, id, testId }) {
  return <ListItem title={title} summary={children} id={id} testId={testId} />;
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
    summary: `The dataset has few 1-year-olds in families with a parent over £100,000: ${pct(share["1"])}, against ${pct(Math.min(...others))} to ${pct(Math.max(...others))} at the other ages under 5.`,
    detail: `No source outside the survey crosses income with a child's age. Spreading the newly entitled 1-to-4-year-olds evenly across those ages, or on CenTax's gradient, adds about ${formatBn(lo, 2)} to ${formatBn(hi, 2)} to the 30 hours' cost in ${fyLabel(u.age.year)}, measured on the dataset's own record of who claims.`,
  };
}


export default function MethodTab({ data, setting = STATIC_SETTING }) {
  const meta = getMeta(data);
  const validation = getValidation(data);
  const takeUp = getTakeUp(data);
  const fileLimitations = getLimitations(data);
  const limitations = [...fileLimitations, ageProfileLimitation(data)];
  const flat = takeUp.order.map((id) => takeUp.bases[id]).find((b) => b.unit === "family");
  const years = `${fyLabel(meta.years[0])} to ${fyLabel(meta.years.at(-1))}`;
  const dataset = (meta.dataset_label ?? meta.dataset).replace(/\s*\(.*\)$/, "");

  return (
    <div className="animate-[fadeIn_0.4s_ease-out]" data-testid="method-tab">
      <Card id="model" title="How we cost it" lead="Five steps, from the data to the published figures.">
        <BulletList ordered testId="method-steps">
          <Step title="Data" testId="method-step-data">
            <Ext href={MICROCOSM_URL}>{dataset}</Ext>: PolicyEngine&apos;s survey-based dataset of UK households,
            reweighted to official totals.
          </Step>
          <Step title="Two runs and the cost" testId="method-step-runs">
            For each year, {years}, the model runs on the same households with today&apos;s rules and with the
            £100,000 limit removed from England&apos;s 30 hours and UK-wide Tax-Free Childcare (set out on{" "}
            <a href="?tab=budget#schemes">Budget impact</a>). The limit tests each parent: a couple both earning £95,000
            qualify today. The cost is the extra spending between the two runs.
          </Step>
          <Step title="Take-up" id="take-up-method" testId="method-take-up">
            Each newly eligible child takes up the 30 hours at{" "}
            <Ext href={takeUp.bases[takeUp.headline].source_url}>DfE&apos;s rate for its age</Ext>.{" "}
            <a href="?tab=budget#take-up-options">Budget impact</a>
            {" also offers CenTax's rates and one flat rate"}
            {flat ? ` (each point of which moves the 30 hours by about £${flat.per_point_m[String(LEAD_YEAR)]}m in ${fyLabel(LEAD_YEAR)})` : ""};{" "}
            <a href="#limitations">Limitations</a> says why take-up is uncertain.
          </Step>
          <Step title="Sensitivities" testId="method-step-sensitivities">
            Further runs change one uncertain assumption at a time; <a href="#assumptions">the comparison table</a>{" "}
            shows what each changes, and <a href="?tab=budget#uncertainty">Budget impact</a> the sampling uncertainty.
          </Step>
          <Step title="Pinned versions" testId="method-step-versions">
            {`policyengine.py ${meta.policyengine}, policyengine-uk ${meta.policyengine_uk} and the dataset are fixed, and the dataset's checksum is checked before each run, so the results can be rebuilt exactly from `}
            <Ext href={`${REPO_URL}/commit/${meta.git_revision}`}>this code revision</Ext>.
          </Step>
        </BulletList>
      </Card>

      <LabourSupplySection data={data} />

      <Card
        id="assumptions"
        title="How do we compare with other estimates?"
        lead="Our costing set against CenTax's, the Conservatives' figure, and the official sources and law."
      >
        <Subhead>The table</Subhead>
        <Expandable title="Show the comparison table" testId="comparison-expandable" compact>
          <UnifiedComparison data={data} setting={setting} />
        </Expandable>
        <p className="mt-3 text-sm leading-6 text-slate-600" data-testid="choices-method-link">
          More on each choice is in the <Ext href={METHOD_URL}>method notes on GitHub</Ext>.
        </p>
        <BenchmarkNotes data={data} Heading={Subhead} />
      </Card>

      <Card
        id="validation"
        title="Baseline validation"
        lead="How the model's picture of today, before any reform, compares with official statistics."
      >
        <Expandable title="Show the validation table" testId="validation-expandable" compact>
          <ValidationTable rows={validation} />
        </Expandable>
        <BulletList className="mt-5" testId="validation-notes">
          <li>Tax-Free Childcare and the number of people over £100,000 match HMRC closely.</li>
          <li>
            Working-parent counts match DfE&apos;s January 2025 census for 3- and 4-year-olds; under-3s are a little
            above. Funded-hours spending is close to DfE&apos;s illustrative totals.
          </li>
        </BulletList>
      </Card>

      <Card id="limitations" title="Limitations" lead="What the costing does not capture.">
        <BulletList testId="limitations">
          {limitations.map((l) => (
            <ListItem
              key={l.title}
              title={l.title}
              summary={<RichText text={l.summary} />}
              id={l.id}
              testId={`limitation-${l.id ?? l.title}`}
            >
              {l.detail ? <RichText text={l.detail} /> : null}
            </ListItem>
          ))}
        </BulletList>
      </Card>
    </div>
  );
}
