---
name: Risk Miner
description: Pamięć inwestycji — a control room for how public water and sewage investments really ended.
colors:
  reservoir-teal: "#0f7c8c"
  reservoir-teal-deep: "#0c6774"
  reservoir-teal-wash: "#e3f3f5"
  main-line-navy: "#16324f"
  link-navy: "#1f4670"
  night-network: "#0f2438"
  flow-cyan: "#7fd6e0"
  junction-amber: "#f2b45a"
  desk-mist: "#f4f6f9"
  sheet-white: "#ffffff"
  ink: "#1b2430"
  slate-muted: "#5d6b7c"
  hairline: "#dde3ea"
  soft-fill: "#eef2f6"
  ok-green: "#1f7a4d"
  ok-wash: "#e5f4ec"
  warn-ochre: "#a15c00"
  warn-wash: "#fff3e0"
  bad-red: "#b42318"
  bad-wash: "#fdecea"
  info-blue: "#3557a0"
  info-wash: "#e9effb"
typography:
  display:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, Ubuntu, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "31px"
    fontWeight: 750
    lineHeight: 1.18
    letterSpacing: "-0.6px"
  headline:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, Ubuntu, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.3
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, Ubuntu, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, Ubuntu, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, Ubuntu, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.4
  eyebrow:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, Ubuntu, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    letterSpacing: "0.5px"
  metric:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, Ubuntu, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "26px"
    fontWeight: 700
    lineHeight: 1.1
    fontFeature: "'tnum'"
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "12px"
rounded:
  xs: "6px"
  sm: "8px"
  md: "10px"
  lg: "12px"
  xl: "14px"
  hero: "18px"
  pill: "999px"
spacing:
  xxs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "22px"
  xl: "28px"
components:
  button-primary:
    backgroundColor: "{colors.reservoir-teal}"
    textColor: "{colors.sheet-white}"
    rounded: "{rounded.sm}"
    padding: "7px 12px"
  button-primary-hover:
    backgroundColor: "{colors.reservoir-teal-deep}"
  button-secondary:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "7px 12px"
  button-approve:
    backgroundColor: "{colors.ok-green}"
    textColor: "{colors.sheet-white}"
    rounded: "{rounded.sm}"
    padding: "7px 12px"
  button-reject:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.bad-red}"
    rounded: "{rounded.sm}"
    padding: "7px 12px"
  sidebar-cta:
    backgroundColor: "{colors.flow-cyan}"
    textColor: "{colors.night-network}"
    rounded: "{rounded.md}"
    padding: "11px 13px"
  card:
    backgroundColor: "{colors.sheet-white}"
    rounded: "{rounded.md}"
    padding: "16px"
  input:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.ink}"
    rounded: "7px"
    padding: "7px 9px"
  pill-ok:
    backgroundColor: "{colors.ok-wash}"
    textColor: "{colors.ok-green}"
    rounded: "{rounded.pill}"
    padding: "1px 8px"
  pill-warn:
    backgroundColor: "{colors.warn-wash}"
    textColor: "{colors.warn-ochre}"
    rounded: "{rounded.pill}"
    padding: "1px 8px"
  pill-bad:
    backgroundColor: "{colors.bad-wash}"
    textColor: "{colors.bad-red}"
    rounded: "{rounded.pill}"
    padding: "1px 8px"
  badge:
    backgroundColor: "{colors.junction-amber}"
    textColor: "#2a1800"
    rounded: "7px"
    padding: "1px 7px"
  hint:
    backgroundColor: "{colors.info-wash}"
    textColor: "#24407a"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
---

# Design System: Risk Miner

## Overview

**Creative North Star: "The Utility Control Room"**

Risk Miner is laid out like the control room of a water utility. The dark sidebar is the network schematic: a single pipe runs down each navigation group, every destination is a junction node on it, and the active page lights up with flow cyan. The workspace to its right is the control desk, a calm, light surface of white sheets where every reading carries a gauge (P50/P80/P90, k of n, % confidence) and a source you can follow. The schematic sets the identity; the desk does the work.

