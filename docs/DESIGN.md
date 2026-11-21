---
name: Risk Miner
description: Pamięć inwestycji — investment risk read like a river level on a gauge staff, against warning and alarm marks.
colors:
  river: "#0B2A45"
  river-2: "#123A5D"
  river-3: "#1A4C77"
  rail-text: "#C7D6E4"
  rail-muted: "#8FA8BF"
  rail-faint: "#A9BCCF"
  water: "#1668A8"
  water-deep: "#0F5389"
  water-bright: "#2E8FD6"
  water-side: "#5FB3EA"
  water-wash: "#E1EEF8"
  water-line: "#BCD6EE"
  level-ok: "#17703F"
  level-ok-fill: "#1E8A52"
  level-ok-wash: "#E2F3EA"
  level-ok-line: "#B9E0C9"
  level-warn: "#7A5600"
  level-warn-fill: "#F4C20D"
  level-warn-edge: "#9A7200"
  level-warn-wash: "#FFF6D6"
  level-warn-line: "#F0DC8E"
  level-alarm: "#B31F27"
  level-alarm-fill: "#D3262E"
  level-alarm-wash: "#FCE6E6"
  level-alarm-line: "#F2BDBF"
  level-alarm-on-river: "#FF5A5F"
  level-p90-on-river: "#FFB3B6"
  ground: "#EEF3F7"
  ground-raised: "#F4F8FB"
  panel: "#FFFFFF"
  ink: "#0E2236"
  muted: "#4A5D72"
  line: "#D3DEE8"
  line-strong: "#A9BDD0"
  soft: "#E6EEF4"
typography:
  display:
    fontFamily: "Barlow Semi Condensed, Barlow, system-ui, sans-serif"
    fontSize: "38px"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-0.2px"
  headline:
    fontFamily: "Barlow Semi Condensed, Barlow, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.15
  title:
    fontFamily: "Barlow Semi Condensed, Barlow, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.2
  subtitle:
    fontFamily: "Barlow Semi Condensed, Barlow, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 700
  body:
    fontFamily: "Barlow, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  label:
    fontFamily: "Barlow Semi Condensed, Barlow, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0.3px"
  tile-heading:
    fontFamily: "Barlow Semi Condensed, Barlow, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.15
    fontFeature: "tnum"
  figure-xl:
    fontFamily: "Barlow Semi Condensed, Barlow, system-ui, sans-serif"
    fontSize: "52px"
    fontWeight: 800
    lineHeight: 1
    fontFeature: "tnum"
  figure:
    fontFamily: "Barlow Semi Condensed, Barlow, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 800
    lineHeight: 1
    fontFeature: "tnum"
rounded:
  xs: "6px"
  sm: "8px"
  md: "10px"
  card: "12px"
  lg: "14px"
  xl: "18px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "12px"
  lg: "16px"
  card: "18px"
  xl: "24px"
  page-x: "32px"
components:
  button-primary:
    backgroundColor: "{colors.water}"
    textColor: "{colors.panel}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
  button-primary-hover:
    backgroundColor: "{colors.water-deep}"
  button-secondary:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
  button-new-investment:
    backgroundColor: "{colors.water}"
    textColor: "{colors.panel}"
    rounded: "{rounded.md}"
    padding: "12px 14px"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "8px 10px"
  card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.card}"
    padding: "{spacing.card}"
  chip-ok:
    backgroundColor: "{colors.level-ok-wash}"
    textColor: "{colors.level-ok}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  chip-warn:
    backgroundColor: "{colors.level-warn-wash}"
    textColor: "{colors.level-warn}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  chip-alarm:
    backgroundColor: "{colors.level-alarm-wash}"
    textColor: "{colors.level-alarm}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  chip-pending:
    backgroundColor: "{colors.water-wash}"
    textColor: "{colors.water-deep}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  nav-rail:
    backgroundColor: "{colors.river}"
    textColor: "{colors.rail-text}"
    width: "272px"
  gauge-panel:
    backgroundColor: "{colors.river}"
    rounded: "{rounded.lg}"
    padding: "18px"
  drawer:
    backgroundColor: "{colors.panel}"
    width: "440px"
