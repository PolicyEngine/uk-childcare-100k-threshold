"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import LandingTab from "./LandingTab";
import WhoGainsTab from "./WhoGainsTab";
import MethodTab from "./MethodTab";
import { fyLabel, getMeta, getYears } from "../lib/dataHelpers";
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
    { id: "comparisons", title: "Against the £0.7bn" },
    { id: "thirty-hours", title: "Inside the 30 hours" },
  ],
  "who-gains": [
    { id: "household", title: "Your household" },
    { id: "breakdown", title: "Where the gains go" },
    { id: "recipients", title: "Families gaining" },
  ],
  method: [
    { id: "model", title: "How we cost it" },
    { id: "limits", title: "How the limits work" },
    { id: "assumptions", title: "Assumptions" },
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

  function handleTabChange(tab) {
    setActiveTab(tab);
    router.replace(tab === DEFAULT_TAB ? "/" : `/?tab=${tab}`, { scroll: false });
  }

  return (
    <div className="app-shell min-h-screen">
      <header className="title-row">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-4 md:px-10 lg:pl-24">
          <h1>Removing the £100,000 childcare limit</h1>
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
            to remove this limit for both schemes, paid for by cutting staff at arm&apos;s-length public bodies; the pledge
            sets no start date. This dashboard costs removing it from
            both schemes with{" "}
            <a href="https://policyengine.org/uk" target="_blank" rel="noreferrer" className="underline">
              PolicyEngine UK
            </a>
            {` from ${period}`}.
          </p>
          <p className="mb-3 text-base leading-7 text-slate-700" data-testid="tab-guide">
            The <strong>Budget impact</strong> tab shows what removing the limit adds to government spending each year,
            split between the two schemes, and how our figure compares with the £0.7bn the party gave.{" "}
            <strong>Who gains</strong>{" "}
            starts with your own household: choose the parents, the children and the
            childcare spending to see how the family&apos;s income changes as earnings pass £100,000, with and without
            the limit. It then shows where the gains go by household income, family type and region, and how many
            families and children gain. <strong>Methodology</strong> explains how we cost it, the assumptions behind
            every figure and what each one changes, how the model compares with official statistics, and what the
            costing leaves out.
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

        <TabLayout key={activeTab} sections={SECTIONS[activeTab]}>
          {activeTab === "budget" && <LandingTab data={data} />}
          {activeTab === "who-gains" && <WhoGainsTab data={data} />}
          {activeTab === "method" && <MethodTab data={data} />}
        </TabLayout>

        <footer className="mt-12 border-t border-slate-200 pt-8 text-center text-sm text-slate-500">
          <ReplicationLine meta={getMeta(data)} />
        </footer>
      </main>
    </div>
  );
}

export default Dashboard;
