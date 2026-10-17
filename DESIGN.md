# Design System: Signalpost

Single source of truth for both Signalpost interfaces: the static **showcase**
(`src/signalpost/showcase/template.html`) and the local **live console**
(`src/signalpost/console/console.html`). Both declare the tokens below as CSS
custom properties on `:root`. **Light ("Birch") is the default regardless of the OS setting**; the dark set
lives only under `:root[data-theme="dark"]` and is reached through the in-page toggle (remembered locally).

Influences, blended and not copied: Linear (hairlines instead of shadows, one accent,
tight display tracking), IBM Carbon (data-dense tables, semantic support colours,
visible focus), and the restraint of Nordic public-sector registers. No brand marks,
names or palettes from those systems are used.

---

## 1. Visual theme and atmosphere

**"A well-kept public register."** Calm, editorial and exact. Warm birch-paper
canvas, off-black ink, a single fjord-blue accent, and colour that appears only where
it carries meaning (availability state, a link, focus, a negative number).

| Dial | Value | Meaning |
|---|---|---|
| Density | 6 (showcase) / 8 (console) | Daily-app balanced; the console is cockpit-dense |
| Variance | 3 | Predictable grid. This is a verification tool, not a portfolio |
| Motion | 2 | Static and restrained. Motion explains state changes, nothing loops for decoration |

The product promise is **"every fact is one tap from its evidence"**. Visual design
serves that: facts are large and quiet, their source affordance is small, consistent
and always in the same place (right edge of a row, or a numbered citation after a
sentence).

## 2. Colour palette and roles

One warm-grey family for every neutral. Never mix in cool greys.

### Light ("Birch")
| Token | Hex | Role |
|---|---|---|
| `--canvas` | `#F7F6F3` | Page background (warm bone) |
| `--surface` | `#FFFFFF` | Panels, tables, drawer |
| `--surface-2` | `#F1EFEA` | Sunken wells, row hover, inline code, inactive segments |
| `--surface-3` | `#E9E6E0` | Pressed state, skeleton base |
| `--line` | `#E4E1DA` | 1px hairlines: panel borders, row dividers |
| `--line-strong` | `#D2CEC5` | Input borders, axis baselines, focus-adjacent edges |
| `--ink` | `#1C1B19` | Primary text (15.9:1 on canvas) |
| `--ink-2` | `#55524C` | Secondary text, labels (7.2:1) |
| `--ink-3` | `#6E6A63` | Muted metadata, axis labels (5.0:1, still AA) |
| `--accent` | `#285A80` | **Fjord blue.** Links, primary button, focus ring, active nav, chart series (6.8:1) |
| `--accent-hover` | `#1F4A6B` | Hover/pressed accent |
| `--accent-soft` | `#E3ECF3` | Selected row, active tab wash, citation hover |
| `--on-accent` | `#FFFFFF` | Text on accent fill (7.3:1) |

### Dark ("Polar night")
| Token | Hex | Role |
|---|---|---|
| `--canvas` | `#141412` | Page background (never `#000`) |
| `--surface` | `#1B1B19` | Panels |
| `--surface-2` | `#232320` | Wells, hover |
| `--surface-3` | `#2C2C29` | Pressed, skeleton |
| `--line` | `#2E2E2B` | Hairlines |
| `--line-strong` | `#3D3D39` | Inputs, baselines |
| `--ink` | `#EDEBE6` | Primary text (15.5:1) |
| `--ink-2` | `#BDB9B0` | Secondary (9.4:1) |
| `--ink-3` | `#9A968D` | Muted (6.3:1) |
| `--accent` | `#8DB8DC` | Fjord blue, stepped for dark (8.8:1) |
| `--accent-hover` | `#A6C8E5` | Hover |
| `--accent-soft` | `#1F2A33` | Selected wash |
| `--on-accent` | `#10161B` | Text on accent fill |

### Availability states (semantic, reserved)
The six terminal states of the data contract. Each state always ships **icon + label**,
never colour alone. Chip text/background pairs measure 5.4–7.9:1.