---

# Design System: Risk Miner

## Overview

**Creative North Star: "Stany ostrzegawcze" (the hydrological bulletin)**

Risk Miner reads investment risk the way Poland reads a river: a level on a gauge staff, measured against a warning mark (stan ostrzegawczy, the base's P50) and an alarm mark (stan alarmowy, P80). The world is an IMGW bulletin: a deep river-navy shell, a light mist work ground, water blue as the only colour that acts, and a three-step warning ladder that carries risk level and nothing else.

Density is that of a working desk tool, not a marketing page: white sheets on mist, condensed numerals, every figure tabular. The signature is the gauge staff (wodowskaz), a decimetre E-block face on a navy plate that water fills once and settles at P80. The same level vocabulary colours chips, tiles, chart dots, chart bands and the small staff bar in the project drawer, so a reader who has learned one gauge can read every screen.

The system refuses the navy/teal SaaS dashboard with one accent and flat interchangeable cards. Desktop is the target (user decision); below 1100px grids collapse, below 900px the rail stacks, and nothing further is promised.

**Key Characteristics:**
- River-navy rail and gauge plates; mist ground; white sheets.
- Water blue for every action, link, selection and focus on light ground.
- Green / yellow / red ladder for risk level only, always tied to P50 and P80.
- Barlow for prose, Barlow Semi Condensed for headings and numbers, tabular figures everywhere.
- Motion fills and settles once; reduced motion shows the final state.

## Colors

A cold river palette with one action hue and a signal ladder held in reserve for risk.

### Primary
- **Water** (water): primary buttons, the "Analizuj nową inwestycję" call, links, active tab underline, input focus border. Hover deepens to **Deep Water** (water-deep); the rail call lifts to #1F7FC4.
- **Bright Water** (water-bright): the water inside gauges, plan bars and plan dots in charts, probability bars.
- **Side Water** (water-side): water seen against the river: active nav icon, record ids in the rail, drawer id, gauge base line, DB progress.
- **Water Wash** (water-wash) with **Water Line** (water-line): pending, to-verify, info and selected states (chips, flags, tiles, hovered table rows, selected command item, input focus ring).

### Secondary: the warning ladder
- **Level OK** (level-ok, fill level-ok-fill, wash, line): below P50, stan normalny.
- **Level Warn** (level-warn text, level-warn-fill signal yellow, edge, wash, line): at or above P50, stan ostrzegawczy.
- **Level Alarm** (level-alarm text, level-alarm-fill, wash, line): at or above P80, stan alarmowy.
- **Alarm on River** (level-alarm-on-river) and **P90 on River** (level-p90-on-river, dashed): the P80 and P90 marks drawn on the navy gauge plate, where the light-ground reds lack contrast.

### Neutral
- **River** (river), **River 2** (river-2), **River 3** (river-3): rail, gauge plate, drawer header, flow strip, toast, tooltip; hover and active nav steps.
- **Rail Text / Muted / Faint** (rail-text, rail-muted, rail-faint): text tiers on river surfaces.
- **Mist Ground** (ground): page background. **Raised Ground** (ground-raised): table heads, quotes, gauge face.
- **Panel** (panel): cards, tiles, drawer, modals. **Ink** (ink), **Muted** (muted): text. **Line** (line), **Line Strong** (line-strong, hover borders), **Soft** (soft, grey chips and tracks).

### Named Rules
**The One Water Rule.** Water is the only action colour. Buttons, links, active tabs, focus rings on light ground and selected rows are water; no ladder colour ever marks something clickable.

**The Ladder Means Level Rule.** Green, yellow and red say where a value stands against the base's P50 and P80, and nothing else. Pending, to-verify, in-progress and info states use water wash, never the ladder.

**The Two Marks Rule.** P50 is always stan ostrzegawczy (yellow) and P80 always stan alarmowy (red), in gauges, chart bands, staff bars, legends and copy. `levelOf` is the single source: value ≥ P80 alarm, ≥ P50 warn, otherwise ok.

## Typography

**Display Font:** Barlow Semi Condensed (self-hosted 600–800, fallback Barlow, system-ui)
**Body Font:** Barlow (self-hosted 400–700, fallback system-ui)

**Character:** the condensed face is the bulletin's figure and heading voice, upright and engineered; Barlow carries the plain Polish prose at a comfortable desk size.

### Hierarchy
- **Display** (700, 38px, 1.08): the start-page hero question, max 20ch; 42px on the empty-base hero.
- **Headline** (700, 30px, 1.15): page h1.
- **Title** (700, 22px, 1.2): h2, drawer title; 24px for the verdict heading; 20px for evidence-layer tags.
- **Subtitle** (700, 17px): h3 and gauge titles; 16px for disclosure summaries.
- **Body** (400, 15px, 1.5): all prose; lead copy 16.5px/1.6 max 58ch; sub-lines max 90ch.
- **Label** (700, 12.5px, 0.3px tracking): table heads, chips.
- **Tile heading** (700, 22px, 1.15, condensed): one line per tile, a run-in label in ink at weight 600 followed by a colon, then the value in its level colour ("Dane wejściowe: bez problemów"). A tile whose sentence already names itself carries no label ("Ceny z przetargu −26% wobec kosztorysu").
- **Figures** (800, 52px / 34px / 30px): risk percentage callout, flow counts, gauge values, KPI values.

### Named Rules
**The Tabular Figures Rule.** `font-variant-numeric: tabular-nums` is set on body and inherited everywhere; numbers align in columns and do not jitter while counting up.

**The Condensed Numbers Rule.** Every figure that is read as a measurement, and every heading, sets in Barlow Semi Condensed; prose and controls stay in Barlow.

**The No Kicker Rule.** Headings stand alone; no small label line sits above a heading or a value. A tile names itself with a run-in label on the same line as its value, never with a caption stacked above it. The only uppercase text in the system is the nav group label inside the river rail.

## Layout

A two-column shell: a sticky 272px river rail (78px when collapsed to icons with the `[` key) and a main column padded 26px 32px 64px, capped at 1440px. Content sits on 2/3/4/6-column grids with 16px gaps; tiles use auto-fit columns of min 220px with 12px gaps. The start hero is a 1 : 1.1 split of question and chart; the analysis verdict is gauges on the left, answer on the right. Project detail opens in a 440px drawer from the right instead of navigating away. Rhythm steps are 6 / 10 / 12 / 16 / 18 / 24 / 32px. Desktop only: grids fall to two or one column at 1100px, the verdict stacks at 1250px, the rail stacks at 900px.

## Elevation & Depth

Depth is mostly tonal: navy rail and plates against mist, white sheets on mist. One soft ambient shadow lifts sheets; overlays get progressively deeper navy-tinted shadows. Shadows are always tinted with river (rgba 11,42,69), never neutral black.

### Shadow Vocabulary
- **Sheet** (`0 1px 2px rgba(11,42,69,.06), 0 4px 14px rgba(11,42,69,.06)`): cards, hero, verdict, evidence layers, change entries.
- **Tile lift** (`0 8px 22px rgba(11,42,69,.08)`): tile hover with a 2px rise.
- **Primary hover** (`0 4px 12px rgba(22,104,168,.25)`): water glow under a hovered primary button.
- **Drawer** (`-16px 0 40px rgba(11,42,69,.18)`), **Tooltip** (`0 10px 28px rgba(11,42,69,.28)`), **Toast** (`0 10px 30px rgba(11,42,69,.3)`), **Modal** (`0 24px 60px rgba(11,42,69,.3)`), **Command palette** (`0 30px 80px rgba(11,42,69,.4)`).

## Shapes

Gently rounded, never pill-shaped except chips: 8px controls, 10px rail items and flags, 12px cards and tiles, 14px gauge plates and flow strip, 18px hero and verdict sheets. Ladder chips are fully rounded with a 1px line in the matching level-line colour. The gauge staff keeps its engineering geometry: a 4px-rounded navy plate, square E-block ticks alternating left and right per decimetre.

## Components

### Buttons
- **Shape:** 8px radius, 600 14px Barlow, 1px border; `sm` 6px/13px, `big` 10px/16px.
- **Primary:** water fill, white text; hover deep water plus water glow; active presses 1px down.
- **Secondary:** white with line border; hover line-strong border and #F6F9FC.
- **Destructive:** white with alarm-line border and alarm text; hover alarm wash.
- **New investment (rail):** water block with plus icon, 700 15px; hover lifts 1px; white with river text when its view is active.

### Chips
- **Style:** 700 12.5px condensed, fully rounded, wash background, level-coloured text, level-line border.
- **State:** ok / warn / alarm for level; water wash for pending and to-verify; soft grey for neutral or rejected.

### Cards / Tiles
- **Corner Style:** 12px (`--r`).
- **Tile heading:** a single 22px condensed line, `Label:` run in at ink 600, value in the level colour (river when the tile has no level); an optional 13.5px muted sub-line below.
- **Background:** panel; tiles take the level wash and line of their level, water wash for info.
- **Shadow Strategy:** Sheet shadow; tiles border-only with a lift on hover.
- **Internal Padding:** 18px cards, 14px 16px tiles.

### Inputs / Fields
- **Style:** 1px line, 8px radius, 8px 10px padding, panel fill.
- **Focus:** water border plus 3px water-wash ring. Labels 600 13px muted above the field.

### Navigation
- **Rail:** river background; items 15px 600 with a 12.5px rail-muted hint line and a 20px stroke icon; hover river-2, active river-3 with the icon in side water. Group labels are 700 11.5px uppercase condensed in #7F98B0. Recent records show their ids in side water. Search opens a ⌘K command palette.
- **Tabs:** 600 15px muted, 3px water underline when active.

### Gauge Staff (wodowskaz)
A navy plate holding a mist face with decimetre E-block ticks. Bright water (78% opacity, wavy crest) fills from below and settles at P80 over 1.6s; P50 (signal yellow), P80 (alarm on river) and dashed P90 marks fade in after 1s with white labels, offset so they never collide. The value below counts up over 1.1s in 800 30px condensed. Two gauges (cost reserve, time) share one river panel with a legend that names P50 stan ostrzegawczy and P80 stan alarmowy.

### Plan → Reality Chart
Start-page scatter: x is delay, y is cost deviation. Alarm-wash and warn-wash bands sit above the dashed P80 and P50 lines; their two-line labels ("stan alarmowy / P80 …", "stan ostrzegawczy / P50 …") live in a 108px right margin outside the plot, so a label never sits on data; dots are coloured by `levelOf` (ok / warn / alarm), filled when on time and hollow-outlined when late, and open the project drawer. Bands rise, arrows draw, dots pop in once.

### Map Side Lists
Beside the Poland map, "Najdłuższe opóźnienia" and "Największe przekroczenia kosztu" list contracts with a level dot. Each list levels its dots by its own measure: delay against the base's time P50/P80, cost against the base's cost P50/P80. A small muted caption under each heading says which level the colour shows ("kolor: stan opóźnienia względem całej bazy").

### Project Drawer
440px slide-in from the right (0.42s) over a 28% river scrim; river header with side-water id and white title; body sections slide in staggered 60ms; a horizontal staff bar shows this contract against the base's ok / warn / alarm zones with a navy pointer.

## Do's and Don'ts

### Do:
- **Do** use water (`--water`) for every action and link, and water wash for pending, to-verify and info states.
- **Do** colour risk by `levelOf`: below P50 ok, P50 stan ostrzegawczy, P80 stan alarmowy, and label the marks with those words.
- **Do** say which measure a level colour shows (cost or time) wherever both could apply, and keep chart labels in the margin, off the data.
- **Do** set headings and measured figures in Barlow Semi Condensed with tabular figures.
- **Do** keep motion to one fill-and-settle, count-up or slide, on `cubic-bezier(.16,1,.3,1)`, and show final states under `prefers-reduced-motion`.
- **Do** tint every shadow and scrim with river navy.

### Don't:
- **Don't** use green, yellow or red for anything other than risk level against P50/P80.
- **Don't** add a second action hue or make a ladder colour clickable.
- **Don't** put uppercase kickers or eyebrows above headings.
- **Don't** loop animations; nothing pulses, waves or spins indefinitely.
- **Don't** fall back to system display faces or proportional figures for numbers.
