import type { Metadata } from "next";
import Link from "next/link";
import "@fontsource/dm-sans/latin-400.css";
import "@fontsource/dm-sans/latin-500.css";
import "@fontsource/dm-sans/latin-700.css";
import "@fontsource/instrument-serif/latin-400.css";
import "@fontsource/instrument-serif/latin-400-italic.css";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "Kairos — Find the step that changed the outcome",
    template: "%s — Kairos",
  },
  description:
    "Inspect captured context, investigate agent failures, and test repairs against an independent grader. A full-stack engineering project with inspectable evidence.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <a className="skip" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <Link className="wordmark" href="/" aria-label="Kairos home">
            <span className="brand-symbol" aria-hidden="true">
              κ
            </span>
            kairos<span className="edition">FIELD NOTES / 001</span>
          </Link>
          <nav aria-label="Main navigation">
            <Link href="/incidents">Incidents</Link>
            <Link href="/engineering">Engineering</Link>
            <Link href="/evidence">Evidence</Link>
            <Link href="/docs">
              Docs <span aria-hidden="true">↗</span>
            </Link>
          </nav>
        </header>
        <main id="main">{children}</main>
        <footer className="site-footer">
          <Link className="footer-mark" href="/">
            kairos.
          </Link>
          <p>
            Built to make agent behavior inspectable.
            <br />
            <span>Controlled data. Real executions. Explicit limits.</span>
          </p>
          <Link href="/docs#guarantees">Read the guarantees ↗</Link>
        </footer>
      </body>
    </html>
  );
}