| State | Glyph | Light text / soft / fill | Dark text / soft / fill |
|---|---|---|---|
| `available` | `✓` | `#2F6B3A` / `#E7F0E6` / `#3E8A4C` | `#8CCB95` / `#1C2A1E` / `#5DAA69` |
| `not_available` | `–` | `#5F5B54` / `#EEECE7` / `#BDB8AE` | `#B5B0A7` / `#262623` / `#55534D` |
| `ambiguous` | `?` | `#7F5300` / `#F8EED3` / `#B07A10` | `#E3B65C` / `#2E2614` / `#C99A3E` |
| `blocked` | `⊘` | `#984519` / `#F7E6DA` / `#C2662F` | `#E79A6C` / `#2F2119` / `#C77748` |
| `failed` | `✕` | `#A3302C` / `#F8E3E1` / `#C2413B` | `#EE8F88` / `#321D1B` / `#D25A52` |
| `not_applicable` | `∅` | `#625E57` / `#F1EFEA` / hatched `#D2CEC5` | `#A29E95` / `#232320` / hatched `#3D3D39` |

`not_available` and `not_applicable` fills are deliberately recessive (they mean
"nothing to show"); their percentage is always printed as text beside the bar.
`not_applicable` uses a 45° hatch so it never reads as a second grey.

### 2b. Glass layer
Panels float as frosted glass over a fixed, very soft ambient background; nothing else moves.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--glass` | `rgba(255,255,255,.70)` | `rgba(32,33,31,.62)` | Panel fill |
| `--glass-strong` | `rgba(255,255,255,.84)` | `rgba(32,33,31,.82)` | Top bar, drawer, popovers, dialogs |
| `--glass-border` | `rgba(255,255,255,.80)` | `rgba(255,255,255,.09)` | 1px rim light |
| `--glass-shadow` | inset top highlight + `0 10px 30px -14px rgba(31,74,107,.22)` | inset + `0 14px 34px -14px rgba(0,0,0,.65)` | Lift (tinted with fjord blue, never pure black) |
| `--blur` | `saturate(170%) blur(18px)` | same | `backdrop-filter` on panels and fixed layers |
| `--amb-1/2/3` | fjord `rgba(40,90,128,.30)`, teal `rgba(46,140,150,.22)`, sand `rgba(233,190,140,.42)` | dimmed | Four radial blobs on a fixed `body:before`; never on scrolling content |

Rules: text contrast is measured against the *effective* colour (glass over canvas), and every text token still
clears 4.5:1. `prefers-reduced-transparency: reduce` and print fall back to solid `--surface` with no blur.
Large figures (KPI values) may use a subtle ink → ink/accent text gradient; nothing else uses gradients.

### Charts
- Portfolio overview: availability donut (state colours, legend with counts and %), revenue histogram (NOK only;
  excluded companies are counted in the caption), NACE sections and counties as bar lists. Profile: completeness
  ring (families found / 13), workplaces by municipality. Compare: one bar chart per measure, one colour per company
  (`--s1…--s4`, the validated categorical order), **never two currencies on one scale** (values are listed instead).
- Single-series charts use `--accent`. Negative values in a magnitude chart use the
  `failed` fill and carry a minus sign in the label (diverging: blue ↔ red, grey zero line).
- Gridlines `--line`, baseline `--line-strong`, axis text `--ink-3`. Values in ink, never in series colour.
- No dual axes. Revenue, result and equity are **small multiples**, one measure each.

## 3. Typography

No web fonts are loaded: both UIs must open from `file://` with no network. Stacks
favour the platform's best UI face and exclude Inter/Roboto.

| Role | Stack |
|---|---|
| Sans (UI, body, display) | `"SF Pro Text", "SF Pro Display", "Segoe UI Variable Text", "Segoe UI", system-ui, "Helvetica Neue", sans-serif` |
| Mono (org. numbers, hashes, methods, terminal, numbers in dense tables) | `"SF Mono", "Cascadia Mono", "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace` |