The desk's tone is **warm and guiding**. Its users are procurement, investment and legal specialists, not statisticians, so every view leads with a plain-Polish answer ("Odpowiedź w 30 sekund", meaning "the answer in 30 seconds"; story cards; "co zrobić przed ogłoszeniem przetargu", meaning "what to do before announcing the tender") and keeps the full evidence one click away. Density is high where comparison matters (tables, the change library, review queues) and generous where a decision is made (hero, verdict tiles, the funding-risk percentage). Colour almost always carries meaning: status, the evidence layer, or flow. It is not decoration.

The one confirmed anti-reference is **government-form greyness**: walls of identical grey fields with no hierarchy, no explanation and no voice. Risk Miner serves the public sector without looking like a form.

**Key Characteristics:**
- A dark network sidebar (night network, flow cyan, junction amber) against a light misty desk.
- Reservoir teal is the single action colour on the desk.
- A traffic-light status vocabulary, always as a soft wash plus a strong text colour, never as solid blocks.
- Three evidence layers (A: source data, B: calculations, C: conclusions), each with its own colour.
- Headline numbers in large type with tabular figures. Plain-language explanations sit next to every number.
- The system font stack, with weights from 400 to 800 doing the hierarchy work.

## Colors

The palette is a utility network at night against a daylight desk. Its saturated hues are reserved for action, status and evidence.

### Primary
- **Reservoir Teal** (`reservoir-teal`): the one action colour on the desk. Primary buttons, active tab underlines, progress bars, the calculation layer (B), the story card's left edge, and the eyebrow labels. Its deep variant is the hover state, and its wash is the selected-row and drop-zone highlight.
- **Main Line Navy** (`main-line-navy`): authority without alarm. Headline numbers (KPIs, flow counts, verdict tiles), hero headings, the verdict's top edge, the median line in range bars, and toasts. **Link Navy** (`link-navy`) is used for inline links and `<details>` summaries.

### Secondary
- **Night Network** (`night-network`): the sidebar's ground and the logo tile. Never used as a desk surface.
- **Flow Cyan** (`flow-cyan`): water in the pipes. The active nav node, the "Analizuj nową inwestycję" CTA, the pipe line (at 22% alpha), the database fill bar, and the command-palette pulse. It appears only on Night Network, where it has contrast; it is never text on white.

### Tertiary
- **Junction Amber** (`junction-amber`): attention inside the network. Review and monitoring count badges, the expert avatar, and the sidebar focus ring. Its text partner is the near-black `#2a1800`.

### Neutral
- **Desk Mist** (`desk-mist`): the page ground behind the sheets.
- **Sheet White** (`sheet-white`): cards, layers, the hero, modals and tables.
- **Ink** (`ink`): body text.
- **Slate Muted** (`slate-muted`): secondary text, labels, table headers and units.
- **Hairline** (`hairline`): every 1px border and table rule.
- **Soft Fill** (`soft-fill`): track backgrounds (bars, ranges) and the grey pill.

### Status and evidence
- **OK Green / Warn Ochre / Bad Red / Info Blue**, each paired with its wash. They are used for pills, flags (`wysoki` / `podwyższony` / `do sprawdzenia`, meaning high / elevated / to check), verdict tiles, the big percentage block, and expert-decision edges.
- **Evidence layers:** A, source data = info blue top edge; B, calculations = reservoir teal top edge; C, conclusions = warn ochre top edge.

### Named Rules
**The Wash-and-Ink Rule.** Status is shown as a soft wash with strong same-hue text and a tinted border, for example Bad Wash ground, Bad Red text, border `#f3c5c0`. Solid status fills are reserved for decisive action buttons (approve).

**The Water Stays in the Pipes Rule.** Flow Cyan and Junction Amber live on the Night Network sidebar. On the desk, action is Reservoir Teal and emphasis is Main Line Navy.

**The Graded Risk Rule.** Risk severity always uses the full scale (ok, warn, bad, info, grey). Red is for the specific finding that is high, such as the hero's key number or a cost overrun, never for a whole screen.

## Typography

**Display Font:** system-ui (with -apple-system, Segoe UI, Roboto, Ubuntu, Helvetica Neue, Arial)
**Body Font:** the same stack
**Label/Mono Font:** ui-monospace (with SFMono-Regular, Menlo, Consolas), only for codes and logs

**Character:** a single native sans that reads as a dependable instrument on every government laptop. Hierarchy comes from weight (400 to 800) and size, not from a second family. Numbers always use tabular figures.

