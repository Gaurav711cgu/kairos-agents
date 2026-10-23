import type { Metadata } from "next";
import Link from "next/link";
import { isRecordedEvidence } from "@/lib/evidence-mode";
import "@fontsource/dm-sans/latin-400.css";
import "@fontsource/dm-sans/latin-500.css";
import "@fontsource/dm-sans/latin-700.css";
import "@fontsource/instrument-serif/latin-400.css";
import "@fontsource/instrument-serif/latin-400-italic.css";
import "./globals.css";
import "./investigations.css";
// Runtime mode also controls static informational pages; never reuse a build-time label.
export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: {
    default: "Kairos — Inspect the investigation",
    template: "%s — Kairos",
  },
  description:
    "Inspect captured context, investigate agent failures, and test repairs against an independent grader. A full-stack engineering project with inspectable evidence.",
  openGraph: {
    title: "Kairos — Autonomous Code-Repair & Graph-RAG Verification Dashboard",
    description:
      "Inspect Kairos investigation records, 14B QLoRA training artifacts and repository-context experiments with their observed checks and scope.",
    type: "website",
    siteName: "Kairos",
  },
  twitter: {
    card: "summary_large_image",
    title: "Kairos — Autonomous Code-Repair & Graph-RAG Verification Dashboard",
    description:
      "Inspect Kairos investigation records, 14B QLoRA training artifacts and repository-context experiments with their observed checks and scope.",
  },
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <a className="skip" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <Link className="wordmark" href="/" aria-label="Kairos home">
            <span className="brand-symbol" aria-hidden="true">
              κ
            </span>
            Kairos<span className="edition">Build 007</span>
          </Link>
          <nav aria-label="Main navigation">
            <Link href="/how-it-works">Start here</Link>
            <Link href="/benchmark">Benchmark</Link>
            <Link href="/investigations">Investigations</Link>
            <Link href="/repair-comparison">Comparison</Link>
            <Link href="/engineering">Engineering</Link>
            <Link href="/advancement">Repair results</Link>
            <Link href="/capacity">Capacity</Link>
            <Link href="/history">History</Link>
            <Link href="/workbench">Workbench</Link>
            <Link href="/docs">Docs</Link>
          </nav>
        </header>
        <main id="main">{isRecordedEvidence() && <aside className="recorded-mode-note" aria-label="Evidence mode"><span>Evidence viewer · Original investigation captures</span><Link href="/workbench">Live workbench setup</Link></aside>}{children}</main>
        <footer className="site-footer">
          <Link className="footer-mark" href="/">
            Kairos
          </Link>
          <p>
            Repository investigations, source changes and independent checks.
            <br />
            <span>
              Pinned source, proposed changes and captured verification results.
            </span>
          </p>
          <Link href="/#guarantees">Explore the engineering</Link>
        </footer>
      </body>
    </html>
  );
}