| Step | Size / line-height | Weight | Tracking | Use |
|---|---|---|---|---|
| Display | `clamp(30px, 4.2vw, 46px)` / 1.08 | 650 | -0.025em | Overview hero only |
| H1 | `clamp(24px, 3vw, 32px)` / 1.15 | 650 | -0.02em | Page and company titles |
| H2 | 19px / 1.3 | 620 | -0.01em | Section titles |
| H3 | 14px / 1.4 | 600 | 0 | Panel titles (sentence case, not all-caps) |
| Body | 15px / 1.6 | 400 | 0 | Prose, max 68ch |
| UI | 14px / 1.45 | 450–500 | 0 | Tables, controls |
| Small | 13px / 1.45 | 450 | 0 | Metadata |
| Eyebrow | 12px / 1.3 | 600 | +0.06em, uppercase | At most one per panel (section numbers, source class) |
| Figure | 22–28px / 1.1 | 620 | -0.01em | KPI values, `tabular-nums` |

Rules: every number uses `font-variant-numeric: tabular-nums`; headings use
`text-wrap: balance`, prose `text-wrap: pretty`; weights 400/500/600 do the hierarchy,
700 is reserved for nothing.

## 4. Spacing, radius, elevation, z-index

- **4px base.** Scale: `4 8 12 16 20 24 32 48 64`. Panel padding 20px (16px under 600px).
  Section gap 32px desktop, 24px mobile.
- **Radius.** 4px chips and citations, 6px buttons and inputs, 10px panels,
  14px drawer/dialog corners. Never pill-shaped containers or primary buttons; state
  chips may be fully rounded.
- **Elevation.** Depth comes from the glass layer (§2b): translucent fill, rim light and a soft tinted lift.
  Floating layers (drawer, dialog, typeahead, toast) add `--shadow-overlay`:
  light `0 12px 32px -12px rgba(41,36,28,.22)`, dark `0 12px 32px -12px rgba(0,0,0,.6)`.
- **Z-index scale.** `--z-sticky: 10`, `--z-pop: 20`, `--z-scrim: 30`, `--z-drawer: 40`, `--z-toast: 50`.

## 5. Components

- **Top bar.** 56px, sticky, surface at 92% with an 8px backdrop blur and a bottom hairline.
  Brand mark, text nav with an underline indicator for the active route, search,
  language segment (NO/EN), theme menu. Collapses to two rows under 760px; nav scrolls
  horizontally rather than hiding behind a hamburger (5 destinations fit).
- **Buttons.** Primary: accent fill, on-accent text, 6px radius, 40px min height (44px on
  touch). Secondary: surface with `--line-strong` border. Tertiary: text link style.
  Hover shifts background one step; `:active` is `translateY(1px)`. No glows.
- **Inputs.** Label above, help text below in `--ink-3`, error below in `failed` text
  with an icon. 40px min height (44px on touch), `--line-strong` border, accent focus ring.
- **Focus.** `outline: 2px solid var(--accent); outline-offset: 2px` on `:focus-visible`
  for every interactive element. Never removed.
- **Panels.** Surface fill + 1px `--line` border + 10px radius. Used only to group a
  family or a tool. Inside a panel, sub-groups are separated by hairlines or spacing,
  never by another bordered card.
- **State chip.** Glyph + label, 12.5px/600, soft background, state text colour. Compact
  variant (glyph only, 18px square, `aria-label` with the state) for dense grids.
- **Evidence affordances.**
  - *Citation* `[1]` after a sentence: 20px tall, 4px radius, mono numerals, accent text.
  - *Source button* at row end: `Registry · 2026-10-17`, small, hairline border. Same
    position on every row.
  - Both open the **evidence drawer**.
- **Evidence drawer.** Right sheet 480px on desktop, bottom sheet (88dvh, 14px top corners,
  grab handle) under 760px. `role="dialog"`, `aria-modal`, focus trapped, `Esc` closes,
  focus returns to the opener. Content: claim value, family, period, first seen, then one
  block per evidence item: source class eyebrow, highlighted span (value marked with
  `<mark>`), source URL, retrieved, period, method (mono), identity reason, licence,
  full SHA-256 in mono with copy.
