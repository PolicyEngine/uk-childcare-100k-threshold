"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import LandingTab from "./LandingTab";
import WhoGainsTab from "./WhoGainsTab";
import CliffTab from "./CliffTab";
import MethodTab from "./MethodTab";
import SampleBanner from "./SampleBanner";
import { fyLabel, getMeta, getYears } from "../lib/dataHelpers";
import { TabLayout } from "./ui";

export const TAB_OPTIONS = [
  { id: "budget", label: "Budget impact" },
  { id: "who-gains", label: "Who gains" },
  { id: "cliff", label: "The cliff" },
  { id: "method", label: "Methodology" },
];
export const DEFAULT_TAB = "budget";

// Each tab's sections, for the "On this tab" links (the ids are set in the sections themselves).
const SECTIONS = {
  budget: [
    { id: "at-a-glance", title: "At a glance" },
    { id: "each-year", title: "Each year" },
    { id: "assumptions", title: "Assumptions" },
    { id: "comparisons", title: "Comparisons" },
  ],
  "who-gains": [
    { id: "deciles", title: "By income" },
    { id: "recipients", title: "Families gaining" },
    { id: "nations", title: "By nation" },
  ],
  cliff: [
    { id: "example", title: "One family" },
    { id: "what-changes", title: "What changes" },
  ],
  method: [
    { id: "model", title: "Data and model" },
    { id: "limits", title: "How the limits work" },
    { id: "validation", title: "Validation" },
    { id: "limitations", title: "Limitations" },
  ],
};

const ANNOUNCEMENT_URL = "https://www.conservatives.com/news/conservatives-pledge-to-abolish-absurd-childcare-cliff-edge";
const REPO_URL = "https://github.com/PolicyEngine/uk-childcare-100k-threshold";

function getInitialTab(tabParam) {
  return TAB_OPTIONS.some((t) => t.id === tabParam) ? tabParam : DEFAULT_TAB;
}

/** "Replication code: PolicyEngine/uk-childcare-100k-threshold. Built with PolicyEngine UK X on D." */
export function ReplicationLine({ data }) {
  const meta = getMeta(data);
  return (
    <p data-testid="replication">
      Replication code:{" "}
      <a href={REPO_URL} target="_blank" rel="noreferrer">
        PolicyEngine/uk-childcare-100k-threshold
      </a>
      .{meta ? ` Built with PolicyEngine UK ${meta.policyengine_uk} on ${meta.dataset}.` : ""}
    </p>
  );
}

export function Dashboard({ data }) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState(() => getInitialTab(searchParams.get("tab")));
  const years = getYears(data);
  const period = years ? `${fyLabel(years[0])} to ${fyLabel(years.at(-1))}` : null;

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
        <SampleBanner data={data} />
        <div className="animate-[fadeIn_0.4s_ease-out]">
          <p className="mb-3 text-[1.1rem] leading-relaxed text-slate-700" data-testid="intro">
            Working parents lose the 30 funded hours of childcare in England, and Tax-Free Childcare across the UK, as
            soon as either parent&apos;s adjusted net income goes above £100,000. On 4 October 2026 Conservative leader
            Kemi Badenoch{" "}
            <a href={ANNOUNCEMENT_URL} target="_blank" rel="noreferrer" className="underline">
              pledged
            </a>{" "}
            to remove this limit, funded by cutting civil service jobs. We cost removing it from both schemes with{" "}
            <a href="https://policyengine.org/uk" target="_blank" rel="noreferrer" className="underline">
              PolicyEngine UK
            </a>
            {period ? ` from ${period}` : ""}, and show who gains and how the £100,000 cliff disappears for a family
            near the limit.
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
          {activeTab === "cliff" && <CliffTab data={data} />}
          {activeTab === "method" && <MethodTab data={data} />}
        </TabLayout>

        <footer className="mt-12 border-t border-slate-200 pt-8 text-center text-sm text-slate-500">
          <ReplicationLine data={data} />
        </footer>
      </main>
    </div>
  );
}

export default Dashboard;
