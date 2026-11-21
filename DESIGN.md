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
    rounded: "{rounded.sm}"
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
    rounded: "{rounded.sm}"
    padding: "1px 7px"
  hint:
    backgroundColor: "{colors.info-wash}"
    textColor: "#24407a"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
---

# Design System: Risk Miner

<!-- impeccable:design-map -->
Name: Risk Miner
Colors: primary: reservoir-teal #0f7c8c; secondary: night-network #0f2438; tertiary: junction-amber #f2b45a; neutral: desk-mist #f4f6f9; status: ok-green #1f7a4d; primary: main-line-navy #16324f (+7 more in the sidecar)
Fonts: system-ui (display, headline, title, body, label, eyebrow, metric); ui-monospace (mono)
Spacing: xxs 4px, xs 8px, sm 12px, md 16px, lg 22px, xl 28px
Radius: xs 6px, sm 8px, md 10px, lg 12px, xl 14px, hero 18px, pill 999px
North Star: "The Utility Control Room"
Rules:
- The Wash-and-Ink Rule. Status is shown as a soft wash with strong same-hue text and a tinted border, for example Bad Wash ground, Bad Red text, border `#f3c5c0`.
- The Water Stays in the Pipes Rule. Flow Cyan and Junction Amber live on the Night Network sidebar.
- The Graded Risk Rule. Risk severity always uses the full scale (ok, warn, bad, info, grey).
- The Number-with-a-Sentence Rule. A large figure never stands alone.
- The Floating-Only-When-Floating Rule. Shadows heavier than Sheet belong only to layers that sit above the page (modal, palette, tooltip).
Elevation:
- Sheet: 0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.08)
- Tooltip: 0 8px 24px rgba(16,32,52,.16)
- Modal: 0 20px 60px rgba(0,0,0,.25)
- Palette: 0 30px 80px rgba(0,0,0,.35)
Don't:
- Don't let a screen fall into government-form greyness: rows of identical grey fields with no eyebrow, no answer, no hint and no hierarchy.
- Don't use Flow Cyan as text or fill on white sheets; it fails contrast there.
- Don't fill status as solid blocks or paint a whole section red; grade it.
- Don't lift cards with heavier shadows to signal importance; use an edge colour, an eyebrow or a verdict tile.
- Don't show a number without its source path or sample size.
Do:
- Do lead every view with the plain-language answer, then the numbers, then the evidence trail (verdict, then layers, then sources).
- Do pair every headline number with its basis in Slate Muted ("k z n", n_eff, P80 interval).
- Do use the Wash-and-Ink treatment for status, with tinted borders: ok `#bfe3cf`, warn `#f3d6a8`, bad `#f3c5c0`, info `#c9d6f2`.
- Do keep Reservoir Teal as the only action colour on the desk, and Flow Cyan and Junction Amber inside the sidebar.
- (+3 more)
Full: .impeccable/design-full.md (read a section when you need its detail)
