---
version: 1
slug: "static-index-html"
primary_target: "static/index.html"
related_targets: []
---

# Surface brief: Risk Miner app (whole SPA)

Scope: every view of the single-page app (Start, case base, change library, expert panel, monitoring, expert knowledge, reports, settings, new-investment analysis). Mode: Operate. Desktop only (no mobile work). Audience: ministry analysts, planners and experts; the HackNation jury in a 3-minute demo. Constraints: Polish UI, WCAG 2.1 AA, works offline (self-hosted fonts), only static/ may change. User asked for vivid colour, motion, live charts and elements that slide out; user-declared failures: too playful, unreadable numbers, generic SaaS.

## Direction contract

THESIS: Investment risk read the way Poland reads a river: as a level on a gauge staff against warning and alarm marks. Refuses the navy/teal SaaS dashboard with one accent and flat cards.

OWN-WORLD: IMGW hydrological bulletin. Deep river-navy shell, light mist work ground, water blue as the only action colour, a warning ladder (green → yellow → red: below P50, stan ostrzegawczy at P50, stan alarmowy at P80) that carries risk levels only. Barlow for text, Barlow Semi Condensed for numbers and headings, tabular figures everywhere. Gauge staffs with decimetre ticks; level chips.

STORY: The visitor sees immediately how far real contracts rose above plan, opens any contract from a chart in a sliding panel, then describes a new investment and watches its cost and time gauges fill to P80 against the base's warning and alarm levels, with actions to take.

FIRST VIEWPORT: Navy rail left. Start: hero question with the plan→reality chart, where horizontal bands mark the base's P50 (stan ostrzegawczy) and P80 (stan alarmowy); dots open a slide-out project panel. Analysis: verdict with two animated gauges (cost reserve, time) and level-coloured tiles; primary action "Analizuj nową inwestycję" in water blue.

FORM: Stany ostrzegawcze (IMGW hydrological bulletins); position 1 on my ordered list, chosen by the user as the pick card over the assigned position 5 (Linie sieci); seed:8f5adcc1c3138b2b (degraded roll, no challengers).

SIGNATURE: the gauge staff (wodowskaz): water rises with eased motion to P50/P80/P90 marks; the same level vocabulary colours chips, tiles and chart bands. Motion grammar: one fill-and-settle per gauge, count-up numbers, panels and disclosures slide; reduced-motion shows final states.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
