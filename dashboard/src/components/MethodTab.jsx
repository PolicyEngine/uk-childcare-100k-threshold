"use client";

import {
  fyLabel,
  getLabourSupply,
  getLimitations,
  getMeta,
  getModellingAssumptions,
  getReform,
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

function VersionsTable({ meta }) {
  const rows = [
    [
      "Model package",
      <>
        <a href={`https://pypi.org/project/policyengine/${meta.policyengine}/`} target="_blank" rel="noopener noreferrer">
          policyengine.py {meta.policyengine}
        </a>
        , pinned exactly
      </>,
    ],
    [
      "Tax and benefit rules",
      <>
        <a href={`https://github.com/PolicyEngine/policyengine-uk/tree/${meta.policyengine_uk}`} target="_blank" rel="noopener noreferrer">
          policyengine-uk {meta.policyengine_uk}
        </a>
        , the version the dataset is built for
      </>,
    ],
    ["Dataset", meta.dataset_label ?? meta.dataset],
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

/** Each modelling choice as a bullet: what we assume, then its sources. */
function AssumptionNotes({ rows }) {
  return rows.map((r) => (
    <li key={r.id} id={r.id === "take_up" ? "take-up-rates" : undefined} data-testid={`choice-${r.id}`}>
      <strong className="font-semibold text-slate-800">{r.title}.</strong> <RichText text={r.modelled} />{" "}
      {(r.sources ?? []).map((x, i) => (
        <span key={x.url + x.label}>
          {i === 0 ? "Sources: " : "; "}
          <a href={x.url} target="_blank" rel="noopener noreferrer">
            {x.label}
          </a>
          {i === r.sources.length - 1 ? "." : ""}
        </span>
      ))}
    </li>
  ));
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

/** Detail under a list item's "More". */
function Prose({ children }) {
  return <div className="space-y-2">{children}</div>;
}

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
      <p className="text-sm font-semibold text-slate-800">What we find, {year}</p>
      <BulletList className="mt-2" testId="labour-supply-details">
        <li data-testid="labour-supply-method">
          <strong className="font-semibold text-slate-800">Partners moving into work:</strong> about{" "}
          {formatCount(entrants)}, who {extText}.
          {extOffset < 0
            ? " Both parents must work for the family to qualify, so a partner starting work unlocks the 30 hours and Tax-Free Childcare."
            : ""}
        </li>
        <li>
          <strong className="font-semibold text-slate-800">Parents changing their hours:</strong> a net{" "}
          {formatMoneyBn(ls.intensive.offset.central[li])} back, at central elasticities. The price effect brings back{" "}
          {formatMoneyBn(ls.intensive.price.central[li])}, as cheaper childcare pulls hours up; the income effect costs{" "}
          {formatMoneyBn(-ls.intensive.income.central[li])}, as being better off pulls them down.
        </li>
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
        <ListItem title="Who responds" testId="ls-who">
          <RichText text={raw.responding_population} />
        </ListItem>
        <ListItem title="Moving into work: method" testId="ls-extensive">
          <p>
            The <Ext href={OBR_NOTE_URL}>OBR&apos;s participation elasticities</Ext> (
            <RichText text={a.participation_elasticities} />
            ), applied to the gain from working net of the childcare a parent would then pay for. Entrants work{" "}
            {a.hours_for_new_entrants} hours a week.
          </p>
          <p>
            Why so few: a partner&apos;s gain from working is small next to the family&apos;s income, and the tax they
            pay is set against the childcare support their family then receives. The hours response, of parents
            already in work whose family the reform makes eligible however many hours they work, changes earnings
            without unlocking support, so it brings money back.
          </p>
        </ListItem>
        <ListItem title="Hours: method" testId="ls-intensive">
          <p>
            It responds to the price of childcare, not to marginal tax rates, because everyone who responds becomes
            eligible whatever they earn; parents holding income just under £100,000 (bunching) are not modelled.
          </p>
          <p>
            <em>Price effect:</em> an assumed childcare-price elasticity of hours of {a.hours_price_elasticity}, an
            extrapolated scenario assumption, not an estimated price elasticity (
            <Ext href={BREWER_URL}>Brewer, Cattan, Crawford and Rabe, IFS WP20/09</Ext>), applied to the price of the
            family&apos;s next hour of paid childcare after Tax-Free Childcare and Universal Credit support.
          </p>
          <p>
            <em>Income effect:</em> the <Ext href={OBR_NOTE_URL}>OBR&apos;s income elasticities</Ext> (
            <RichText text={a.income_elasticities} />) times the family&apos;s gain from the reform as a share of its
            disposable income: a family made better off works slightly less.
          </p>
          <p>
            Of the price effect in {year}, {formatMoneyBn(ls.intensive.at_or_below_limit.price.central[li])} comes
            from adults at or below £100,000 and {formatMoneyBn(ls.intensive.over_limit.price.central[li])} from those
            over it; of the income effect, {formatMoneyBn(-ls.intensive.at_or_below_limit.income.central[li])} and{" "}
            {formatMoneyBn(-ls.intensive.over_limit.income.central[li])}.
          </p>
        </ListItem>
        <ListItem title="Sensitivities" testId="ls-sensitivities">
          <p>
            Low and high multiply every elasticity by {scale(a.elasticity_scales.low)} and by{" "}
            {scale(a.elasticity_scales.high)}: an illustrative range, not a sourced uncertainty interval. More tests
            are in the <Ext href={METHOD_URL}>method notes on GitHub</Ext>.
          </p>
        </ListItem>
        <ListItem title="Couples" testId="ls-checks">
          <RichText text={a.couples} />
        </ListItem>
      </BulletList>
    </Card>
  );
}

/** One section of the tab as a card: a title, a one-line intro, and its content as bullets. */
function Card({ id, title, lead, children }) {
  return (
    <section id={id} className="mt-6 scroll-mt-16 first:mt-0" data-testid={`section-${id}`}>
      <div className="panel">
        <h2 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h2>
        {lead ? <p className="mt-1 text-sm leading-6 text-slate-500">{lead}</p> : null}
        <div className="mt-4">{children}</div>
      </div>
    </section>
  );
}

/** One step of the costing, an item of a numbered list: a one-line summary, and its detail behind "More". */
function Step({ title, children, detail, id, testId }) {
  return (
    <ListItem title={title} summary={children} id={id} testId={testId}>
      {detail ? <Prose>{detail}</Prose> : null}
    </ListItem>
  );
}

/** The limitation on take-up among newly eligible families: its one home is the Take-up step, not Limitations. */
const TAKE_UP_LIMITATION = "Take-up among newly eligible families";

/** The flat rate's cost per point, how to switch between the options, and what is uncertain about take-up. */
function TakeUpDetail({ data, limitation }) {
  const t = getTakeUp(data);
  const flat = t.order.map((id) => t.bases[id]).find((b) => b.unit === "family");
  return (
    <>
      {flat ? (
        <p>
          On the dataset&apos;s flat rate ({formatPct(flat.rate * 100, 1)}{" "}
          of families), each percentage point moves the 30 hours&apos; cost by about{" "}
          £{flat.per_point_m[String(LEAD_YEAR)]}m in {fyLabel(LEAD_YEAR)}.
        </p>
      ) : null}
      <p>
        <a href="?tab=budget#take-up-options">Budget impact</a>{" "}
        switches between the options; why DfE&apos;s rates are the headline is under{" "}
        <a href="#take-up-rates">Who takes up the 30 hours</a> below.
      </p>
      {limitation ? (
        <p data-testid="take-up-limitation">
          <strong className="font-semibold text-slate-700">What is uncertain.</strong> <RichText text={limitation.detail} />
        </p>
      ) : null}
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
    summary: `The dataset has few 1-year-olds in families with a parent over £100,000: ${pct(share["1"])}, against ${pct(Math.min(...others))} to ${pct(Math.max(...others))} at the other ages under 5.`,
    detail: `No source outside the survey crosses income with a child's age. Spreading the newly entitled 1-to-4-year-olds evenly across those ages, or on CenTax's gradient, adds about ${formatBn(lo, 2)} to ${formatBn(hi, 2)} to the 30 hours' cost in ${fyLabel(u.age.year)}, measured on the dataset's own record of who claims.`,
  };
}

/** The reform's two parameters, named in words. */
const PARAMETER_NAMES = {
  "gov.dfe.extended_childcare_entitlement.income.limit": "30 hours income limit",
  "gov.hmrc.tax_free_childcare.income.income_limit": "Tax-Free Childcare income limit",
};

export default function MethodTab({ data, setting = STATIC_SETTING }) {
  const meta = getMeta(data);
  const reform = getReform(data);
  const validation = getValidation(data);
  const takeUp = getTakeUp(data);
  const fileLimitations = getLimitations(data);
  const takeUpLimitation = fileLimitations.find((l) => l.title === TAKE_UP_LIMITATION);
  const limitations = [...fileLimitations.filter((l) => l !== takeUpLimitation), ageProfileLimitation(data)];
  const modelling = getModellingAssumptions(data);
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
          <Step
            title="Two runs and the cost"
            testId="method-step-runs"
            detail={
              <>
                <p>
                  The £100,000 test is on each parent: a couple both earning £95,000 qualify today, a couple earning
                  £101,000 and £20,000 do not. We read the pledge as England&apos;s 30 hours plus UK-wide Tax-Free
                  Childcare; the devolved governments&apos; own offers are unchanged.{" "}
                  <a href="?tab=budget#schemes">Budget impact</a> sets out each scheme.
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
                          <td>{PARAMETER_NAMES[p.name] ?? p.name}</td>
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
            title="Take-up"
            id="take-up-method"
            testId="method-take-up"
            detail={<TakeUpDetail data={data} limitation={takeUpLimitation} />}
          >
            Each newly eligible child takes up the 30 hours with{" "}
            <Ext href={takeUp.bases[takeUp.headline].source_url}>DfE&apos;s take-up for its age</Ext>, the headline.
          </Step>
          <Step
            title="Sensitivities"
            testId="method-step-sensitivities"
            detail={
              <p>
                The sampling uncertainty, from resampling the survey&apos;s households, is on{" "}
                <a href="?tab=budget#uncertainty">Budget impact</a>.
              </p>
            }
          >
            Further runs change one uncertain assumption at a time; <a href="#assumptions">the comparison below</a>{" "}
            shows what each changes.
          </Step>
          <Step title="Pinned versions" testId="method-step-versions" detail={<VersionsTable meta={meta} />}>
            The model and dataset versions are fixed and the dataset&apos;s checksum is checked before each run, so the
            results can be rebuilt exactly.
          </Step>
        </BulletList>
      </Card>

      <LabourSupplySection data={data} />

      <Card
        id="assumptions"
        title="How do we compare with other estimates?"
        lead="Our costing set against CenTax's, the Conservatives' figure, and the official sources and law."
      >
        <Expandable title="Show the comparison table" testId="comparison-expandable" compact>
          <UnifiedComparison data={data} setting={setting} />
        </Expandable>
        <BulletList className="mt-4" testId="assumption-notes">
          <ListItem title="Each choice in full" testId="choices">
            <BulletList>
              <AssumptionNotes rows={modelling} />
            </BulletList>
            <EffectsTable rows={modelling} years={meta.years} />
          </ListItem>
          <BenchmarkNotes data={data} />
        </BulletList>
      </Card>

      <Card
        id="validation"
        title="Baseline validation"
        lead="How the model's picture of today, before any reform, compares with official statistics."
      >
        <Expandable title="Show the validation table" testId="validation-expandable" compact>
          <ValidationTable rows={validation} />
        </Expandable>
        <BulletList className="mt-4" testId="validation-notes">
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
