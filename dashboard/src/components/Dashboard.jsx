"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import LandingTab from "./LandingTab";
import WhoGainsTab from "./WhoGainsTab";
import MethodTab from "./MethodTab";
import {
  fyLabel,
  LEAD_YEAR,
  getLabourSupply,
  getMeta,
  getTakeUp,
  getYears,
  boundOf,
  labourSupplyParams,
  LS_BOUND_LABELS,
  LS_BOUNDS,
  parseLabourSupply,
  parseTakeUp,
  takeUpParams,
} from "../lib/dataHelpers";
import { Expandable, ExpandableGroup, ExpandableRow, Select, TabLayout, TAKE_UP_OPTIONS_ID } from "./ui";
import { formatBn } from "../lib/formatters";

export const TAB_OPTIONS = [
  { id: "budget", label: "Budget impact" },
  { id: "who-gains", label: "Who gains" },
  { id: "method", label: "Methodology" },
];
export const DEFAULT_TAB = "budget";

// Each tab's sections, for the "On this tab" links (the ids are set in the sections themselves).
const SECTIONS = {
  budget: [
    { id: "at-a-glance", title: "At a glance" },
    { id: "schemes", title: "Each scheme" },
    { id: "each-year", title: "Each year" },
    { id: "uncertainty", title: "How certain" },
  ],
  "who-gains": [
    { id: "household", title: "Your household" },
    { id: "breakdown", title: "Where the gains go" },
    { id: "recipients", title: "Families gaining" },
    { id: "gender", title: "Mothers and fathers" },
  ],
  method: [
    { id: "model", title: "How we cost it" },
    { id: "labour-supply", title: "Labour supply" },
    { id: "assumptions", title: "Compared with others" },
    { id: "validation", title: "Validation" },
    { id: "limitations", title: "Limitations" },
  ],
};

const ANNOUNCEMENT_URL = "https://www.conservatives.com/news/conservatives-pledge-to-abolish-absurd-childcare-cliff-edge";
const REPO_URL = "https://github.com/PolicyEngine/uk-childcare-100k-threshold";

// The cliff had its own tab before it joined "Who gains"; old links still land on it.
const TAB_ALIASES = { cliff: "who-gains" };

function getInitialTab(tabParam) {
  const tab = TAB_ALIASES[tabParam] ?? tabParam;
  return TAB_OPTIONS.some((t) => t.id === tab) ? tab : DEFAULT_TAB;
}

/** "Built with policyengine.py <version from results meta>. Replication code: PolicyEngine/uk-childcare-100k-threshold." */
export function ReplicationLine({ meta }) {
  return (
    <p data-testid="replication">
      Built with{" "}
      <a href={`https://pypi.org/project/policyengine/${meta.policyengine}/`} target="_blank" rel="noopener noreferrer">
        policyengine.py {meta.policyengine}
      </a>
      . Replication code:{" "}
      <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
        PolicyEngine/uk-childcare-100k-threshold
      </a>
      .
    </p>
  );
}

/** An on/off switch with its label. */
const OBR_ELASTICITIES_URL = "https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf";
const BREWER_URL =
  "https://ifs.org.uk/sites/default/files/output_url_files/WP202009-Does-more-free-childcare-help-parents-work-more.pdf#page=41";

/**
 * One response as a card: the title row is the switch; under it the margin and, when on, the setting; the
 * description and source closed underneath.
 */