### Hierarchy
- **Display** (750, 31px, line-height 1.18, -0.6px tracking, max 20ch): the dashboard hero question, in Main Line Navy. The empty-state hero goes up to 36px.
- **Headline** (700, 22px): page titles (`h1`), with a muted 14px subtitle under them.
- **Title** (700, 17px; verdict 20px; h3 15px): section heads inside a page.
- **Body** (400, 14px, line-height 1.5): everything else. Story and change texts go up to 14.5–15px at line-height 1.55–1.6 and are capped at 58–110ch.
- **Label** (600, 12px, Slate Muted): field labels, table headers and tile labels.
- **Eyebrow** (700, 11px, 0.5px tracking, uppercase, Reservoir Teal): the kicker above a verdict or a section. The evidence-layer tags use the same form.
- **Metric** (700–800, 26px; verdict 19px; the funding-risk percentage 40px/800): headline numbers, always tabular.

### Named Rules
**The Number-with-a-Sentence Rule.** A large figure never stands alone. It sits with a label above it and a plain-language basis below ("16 z 22 umów", "P80, n_eff = 9").

## Layout

- **Frame:** a two-column app frame. The sidebar is a fixed 268px column, sticky at full height. The main workspace is capped at 1400px with 22px/28px padding.
- **Rail mode:** the sidebar collapses to a 76px icon rail with `[`. Labels, hints and badges hide; the active item becomes a 3px inset cyan edge.
- **Breakpoints:** at 1100px the sidebar narrows to 236px, 4- and 6-column grids drop to 2 columns, 3-column grids and the hero and map splits stack, and the 900px step merges into one column. At 900px the sidebar becomes a static top block and the pipe and nodes disappear.
- **Grid:** content uses simple equal-column grids (2, 3, 4 or 6 columns, 14px gap) and auto-fit tiles (min 200px).
- **Rhythm:** 4, 8, 12, 14, 16, 22 and 28px. Cards pad 16px, hero blocks 28–30px.
- **Dashboard order:** answer first. The hero (question, number, chart) comes first, then the data-flow strip (import → notices → contracts → changes), then the map and the lists.

## Elevation & Depth

The desk is a **lightly lifted sheet system**. Every sheet (card, layer, hero, story, verdict, flow strip) sits 1–3px off the mist on one soft ambient shadow plus a hairline border, so depth comes from border and tone first and shadow second. Real elevation is reserved for things that float above the work: the modal, the command palette and the chart tooltip. The sidebar is flat.

### Shadow Vocabulary
- **Sheet** (`box-shadow: 0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.08)`): all resting cards and blocks.
- **Tooltip** (`box-shadow: 0 8px 24px rgba(16,32,52,.16)`): chart tooltips.
- **Modal** (`box-shadow: 0 20px 60px rgba(0,0,0,.25)`): dialogs, over a `rgba(10,20,35,.45)` scrim.
- **Palette** (`box-shadow: 0 30px 80px rgba(0,0,0,.35)`): the command palette, over a `rgba(8,20,33,.55)` scrim with a 3px blur.

### Named Rules
**The Floating-Only-When-Floating Rule.** Shadows heavier than Sheet belong only to layers that sit above the page (modal, palette, tooltip). Never lift a card to make it look important; use an edge colour or an eyebrow instead.

## Shapes

The shapes are friendly but engineered. Radius grows with the size of the container: 6px for small buttons, 7–8px for inputs, buttons and tree nodes, 10px for cards (`--r`), 12–14px for stories, the verdict, the flow strip and the palette, and 18px for the hero. Status pills are fully rounded. **Coloured edges** are the recurring signature: a 4–5px top edge on evidence layers and verdicts, a 4–5px left edge on review events and story cards, and a 3px left rule on quotes. The pipe-and-node motif (a 2px vertical line with 10px ring nodes) belongs to the sidebar alone.

## Components

### Buttons
- **Shape:** gently rounded (8px; small 6px; big 10px with 11px × 18px padding at 15px).
- **Primary:** Reservoir Teal with white text, weight 500. Hover deepens to Reservoir Teal Deep.
- **Secondary:** white with a Hairline border and Ink text. Hover tints the border to `#b9c5d3` and the background to `#f9fbfd`.
- **Approve / Reject:** approve is solid OK Green; reject is white with Bad Red text and a `#e6b3ae` border, so destructive is quieter than constructive.
- **Disabled:** 50% opacity.

