# Design System: Kairos for Agents
**Project ID:** `projects/kairos-agent-harness`

## 1. Visual Theme & Atmosphere
Utilitarian, High-Density Systems Workbench. The atmosphere rejects generic "AI SaaS" templates (no purple gradient blobs, no floating cartoon robot mascots, no hollow marketing superlatives). The interface communicates absolute cryptographic certainty, spatial depth, and high-frequency systems observability. It is inspired by mission-critical avionics dashboards, compiler debuggers (LLVM/PTX inspection tools), and modern high-throughput distributed tracing engines (Jaeger/Tempo).

Every surface feels physical, weightless, and layered: deep obsidian slate foundations supporting semi-translucent glass panels with whisper-soft diffused drop shadows and crisp 1px borders that capture light without glare.

## 2. Color Palette & Roles

* **Obsidian Canvas (`#09090b`):** The primary infinite background, deep matte black-zinc that eliminates eye strain and grounds high-contrast monospace telemetry.
* **Elevated Surface Layer (`#121214`):** Base container fill for panels, toolbars, and inspection cards.
* **Translucent Glass Panel (`rgba(18, 18, 20, 0.78)`):** Layered floating glass with `backdrop-filter: blur(16px)` for floating HUDs, sticky scrubbers, and modal workbenches.
* **Crisp Perimeter Border (`#27272a`):** Ultra-thin 1px border establishing precise architectural separation.
* **Subtle Structural Border (`#3f3f46`):** Highlight border for interactive elements, hover states, and active cards.
* **Pure Signal White (`#f4f4f5`):** Primary text, numbers, and active metrics with maximum legibility.
* **Muted Telemetry Zinc (`#a1a1aa`):** Secondary metadata, labels, timestamps, and architectural descriptions.
* **Subtle Code Zinc (`#71717a`):** Monospace line numbers, parent hash pointers, and table column types.
* **Verified Signal Emerald (`#10b981`):** Indicates 100% deterministic invariant verification pass, intact cryptographic chains, and 0.00% ring buffer drops.
* **Divergence Warning Amber (`#f59e0b`):** Pinpoints the exact step $k$ where candidate execution diverged from the baseline reference.
* **Invariant Violation Crimson (`#ef4444`):** Flags schema hallucinations, unauthorized state mutations, unhandled policy exceptions, and statistical CI regression gates.
* **Telemetry Electric Indigo (`#6366f1`):** Highlights Go ring buffer throughput, content-addressed deduplication ratios, and active SQL token meters.

## 3. Typography Rules

* **Display & Navigation:** Geist Sans / Inter (`font-sans`), weights 500 (medium) and 600 (semibold). Strict negative letter-spacing (`tracking-tight`, `-0.02em` to `-0.03em`) for a modern, compact, authoritative silhouette.
* **Code & Telemetry Data:** Geist Mono / JetBrains Mono (`font-mono`), weight 400 (regular) and 500 (medium). Used exclusively for SHA-256 hashes, timestamps, SQL queries, token counts, JSON payloads, and $p$-values. Zero decorative script fonts.
* **Hierarchy:**
  - Micro Eyebrow: `10px` / `11px`, all-caps, `tracking-wider` (`0.08em`), muted zinc (`#71717a`).
  - Panel Header: `14px` / `15px`, semibold, pure white (`#f4f4f5`).
  - Quantitative Metric: `20px` to `24px`, bold monospace.
  - Body Prose: `13px` / `14px`, regular, line-height 1.6, muted zinc (`#a1a1aa`).

## 4. Component Stylings

* **Action Buttons:**
  - Primary: Squared with subtle corner rounding (`rounded-md`, 6px), crisp border (`border-[#3f3f46]`), background (`#18181b`), pure white text, hover background (`#27272a`), 0.2s ease transition. Zero pill-shaped rainbow gradient buttons.
  - Signal Action (Fork / Run): Emerald accent border (`border-emerald-600`), deep emerald background (`#064e3b` or `#065f46`), white text, instant responsiveness.
* **Cards & Containers:**
  - Rounded corners (`rounded-lg`, 8px).
  - Background fill: `#121214` with subtle linear gradient `linear-gradient(180deg, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0) 100%)`.
  - Shadows: Layered, whisper-soft drop shadows (`box-shadow: 0 4px 20px -2px rgba(0,0,0,0.5)`).
  - Hover state: 3D perspective tilt (`perspective: 1000px`, `transform: translateY(-2px) rotateX(1deg) rotateY(-1deg)`).
* **Input Fields & Code Editors:**
  - Background `#0c0c0e`, border `#27272a`, focus outline `1px solid #6366f1`.
  - Monospace text with syntax color differentiation (SQL keywords, table identifiers, numeric literals).
* **Status Badges:**
  - Strict rectangular chips (`rounded`, 4px), micro text (`10px` or `11px`), monospace font. No rounded pills or pastel emoji tags.
  - `[PASS]`: Emerald text with subtle emerald background (`rgba(16, 185, 129, 0.1)`), border `rgba(16, 185, 129, 0.3)`.
  - `[FAIL]`: Crimson text with subtle crimson background (`rgba(239, 68, 68, 0.1)`), border `rgba(239, 68, 68, 0.3)`.
  - `[DIVERGED]`: Amber text with subtle amber background (`rgba(245, 158, 11, 0.1)`), border `rgba(245, 158, 11, 0.3)`.

## 5. Layout Principles

* **Density:** High information density. Whitespace is purposeful and structured, never cavernous or wasteful.
* **Visual Rhythm:** 8px baseline grid (padding `p-2`, `p-4`, `p-6`, gaps `gap-2`, `gap-4`, `gap-6`).
* **Z-Axis Hierarchy:**
  - Base: Canvas `#09090b` (Z-0)
  - Layout Grid: Containers `#121214` with `#27272a` borders (Z-10)
  - Sticky Controls: Glass Scrubber HUD `rgba(18,18,20,0.85)` (Z-20)
  - Interactive Overlays: Time-Travel Fork Modal & Invariant Inspect Modals (Z-50)
* **Zero Emojis Policy:** Strictly zero unicode emojis across all UI surfaces, headers, logs, tooltips, and documentation. All status representations use SVG vectors or typed alphanumeric badges.
