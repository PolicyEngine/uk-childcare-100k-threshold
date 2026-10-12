import { isNum } from "./dataHelpers";

// Every formatter throws on a missing or non-finite value: the results file is validated before the build, so a bad
// value reaching a formatter is a bug, and it must fail rather than print "NaN", "£bn" or a placeholder.

function check(value, name) {
  if (!isNum(value)) throw new TypeError(`${name}: ${JSON.stringify(value)} is not a number`);
}

export function formatCurrency(value) {
  check(value, "formatCurrency");
  const rounded = Math.round(value);
  const sign = rounded < 0 ? "-" : "";
  return `${sign}£${Math.abs(rounded).toLocaleString("en-GB")}`;
}

export function formatBn(value, digits = 1) {
  check(value, "formatBn");
  const fixed = Math.abs(value).toFixed(digits);
  const sign = value < 0 && Number(fixed) !== 0 ? "-" : "";
  return `${sign}£${fixed}bn`;
}

export function formatPct(value, digits = 1) {
  check(value, "formatPct");
  // No "-0.0%": a small negative that rounds to zero prints as zero.
  const v = Number(Math.abs(value).toFixed(digits)) === 0 ? 0 : value;
  return `${v.toFixed(digits)}%`;
}

export function formatCount(value) {
  check(value, "formatCount");
  return Math.round(value).toLocaleString("en-GB");
}

/** A count rounded to the nearest thousand: 94,560 -> "95,000". */
export function formatThousands(value) {
  check(value, "formatThousands");
  return (Math.round(value / 1000) * 1000).toLocaleString("en-GB");
}

/** £bn shown in £m below £0.1bn, so a small change is not rounded away: 0.003 -> "£3m", 0.55 -> "£0.55bn". */
export function formatMoneyBn(value) {
  check(value, "formatMoneyBn");
  if (Math.abs(value) >= 0.1) return formatBn(value, 2);
  const m = Math.round(value * 1000);
  return `${m < 0 ? "-" : ""}£${Math.abs(m).toLocaleString("en-GB")}m`;
}
