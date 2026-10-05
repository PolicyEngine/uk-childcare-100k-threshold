import { isSample } from "../lib/dataHelpers";

/**
 * Shown whenever the results file carries `"meta": {"sample": true}`. The
 * analysis pipeline's real output omits the key, so the banner disappears
 * when the real results.json is copied in.
 */
export default function SampleBanner({ data }) {
  if (!isSample(data)) return null;
  return (
    <div role="alert" className="note-card mb-6 rounded-xl px-5 py-4" data-testid="sample-banner">
      <p className="note-eyebrow eyebrow">Sample data — not results</p>
      <p className="note-body mt-1 text-sm">
        Every figure on this page is a placeholder used to build the dashboard. Do not quote or
        use any of them.
      </p>
    </div>
  );
}
