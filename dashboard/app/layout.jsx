import PolicyEngineFooter from "../src/components/PolicyEngineFooter";
import PolicyEngineHeader from "../src/components/PolicyEngineHeader";

import "./globals.css";

export const metadata = {
  title: "Scrapping the £100,000 childcare cliff edge | PolicyEngine",
  description:
    "What removing the £100,000 income limit on the 30 funded hours and Tax-Free Childcare would cost, who would gain, and how it removes the childcare cliff, from PolicyEngine UK microsimulation.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <PolicyEngineHeader />
        {children}
        <PolicyEngineFooter />
      </body>
    </html>
  );
}
