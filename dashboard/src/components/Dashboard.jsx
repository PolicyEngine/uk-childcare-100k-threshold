"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import LandingTab from "./LandingTab";
import WhoGainsTab from "./WhoGainsTab";
import CliffTab from "./CliffTab";
import MethodTab from "./MethodTab";
import { fyLabel, getYears } from "../lib/dataHelpers";
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
    { id: "sensitivities", title: "What moves the cost" },
    { id: "comparisons", title: "Against the £0.7bn" },
    { id: "thirty-hours", title: "Inside the 30 hours" },
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
    { id: "take-up", title: "Take-up" },
    { id: "validation", title: "Validation" },
    { id: "limitations", title: "Limitations" },
  ],
};

const ANNOUNCEMENT_URL = "https://www.conservatives.com/news/conservatives-pledge-to-abolish-absurd-childcare-cliff-edge";
const REPO_URL = "https://github.com/PolicyEngine/uk-childcare-100k-threshold";

function getInitialTab(tabParam) {
  return TAB_OPTIONS.some((t) => t.id === tabParam) ? tabParam : DEFAULT_TAB;
}

/** "Replication code: PolicyEngine/uk-childcare-100k-threshold." */
export function ReplicationLine() {
  return (
    <p data-testid="replication">
      Replication code:{" "}
      <a href={REPO_URL} target="_blank" rel="noreferrer">
        PolicyEngine/uk-childcare-100k-threshold
      </a>
      . Model and data versions are on the Methodology tab.
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
            to remove this limit, paid for by savings elsewhere in public spending. This dashboard costs removing it from
            both schemes with{" "}
            <a href="https://policyengine.org/uk" target="_blank" rel="noreferrer" className="underline">
              PolicyEngine UK
            </a>
            {` from ${period}`}. The four tabs cover:
          </p>
          <ul className="mb-3 list-disc space-y-2 pl-6 text-base leading-7 text-slate-700" data-testid="tab-guide">
            <li>
              <strong>Budget impact</strong>: what removing the limit adds to government spending each year, split
              between the 30 hours and Tax-Free Childcare, with a low and a high estimate around it. It also shows which
              uncertain assumptions move the cost most, and how our figure compares with the £0.7bn reported for the
              pledge.
            </li>
            <li>
              <strong>Who gains</strong>: only families with a parent above £100,000 gain, so this tab shows where they
              sit in the income distribution, how many families and children gain from each scheme, and how the gains
              split across England, Scotland, Wales and Northern Ireland.
            </li>
            <li>
              <strong>The cliff</strong>: one example family&apos;s net income as a parent&apos;s earnings rise past
              £100,000, with and without the limit. It explains why earning one pound more can leave the family worse
              off today, and how removing the limit smooths that drop.
            </li>
            <li>
              <strong>Methodology</strong>: the data and model behind every figure, how the two income limits work,
              the take-up assumptions for newly eligible families, how the baseline compares with official statistics,
              and what the costing does not capture.
            </li>
          </ul>
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
          <ReplicationLine />
        </footer>
      </main>
    </div>
  );
}

export default Dashboard;