- **Tables.** 1px row dividers, no zebra, 40px rows (desktop), sticky header,
  `aria-sort` on sortable headers with a visible arrow. Numbers right-aligned, mono
  tabular. Under 760px rows become stacked cards with `data-label` captions.
- **Meters** (budget, coverage). 8px track in `--surface-2`, fill in accent; ≥70% →
  ambiguous colour + "warning" label, ≥90% → failed colour + "near limit" label.
  `role="meter"` with `aria-valuenow/min/max` and a text value beside it.
- **Coverage bar.** Stacked state segments with 2px surface gaps, a 95% Wilson interval
  drawn as a thin ink whisker over the `available` share, percentage and interval as text.
- **Skeletons.** Shimmer-free blocks in `--surface-3` matching the final layout. No spinners.
- **Empty states.** One sentence on why it is empty and one action that fills it
  (e.g. "Baseline run. Re-run with `--previous` to see changes").
- **Toast.** Bottom centre, ink on canvas inverted, 1.6s, `role="status"`.
- **Keyboard keys.** `<kbd>`: mono 12px, `--surface-2`, 1px `--line-strong`, 4px radius.

## 6. Layout

- Max content width 1240px, 24px side padding (16px under 600px).
- CSS Grid everywhere; asymmetric splits for overview (`1.4fr 1fr`) and profile
  (content + 220px sticky section index on ≥1100px).
- Single column under 760px, no horizontal page scroll; wide tables scroll inside their panel.
- Tap targets ≥44px on coarse pointers (`@media (pointer: coarse)`).
- `min-height: 100dvh`, never `100vh`.

## 7. Motion and interaction

- 150–200ms `cubic-bezier(.2,.7,.2,1)` for hover, drawer and bars. Transform/opacity only.
- Bars grow from their baseline once on first render; nothing loops except the console's
  "running" status dot.
- `prefers-reduced-motion: reduce` disables all transitions and animations.
- Keyboard: `/` focus search, `Esc` close overlays, `g` then `o/c/h/x/m` for routes,
  `?` shortcut sheet. Shortcuts never fire while typing in a field.

## 8. Language and content

- UI labels in English or Norwegian bokmål (toggle, remembered locally). **Data stays as
  sourced**: registry Norwegian values are not translated.
- Numbers keep unit, currency and period. Amounts: `NOK 14.4 bn` / `14,4 mrd. NOK` with the
  exact value in the drawer and in tooltips. Never round away a sign.
- Sentence case. Plain, specific verbs ("Show evidence", "Copy hash"). No exclamation marks.
- Missing is never zero: show the state chip, not `0` or an empty cell.

## 9. Do and don't

**Do**
- Keep colour for meaning. One accent; states only as states.
- Put the evidence affordance in the same place on every row.
- Print the reason next to every non-available state.
- Show abstentions and rejections as proudly as published facts.

**Don't**
- No glows, neon, decorative imagery or gradient fills on marks. Glass only as specified in §2b.
- No emojis. Glyphs are typographic (`✓ – ? ⊘ ✕ ∅ ↗`).
- No Inter/Roboto, no serif in the app UI, no pure black or pure white text on dark.
- No dual-axis charts, no rainbow palettes, no numbers on every bar of a dense chart.
- No external runtime dependencies: no CDN scripts, fonts or images. Optional network
  features (Kartverket geocoding) are opt-in and degrade silently offline.
- No three equal feature cards, no "Elevate/Seamless/Unleash" copy, no fake round numbers.

## 10. Agent prompt guide

When generating or editing a Signalpost screen:

1. Start from the tokens in §2 as CSS custom properties; never hard-code a hex in a rule.
2. Lay out with CSS Grid inside a 1240px container; collapse to one column under 760px.
3. Every displayed fact must render through the shared claim renderer so it gets a source
   button or citation that opens the evidence drawer.
4. Represent availability with the state chip (glyph + label) and its reason.
5. Numbers: tabular, unit + currency + period preserved, exact value one tap away.
6. Check: light and dark, 375px width, keyboard-only path, `prefers-reduced-motion`,
   `node eval/ui_check.cjs` reports `errors: []`.
