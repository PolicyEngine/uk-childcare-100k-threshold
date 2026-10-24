import { basePath as BASE_PATH } from "../lib/basePath.json";

// PolicyEngine site footer, rendered by the dashboard itself. Multizone
// rewrites proxy this app under policyengine.org/uk/childcare-100k-threshold but do
// not inject the parent site shell, so the footer links mirror the
// policyengine.org site footer.
const FOOTER_LINKS = [
  { label: "About us", href: "https://policyengine.org/uk/team" },
  { label: "Donate", href: "https://policyengine.org/uk/donate" },
  { label: "Developer tools", href: "https://policyengine.org/uk/dev-tools" },
  { label: "Privacy policy", href: "https://policyengine.org/uk/privacy" },
  {
    label: "Terms and conditions",
    href: "https://policyengine.org/uk/terms",
  },
];

export default function PolicyEngineFooter() {
  return (
    <footer
      className="relative z-[1] w-full"
      style={{
        background:
          "linear-gradient(to right, var(--pe-color-primary-800, #234E52), var(--pe-color-primary-600, #2C7A7B))",
      }}
    >
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-8 gap-y-2.5 px-6 py-4 md:px-8">
        <a
          href="https://policyengine.org/uk"
          aria-label="PolicyEngine UK home"
          className="w-fit shrink-0"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`${BASE_PATH}/assets/logos/policyengine-white.svg`}
            alt="PolicyEngine"
            className="h-6 w-auto"
          />
        </a>
        <nav
          aria-label="PolicyEngine site footer"
          className="order-last flex w-full flex-wrap gap-x-5 gap-y-1 md:order-none md:w-auto"
        >
          {FOOTER_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-[14px] font-medium text-white no-underline transition-opacity hover:opacity-80"
            >
              {link.label}
            </a>
          ))}
        </nav>
        <p className="m-0 ml-auto text-[13px] text-white/70">
          &copy; {new Date().getFullYear()} PolicyEngine
        </p>
      </div>
    </footer>
  );
}