### Pills (status chips)
- **Style:** fully rounded, 11.5px weight 600, wash background with strong same-hue text (ok, warn, bad, info, grey, accent).
- **Use:** risk level, link confidence, notice type, decision state. They are not interactive.

### Cards / Containers
- **Corner Style:** 10px.
- **Background:** Sheet White on Desk Mist.
- **Shadow Strategy:** Sheet (see Elevation).
- **Border:** 1px Hairline.
- **Internal Padding:** 16px.

### Inputs / Fields
- **Style:** 1px Hairline, 7px radius, 7px × 9px padding, white, inheriting the body font. Labels sit above in 12px Slate Muted weight 500.
- **Drop zone:** a 2px dashed `#b8c7d6` border on `#fbfcfe`. On hover it turns to a Reservoir Teal border on Teal Wash.

### Navigation
- **Sidebar:** Night Network ground. Each group has a 12px muted caption and a pipe line, with items as junction nodes. Each item shows an icon, a 14px/550 title and an 11.5px hint line ("wnioski z całej bazy", meaning "lessons from the whole base"). Hover gives a 6% white wash. Active gives a 12% cyan wash, a white title, a cyan icon, and a filled cyan node with a 4px halo. Focus is a 2px Junction Amber outline. Navigating pulses the node once (0.7s), the menu's only animation.
- **Tabs:** text buttons on a hairline. The active tab gets a Main Line Navy label at weight 600 and a 2px Reservoir Teal underline.
- **Command palette (⌘K):** a 640px white sheet. Results show a kind chip (akcja / projekt, meaning action / project), a two-line title and meta, and a teal-wash selection.

### Evidence Layers (signature)
White blocks with a 4px top edge and an uppercase tag: **A. Dane źródłowe** (source data; info blue), **B. Obliczenia** (calculations; reservoir teal), **C. Wnioski** (conclusions; warn ochre). LLM narrative is labelled separately. This is how the product shows the difference between data, calculation and conclusion.

### Verdict and Answer Tiles (signature)
A 14px-radius sheet with a 5px Main Line Navy top edge, an eyebrow and a 20px title, holding auto-fit tiles. Each tile has a label, a 19px bold value and a muted basis line, tinted ok, warn, bad or grey. The **big percentage block** (40px/800 number with a sentence beside it, in a status wash) is reserved for the single most consequential risk, such as losing the grant.

### Story Card
A white card with a 5px Reservoir Teal left edge and 15px/1.6 prose: a project's history told in three sentences. It is the warmest component and the model for guiding copy.

### Review Event
A 9px-radius sheet with a 4px left edge for its state: approved or edited is OK Green, proposed is amber `#e8a33d`, and rejected is grey at 65% opacity. Approve, edit and reject actions sit inline.

## Do's and Don'ts

### Do:
- **Do** lead every view with the plain-language answer, then the numbers, then the evidence trail (verdict, then layers, then sources).
- **Do** pair every headline number with its basis in Slate Muted ("k z n", n_eff, P80 interval).
- **Do** use the Wash-and-Ink treatment for status, with tinted borders: ok `#bfe3cf`, warn `#f3d6a8`, bad `#f3c5c0`, info `#c9d6f2`.
- **Do** keep Reservoir Teal as the only action colour on the desk, and Flow Cyan and Junction Amber inside the sidebar.
- **Do** use tabular figures (`font-variant-numeric: tabular-nums`) for every number in tables, tiles and lists.
- **Do** add a short guiding hint (the info-wash `hint` block or a muted sub line) wherever a non-specialist needs to know what to do next.
- **Do** respect `prefers-reduced-motion` for the rail transition, the node pulse and the hero chart draw-in.

### Don't:
- **Don't** let a screen fall into government-form greyness: rows of identical grey fields with no eyebrow, no answer, no hint and no hierarchy.
- **Don't** use Flow Cyan as text or fill on white sheets; it fails contrast there.
- **Don't** fill status as solid blocks or paint a whole section red; grade it.
- **Don't** lift cards with heavier shadows to signal importance; use an edge colour, an eyebrow or a verdict tile.
- **Don't** show a number without its source path or sample size.