function ResponseCard({ on, onChange, bound, onBound, title, tag, description, source, testId }) {
  return (
    <div
      className={`flex flex-col rounded-xl border px-4 py-2.5 transition-colors ${
        on ? "border-[color:var(--pe-color-primary-600)] bg-[color:var(--pe-color-primary-50)]" : "border-slate-200 bg-white"
      }`}
      data-testid={`${testId}-card`}
    >
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={title}
        data-testid={testId}
        onClick={() => onChange(!on)}
        className="flex w-full items-center justify-between gap-3 text-left"
      >
        <span className="font-semibold text-slate-900">{title}</span>
        <span
          aria-hidden
          className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
            on ? "bg-[color:var(--pe-color-primary-600)]" : "bg-slate-300"
          }`}
        >
          <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${on ? "translate-x-4" : "translate-x-0.5"}`} />
        </span>
      </button>
      <div className="mt-1 flex min-h-6 flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span className="text-[11px] font-semibold uppercase tracking-wide">{tag}</span>
        {on ? (
          <label className="flex items-center gap-1.5">
            Setting
            <select
              value={bound}
              onChange={(e) => onBound(e.target.value)}
              className="h-6 rounded-full border border-slate-200 bg-white px-2 text-xs font-medium text-slate-800"
              aria-label={`${title}: setting`}
              data-testid={`${testId}-bound`}
            >
              {LS_BOUNDS.map((x) => (
                <option key={x} value={x}>
                  {LS_BOUND_LABELS[x]}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>
      <details className="group mt-1 text-sm" data-testid={`${testId}-details`}>
        <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded text-xs font-semibold text-slate-600 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--pe-color-primary-600)]">
          Details
          <span aria-hidden="true" className="text-slate-500 transition-transform group-open:rotate-90">
            ›
          </span>
        </summary>
        <p className="mt-1 leading-5 text-slate-600">{description}</p>
        <p className="mt-1 text-xs text-slate-500">
          Source: {source}. How it is modelled: <a href="?tab=method#labour-supply">Methodology</a>.
        </p>
      </details>
    </div>
  );
}

/**
 * Labour supply: the page opens static. Each response can be switched on; the setting picks low, central or high for
 * all of them. Only the cost figures on Budget impact and the comparison on Methodology change, so it is shown under
 * the tab bar on Budget impact only; Methodology explains it.
 */
export function LabourSupplyControl({ data, setting, onChange }) {
  const ls = getLabourSupply(data);
  const a = ls.assumptions;
  const link = (href, text) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="underline">
      {text}
    </a>
  );
  return (
    <div className="mb-8" data-testid="labour-supply-control">
      <div className="grid gap-3 md:grid-cols-2">
        <ResponseCard
          on={setting.extensive}
          onChange={(v) => onChange({ ...setting, extensive: v })}
          bound={boundOf(setting, "extensive")}
          onBound={(x) => onChange({ ...setting, bounds: { ...setting.bounds, extensive: x } })}
          tag="Extensive margin"
          title="Partners move into work"
          description="A partner who doesn't work may start, now that working brings the family childcare support."
          source={link(OBR_ELASTICITIES_URL, "OBR participation elasticities")}
          testId="toggle-extensive"
        />
        <ResponseCard
          on={setting.intensive}
          onChange={(v) => onChange({ ...setting, intensive: v })}
          bound={boundOf(setting, "intensive")}
          onBound={(x) => onChange({ ...setting, bounds: { ...setting.bounds, intensive: x } })}
          tag="Intensive margin"
          title="Parents change their hours"
          description="Parents in work, at any income, may work more as an extra hour of childcare gets cheaper, and a little less as their family is better off."
          source={
            <>
              {link(BREWER_URL, "Brewer et al., IFS WP20/09")} (price, assumed {a.hours_price_elasticity}),{" "}
              {link(OBR_ELASTICITIES_URL, "OBR income elasticities")}
            </>
          }
          testId="toggle-intensive"
        />
      </div>
    </div>
  );
}

/** A take-up option's name in the selector: its short label, marked when it is the headline. */
export function takeUpOptionName(t, id) {
  return `${t.bases[id].short_label}${id === t.headline ? " (headline)" : ""}`;
}

/**
 * Who takes up the 30 hours among newly eligible children: one drop-down, the headline (DfE's rates by age) chosen
 * by default, each option showing the 30 hours' cost it gives in the first full year. What each option is, and its
 * source, is in a closed row under the drop-down, in the same box; it is the one place on Budget impact that states
 * the rates.
 */
export function TakeUpControl({ data, basis, onChange }) {
  const t = getTakeUp(data);
  const year = String(LEAD_YEAR);
  const cost = (id) => formatBn(t.bases[id].gross_bn.thirty_hours[year], 2);
  const options = t.order.map((id) => ({ id, label: `${takeUpOptionName(t, id)}: ${cost(id)}` }));
  return (
    <ExpandableGroup className="mb-4" testId="take-up-control">
      <ExpandableRow compact testId="take-up-row">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <Select
            label="Take-up"
            ariaLabel="Take-up of the 30 hours among newly eligible families"
            options={options}
            value={basis}
            onChange={onChange}
            testId="take-up-select"
            nowrapLabel
          />
          <span className="text-xs text-slate-500">Each option&apos;s 30 hours cost in {fyLabel(LEAD_YEAR)}</span>
        </div>
      </ExpandableRow>
      <Expandable title="About these take-up options" testId="take-up-options" id={TAKE_UP_OPTIONS_ID} compact>
        <ul className="space-y-3 text-sm leading-5 text-slate-600">
          {t.order.map((id) => {
            const b = t.bases[id];
            return (
              <li key={id} data-testid={`take-up-option-${id}`} aria-current={id === basis ? "true" : undefined}>
                <span className={`font-semibold ${id === basis ? "text-[color:var(--pe-color-primary-700)]" : "text-slate-800"}`}>
                  {b.short_label}
                </span>
                {id === t.headline ? (
                  <span className="ml-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Headline</span>
                ) : null}
                <span className="block">{b.description}.</span>
                <span className="block text-xs text-slate-500">
                  Source:{" "}
                  <a href={b.source_url} target="_blank" rel="noopener noreferrer" className="underline">
                    {b.source}
                  </a>
                </span>
              </li>
            );
          })}
        </ul>
      </Expandable>
    </ExpandableGroup>
  );
}

