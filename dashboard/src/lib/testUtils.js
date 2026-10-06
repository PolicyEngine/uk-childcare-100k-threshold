import { render } from "@testing-library/react";

import fileData from "../../public/data/results.json";

// The committed results file. Every test reads its numbers from the file, so the same tests pass on any valid
// results file.
export const realData = fileData;

/** Text a user would see, whitespace collapsed. */
export function textOf(element) {
  const { container, unmount } = render(element);
  const text = container.textContent.replace(/\s+/g, " ");
  unmount();
  return text;
}

/** Deep copy of the results with one dotted path set (or deleted). */
export function mutate(path, value, { remove = false } = {}) {
  const copy = structuredClone(fileData);
  const parts = path.split(".");
  let node = copy;
  for (const part of parts.slice(0, -1)) node = node[part];
  const last = parts[parts.length - 1];
  if (remove) delete node[last];
  else node[last] = value;
  return copy;
}

// Values a stale or partial results file could carry in place of a number.
export const BAD_VALUES = [undefined, null, "x", Number.NaN];

// Text that must never reach the page, whatever the data.
export const BROKEN_TEXT = /NaN|undefined|Infinity|\[object|£-?\.|(of|is|to|at|and) £bn/;

export const fy = (year) => `${year}-${String((year + 1) % 100).padStart(2, "0")}`;
export const bn = (v, d = 2) => `${v < 0 && Number(Math.abs(v).toFixed(d)) !== 0 ? "-" : ""}£${Math.abs(v).toFixed(d)}bn`;
export const gbp = (v) => `${Math.round(v) < 0 ? "-" : ""}£${Math.abs(Math.round(v)).toLocaleString("en-GB")}`;
