# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences carry equal weight:

- **Institution users** at MFiPR (Departament PPP) and public bodies that prepare water and sewage investments:
  - **Analysts** load project records and check the case base built from BZP.
  - **Planners** describe a new investment, optionally upload a draft contract (PPU/SWZ), and need to know how similar contracts actually ended and what this contract should say.
  - **Experts** approve, correct, or reject extracted risk events, facts, and uncertain links. They also edit the risk catalogue and checklist.
- **The HackNation 2026 jury** judges the product through a demo of 3 minutes or less and through the required test paths in `docs/SCENARIUSZ_DEMO.md`: import and enrichment, analysis with export, source tracing, the expert workflow, and an idempotent re-run. The demo path has to land as well as the day-to-day workflow does.

The working language is Polish. Users are public-sector professionals: procurement, investment and legal specialists, not data scientists.

## Product Purpose

Risk Miner is the institution's digital memory of public investments. It builds a structured case base automatically from scattered public sources: the organiser's file, BZP/e-Zamówienia, TED, PDF/DOCX/XLSX documents, and BIP/NIK/KIO pages. From that base it detects documented risk events against the expert catalogue and puts them through expert review. For a new investment it answers how similar contracts actually ended and what to write into this contract so it does not end the same way.

Success means a planner gets reference-class numbers (P50/P80/P90 for cost and time), a priced risk register, and a clause audit. Every number and conclusion must trace back to a cited source.

## Positioning

- It checks against the real BZP API, not against assumptions. The search strategy is built on the filters that actually work.
- It reads the numbered fields of the BZP notice form the way an expert would, with one record per contract change.
- It forecasts from a reference class (similarity-weighted P80 with a bootstrap interval and effective sample size) instead of averaging similar projects.
- It separates source data, calculations, and conclusions explicitly (layers A, B and C), and every fact carries its source, URL, fetch date, page, and quote.

## Operating Context

- It runs locally (`./run.sh` or Docker) on any laptop, with a SQLite database in a single file. It works offline using the bundled copy of 198 real BZP notices for 22 pilot projects.
- Pilot sector: water and sewage (wod-kan).
- Users work with BZP notice numbers, `tenderId`, NIP, KPO/CST numbers, and the bases for change in art. 455, 439, 436 and 447 of the Pzp (public procurement law).
- Outputs: printable risk cards, JSON/CSV exports, and the link-test report.
- Expert decisions are attributed to a named expert, entered in the sidebar.

## Capabilities and Constraints

- Existing UI: a single-page vanilla JS app (`static/`) served by a Python `http.server` backend. It has no mandatory dependencies and no build step.
- Views: Start (lessons from the whole base, the plan-vs-reality chart, the map), the case base, the contract-change library, the expert panel, monitoring, expert knowledge, reports and export, and settings and sources. There is also a ⌘K command palette and the new-investment analysis.
- An LLM is optional and configurable (OpenAI-compatible or Anthropic). LLM-generated narrative must be labelled as such.
- The clause audit is a checklist with quotes and legal bases, for a lawyer to assess. It is not legal advice.
- Small sample (22 contracts): n, n_eff, and bootstrap intervals must stay visible next to statistics.

## Brand Commitments

- Name: **Risk Miner**. Tagline in the UI: „pamięć inwestycji” (investment memory).
- Logo files are binding: `../logo/Risk_Miner_ikona.svg`, `Risk_Miner_ikona.png`, `Risk_Miner_logo_jasne.png` (light), and `Risk_Miner_logo_ciemne.png` (dark). They live in the parent challenge folder, outside the repo.
- Voice: plain, precise Polish. It states numbers with their basis ("16 z 22 umów", meaning 16 of 22 contracts) and does not overclaim.

## Evidence on Hand

- Real data: `samples/bzp_kopia_22_projekty.json` (198 BZP notices), `samples/Risk_Miner_dane_projekty.xlsx` (organiser records), a sample new-investment description, and a sample draft contract.
- Real findings from the base are listed in `docs/OPIS_ROZWIAZANIA.md`. Examples: 16 of 22 contracts settled above the contract value, 18 of 22 finished late, and the data errors in RM-2026-022 and RM-2026-002.
- Demo video: `../Risk_Miner_film.mp4`.
- There are no testimonials, institutional endorsements, or deployment claims. None may be invented.

## Product Principles

1. **Every claim has a source.** No number or conclusion appears without a path back to the notice, document, page, or quote.
2. **Data, calculation, and conclusion stay distinguishable.** The user always knows which of the three they are looking at.
3. **The expert decides.** Automated findings are proposals until a person approves them, and every decision is recorded.
4. **Honest uncertainty.** Show sample size, confidence, and gaps ("not in the package" is not the same as "does not exist") instead of false precision.
5. **Answer first, evidence on demand.** The 30-second answer leads, and the full trail is one click away. This serves the planner and the jury alike.

## Accessibility & Inclusion

WCAG 2.1 AA is binding, as the Polish digital accessibility act requires for public-sector tools. The UI must be fully usable from the keyboard, and Polish is the interface language.
