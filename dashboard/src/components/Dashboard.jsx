"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import LandingTab from "./LandingTab";
import WhoGainsTab from "./WhoGainsTab";
import MethodTab from "./MethodTab";
import {
  fyLabel,
  getLabourSupply,
  getMeta,
  getYears,
  labourSupplyParams,
  LS_BOUND_LABELS,
  LS_BOUNDS,
  parseLabourSupply,
} from "../lib/dataHelpers";
import { TabLayout } from "./ui";

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
    { id: "each-year", title: "Each year" },
  ],
  "who-gains": [
    { id: "household", title: "Your household" },
    { id: "breakdown", title: "Where the gains go" },
    { id: "recipients", title: "Families gaining" },
  ],
  method: [
    { id: "model", title: "How we cost it" },
    { id: "limits", title: "How the limits work" },
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

/** "Replication code: PolicyEngine/uk-childcare-100k-threshold." */
export function ReplicationLine({ meta }) {
  return (
    <p data-testid="replication">
      Built with{" "}
      <a href={`https://pypi.org/project/policyengine/${meta.policyengine}/`} target="_blank" rel="noreferrer">
        policyengine.py {meta.policyengine}
      </a>{" "}
      on {(meta.dataset_label ?? meta.dataset).replace(/\s*\(.*\)$/, "")}. Replication code:{" "}
      <a href={REPO_URL} target="_blank" rel="noreferrer">
        PolicyEngine/uk-childcare-100k-threshold
      </a>
      .
    </p>
  );
}

/** An on/off switch with its label. */
function Toggle({ on, onChange, label, hint, testId }) {
  return (
    <label className="flex cursor-pointer flex-wrap items-center gap-x-2 gap-y-0.5" title={hint}>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={label}
        data-testid={testId}
        onClick={() => onChange(!on)}
        className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
          on ? "bg-[color:var(--pe-color-primary-600)]" : "bg-slate-300"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${on ? "translate-x-4" : "translate-x-0.5"}`}
        />
      </button>
      <span className={on ? "font-semibold text-slate-900" : "text-slate-600"}>{label}</span>
      <span className="text-xs text-slate-500">{hint}</span>
    </label>
  );
}

/**
 * Labour supply: the page opens static. Each margin can be switched on; the elasticity setting scales both. Only the
 * cost figures on Budget impact and the comparison on Methodology change. Shown under the tab bar on Budget impact and
 * Who gains; Methodology explains it.
 */
export function LabourSupplyControl({ data, setting, onChange, tab }) {
  const a = getLabourSupply(data).assumptions;
  const any = setting.extensive || setting.intensive;
  let note;
  if (tab === "who-gains") {
    note =
      "The figures on this tab are always static: who gains, the breakdowns and the household calculator do not change with this setting.";
  } else if (any) {
    note =
      "Changes the cost on this tab and in the comparison on Methodology. The response of parents over £100,000 is not included; Methodology explains what is and is not covered.";
  } else {
    note = "Off: the static costing, with nobody changing how much they work.";
  }
  return (
    <div className="mb-8" data-testid="labour-supply-control">
      <span className="mb-1 block text-xs font-medium text-slate-500">Labour supply</span>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
        <Toggle
          on={setting.extensive}
          onChange={(v) => onChange({ ...setting, extensive: v })}
          label="Extensive margin"
          hint="Moving into work: OBR participation elasticities on the gain to work"
          testId="toggle-extensive"
        />
        <span className="h-5 w-px bg-slate-200" aria-hidden />
        <Toggle
          on={setting.intensive}
          onChange={(v) => onChange({ ...setting, intensive: v })}
          label="Intensive margin"
          hint={`Hours: childcare-price elasticity ${a.hours_price_elasticity}`}
          testId="toggle-intensive"
        />
        {any ? (
          <select
            value={setting.bound}
            onChange={(e) => onChange({ ...setting, bound: e.target.value })}
            className="h-7 rounded-md border border-slate-200 bg-slate-50 px-1.5 text-sm text-slate-700"
            aria-label="Elasticities"
            data-testid="bound-select"
          >
            {LS_BOUNDS.map((b) => (
              <option key={b} value={b}>
                {LS_BOUND_LABELS[b]} elasticities{b === "central" ? "" : ` (x${b === "low" ? "1/3" : "2"})`}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      <p className="mt-1.5 text-xs text-slate-500" data-testid="labour-supply-note">
        {note}
      </p>
    </div>
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

  function replaceUrl(tab, ls) {
    const params = new URLSearchParams([...(tab === DEFAULT_TAB ? [] : [["tab", tab]]), ...labourSupplyParams(ls)]);
    const query = params.toString();
    router.replace(query ? `/?${query}` : "/", { scroll: false });
  }

  function handleTabChange(tab) {
    setActiveTab(tab);
    replaceUrl(tab, setting);
  }

  function handleSettingChange(next) {
    setSetting(next);
    replaceUrl(activeTab, next);
  }

  return (
    <div className="app-shell min-h-screen">
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
            <a href={ANNOUNCEMENT_URL} target="_blank" rel="noreferrer" className="underline">
              pledged
            </a>{" "}
            to remove the limit, paid for by cutting staff at arm&apos;s-length public bodies, with no start date. We cost the
            change with{" "}
            <a href="https://policyengine.org/uk" target="_blank" rel="noreferrer" className="underline">
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

        {activeTab === "budget" || activeTab === "who-gains" ? (
          <LabourSupplyControl data={data} setting={setting} onChange={handleSettingChange} tab={activeTab} />
        ) : null}

        <TabLayout key={activeTab} sections={SECTIONS[activeTab]}>
          {activeTab === "budget" && <LandingTab data={data} setting={setting} />}
          {activeTab === "who-gains" && <WhoGainsTab data={data} />}
          {activeTab === "method" && <MethodTab data={data} setting={setting} />}
        </TabLayout>

        <footer className="mt-12 border-t border-slate-200 pt-8 text-center text-sm text-slate-500">
          <ReplicationLine meta={getMeta(data)} />
        </footer>
      </main>
    </div>
  );
}

export default Dashboard;