export function Dashboard({ data }) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState(() => getInitialTab(searchParams.get("tab")));
  const years = getYears(data);
  const period = `${fyLabel(years[0])} to ${fyLabel(years.at(-1))}`;

  // Follow the URL when it changes (back/forward), adjusting state during render rather than in an effect.
  const tabParam = searchParams.get("tab");
  const [seenParam, setSeenParam] = useState(tabParam);
  if (tabParam !== seenParam) {
    setSeenParam(tabParam);
    setActiveTab(getInitialTab(tabParam));
  }

  // Labour supply, kept in the URL beside the tab (?ls=ext,int&bound=low); static by default.
  const lsParam = searchParams.get("ls");
  const boundParam = searchParams.get("bound");
  const [setting, setSetting] = useState(() => parseLabourSupply(lsParam, boundParam));
  const [seenLs, setSeenLs] = useState(`${lsParam}|${boundParam}`);
  if (`${lsParam}|${boundParam}` !== seenLs) {
    setSeenLs(`${lsParam}|${boundParam}`);
    setSetting(parseLabourSupply(lsParam, boundParam));
  }

  // The 30 hours take-up basis, kept in the URL as ?takeup=centax; the headline (DfE by age) by default.
  const takeUpParam = searchParams.get("takeup");
  const [basis, setBasis] = useState(() => parseTakeUp(takeUpParam, data));
  const [seenTakeUp, setSeenTakeUp] = useState(takeUpParam);
  if (takeUpParam !== seenTakeUp) {
    setSeenTakeUp(takeUpParam);
    setBasis(parseTakeUp(takeUpParam, data));
  }

  function replaceUrl(tab, ls, takeUp) {
    const params = new URLSearchParams([
      ...(tab === DEFAULT_TAB ? [] : [["tab", tab]]),
      ...labourSupplyParams(ls),
      ...takeUpParams(takeUp, data),
    ]);
    const query = params.toString();
    router.replace(query ? `/?${query}` : "/", { scroll: false });
  }

  function handleTabChange(tab) {
    setActiveTab(tab);
    replaceUrl(tab, setting, basis);
  }

  function handleSettingChange(next) {
    setSetting(next);
    replaceUrl(activeTab, next, basis);
  }

  function handleBasisChange(next) {
    setBasis(next);
    replaceUrl(activeTab, setting, next);
  }

  return (
    <div className="app-shell min-h-screen overflow-x-clip">
      <header className="title-row">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-4 md:px-10 lg:pl-24">
          <h1>Scrapping the childcare cliff edge</h1>
        </div>
      </header>

      <main className="relative z-[1] mx-auto max-w-[1600px] px-6 py-10 md:px-10 md:py-12 lg:pl-24 lg:pr-[284px]">
        <div className="animate-[fadeIn_0.4s_ease-out]">
          <p className="mb-3 text-base leading-7 text-slate-700" data-testid="intro">
            Working parents lose the 30 funded hours of childcare in England, and Tax-Free Childcare across the UK, once
            either parent&apos;s adjusted net income passes £100,000. On 4 October 2026 Conservative leader Kemi
            Badenoch{" "}
            <a href={ANNOUNCEMENT_URL} target="_blank" rel="noopener noreferrer" className="underline">
              pledged
            </a>{" "}
            to remove the limit, paid for by cutting staff at arm&apos;s-length public bodies, with no start date. We cost the
            change with{" "}
            <a href="https://policyengine.org/uk" target="_blank" rel="noopener noreferrer" className="underline">
              PolicyEngine UK
            </a>
            {` from ${period}`}: <strong>Budget impact</strong> shows the cost each year,{" "}
            <strong>Who gains</strong> lets you try your own household and shows where the gains go, and{" "}
            <strong>Methodology</strong> sets out our assumptions and how we compare with other estimates.
          </p>
        </div>

        <div
          className="mb-8 mt-8 flex w-fit flex-wrap border-b-2 border-slate-200"
          role="tablist"
          aria-label="Dashboard sections"
        >
          {TAB_OPTIONS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              className={`tab-button ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => handleTabChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Only Budget impact's figures change with the take-up and labour supply settings, so the controls show only there. */}
        {activeTab === "budget" ? (
          <>
            <TakeUpControl data={data} basis={basis} onChange={handleBasisChange} />
            <LabourSupplyControl data={data} setting={setting} onChange={handleSettingChange} />
          </>
        ) : null}

        <TabLayout key={activeTab} sections={SECTIONS[activeTab]}>
          {activeTab === "budget" && <LandingTab data={data} setting={setting} basis={basis} />}
          {activeTab === "who-gains" && <WhoGainsTab data={data} />}
          {activeTab === "method" && <MethodTab data={data} setting={setting} />}
        </TabLayout>

        <footer className="mt-10 border-t border-slate-200 pt-5 text-center text-sm text-slate-500">
          <ReplicationLine meta={getMeta(data)} />
        </footer>
      </main>
    </div>
  );
}

export default Dashboard;
