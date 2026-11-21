/* Risk Miner — interfejs (vanilla JS, bez zależności zewnętrznych) */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => (v === null || v === undefined ? "" : String(v)).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pln = (v) => (v === null || v === undefined || isNaN(v) ? "—" : Number(v).toLocaleString("pl-PL", { maximumFractionDigits: 0 }) + " zł");
const pct = (v) => (v === null || v === undefined || isNaN(v) ? "—" : (v >= 0 ? "+" : "") + (v * 100).toLocaleString("pl-PL", { maximumFractionDigits: 1 }) + "%");
const days = (v) => (v === null || v === undefined ? "—" : (v > 0 ? "+" : "") + Math.round(v) + " dni");
const num = (v, d = 0) => (v === null || v === undefined || isNaN(v) ? "—" : Number(v).toLocaleString("pl-PL", { maximumFractionDigits: d }));
const dt = (s) => (s ? String(s).replace("T", " ").slice(0, 16) : "—");
const user = () => localStorage.getItem("rm_user") || "ekspert";

let RISK_NAMES = {};
let STATUS = null;

async function api(path, opts = {}) {
  const headers = Object.assign({ "X-User": encodeURIComponent(user()) }, opts.headers || {});
  let body = opts.body;
  if (body && !(body instanceof Blob) && !(body instanceof ArrayBuffer) && typeof body !== "string") {
    body = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }
  const r = await fetch(path, { method: opts.method || (body ? "POST" : "GET"), headers, body });
  const ct = r.headers.get("Content-Type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error((data && data.error) || r.statusText);
  return data;
}
const post = (p, b = {}) => api(p, { method: "POST", body: b });
async function upload(path, file) {
  return api(path, { method: "POST", body: file, headers: { "X-Filename": encodeURIComponent(file.name), "Content-Type": "application/octet-stream" } });
}

function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (err ? " err" : "");
  clearTimeout(t._h);
  t._h = setTimeout(() => (t.className = "toast hidden"), err ? 7000 : 3500);
}
function modal(html) { $("#modal-body").innerHTML = html; $("#modal").classList.remove("hidden"); }
function closeModal() { $("#modal").classList.add("hidden"); }
window.closeModal = closeModal;
async function guard(fn, okMsg) {
  try { const r = await fn(); if (okMsg) toast(okMsg); return r; } catch (e) { toast("Błąd: " + e.message, true); throw e; }
}

const statusPill = (s) => {
  const m = { approved: ["zatwierdzone", "p-ok"], edited: ["zatwierdzone (poprawione)", "p-ok"], proposed: ["do weryfikacji", "p-warn"], rejected: ["odrzucone", "p-grey"], auto: ["pewne (identyfikator)", "p-acc"] };
  const [l, c] = m[s] || [s || "—", "p-grey"];
  return `<span class="pill ${c}">${esc(l)}</span>`;
};
const confPill = (c) => {
  if (c === null || c === undefined) return "";
  const cls = c >= 0.9 ? "p-ok" : c >= 0.65 ? "p-info" : c >= 0.45 ? "p-warn" : "p-bad";
  return `<span class="pill ${cls}" title="poziom pewności">${Math.round(c * 100)}%</span>`;
};
const methodLabel = (m) => ({ rule: "reguła katalogu", llm: "model językowy", computed: "wyliczone z danych", manual: "wpis eksperta", "notice-parser": "parser ogłoszenia", xlsx: "plik organizatora", identifier: "identyfikator", "text-match": "dopasowanie treści", "formularz BZP": "pole formularza BZP (odczyt strukturalny)" }[m] || m || "");
const riskLabel = (c) => (c ? `<span class="pill p-info code" title="${esc(RISK_NAMES[c] || "")}">${esc(c)}</span> ${esc(RISK_NAMES[c] || "")}` : "");
function srcLink(sources, sid, page) {
  const s = sources && sid ? sources[sid] : null;
  if (!s) return "";
  const label = esc(s.title || s.ref || s.kind);
  const pg = page ? `, s. ${page}` : "";
  const when = s.fetched_at ? ` · pobrano ${dt(s.fetched_at)}` : "";
  return s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${label}</a><span class="muted small">${pg}${when}</span>` : `<span>${label}</span><span class="muted small">${pg}${when}</span>`;
}

// ------------------------------------------------------------ router
const VIEWS = {};
async function router() {
  const h = location.hash.replace(/^#/, "") || "/";
  const parts = h.split("/").filter(Boolean);
  const v = parts[0] || "";
  const map = { "": "dash", zmiany: "changes", projekty: "projects", projekt: "project", ekspert: "review", nowa: "new", analiza: "new", monitoring: "monitor", wiedza: "knowledge", raporty: "reports", ustawienia: "settings" };
  const key = map[v] || "dash";
  $$("#nav a, .cta-new").forEach((a) => a.classList.toggle("active", a.dataset.v === (key === "project" ? "projects" : key) && !a.dataset.pid));
  $$("#recent a").forEach((a) => a.classList.toggle("active", key === "project" && a.dataset.pid === parts[1]));
  pulseActive();
  $("#main").innerHTML = `<div class="loading">Ładowanie…</div>`;
  try { await VIEWS[key](parts.slice(1)); } catch (e) { $("#main").innerHTML = `<div class="card"><h2>Błąd</h2><p>${esc(e.message)}</p></div>`; }
  refreshBadges();
}
window.addEventListener("hashchange", router);

async function refreshBadges() {
  try {
    STATUS = await api("/api/status");
    RISK_NAMES = STATUS.risk_names || RISK_NAMES;
    const c = STATUS.counts;
    $("#badge-review").textContent = (c.events_proposed + c.links_proposed + c.categories_proposed) || "";
    $("#badge-monitor").textContent = c.monitor_open || "";
    const hint = (v, t) => { const el = $(`#nav a[data-v="${v}"] .nh`); if (el && t) el.textContent = t; };
    const todo = c.events_proposed + c.links_proposed + c.categories_proposed;
    if (c.projects) {
      hint("projects", `${num(c.projects)} projektów · ${num(c.contracts)} umów`);
      hint("review", todo ? `${num(todo)} czeka na decyzję` : "wszystko sprawdzone");
      hint("monitor", c.monitor_open ? `${num(c.monitor_open)} nowych sygnałów` : "bez nowych sygnałów");
      hint("dash", `${num(c.notices)} ogłoszeń BZP w bazie`);
      if (c.changes) hint("changes", `${num(c.changes)} zmian z przyczyną i kosztem`);
    }
    hint("knowledge", `${Object.keys(STATUS.risk_names || {}).length} kategorii ryzyk`);
    hint("reports", c.analyses ? `${num(c.analyses)} analiz · CSV, JSON` : "CSV, JSON, raport łączenia");
    const src = (on, label, val, tip) => `<span class="src ${on ? "on" : "off"}" title="${esc(tip)}"><i></i>${esc(label)} <b>${esc(val)}</b></span>`;
    $("#conn").innerHTML = src(true, "BZP", STATUS.bzp_local ? "kopia lokalna" : STATUS.bzp_url.replace(/^https?:\/\//, "").split("/")[0], "źródło ogłoszeń")
      + src(STATUS.llm.enabled, "Model językowy", STATUS.llm.enabled ? STATUS.llm.model : "wyłączony", STATUS.llm.enabled ? STATUS.llm.provider : "działa na regułach — bez AI")
      + src(STATUS.capabilities.ocr, "OCR skanów", STATUS.capabilities.ocr ? "tak" : "nie", "odczyt zeskanowanych PDF");
    $("#dbstat").innerHTML = c.projects ? `<b>${num(c.projects)}</b> projektów <span>·</span> <b>${num(c.notices)}</b> ogłoszeń BZP<div class="dbbar"><i style="width:${Math.min(100, (c.events_approved / Math.max(1, c.events_approved + c.events_proposed)) * 100)}%"></i></div><span class="dbsm">${num(c.events_approved)} z ${num(c.events_approved + c.events_proposed)} zdarzeń zweryfikowanych</span>` : `<span class="dbsm">Baza jest pusta — wczytaj dane na pulpicie.</span>`;
  } catch (e) { /* serwer niedostępny */ }
}

// ------------------------------------------------------------ zadania w tle
async function watchJob(id, el, onDone) {
  el.innerHTML = `<div class="card"><div class="row"><b>Zadanie #${id}</b><span class="pill p-warn" id="job-st">w toku</span><div class="grow"><div class="bar"><i id="job-bar" style="width:2%"></i></div></div></div><pre class="log" id="job-log"></pre></div>`;
  const tick = async () => {
    const j = await api(`/api/jobs/${id}`);
    $("#job-bar", el).style.width = Math.max(2, (j.progress || 0) * 100) + "%";
    $("#job-log", el).textContent = (j.log || "").trim();
    $("#job-log", el).scrollTop = 1e9;
    $("#job-st", el).textContent = j.status;
    if (j.status === "w toku") return setTimeout(tick, 900);
    $("#job-st", el).className = "pill " + (j.status === "zakończone" ? "p-ok" : "p-bad");
    refreshBadges();
    if (onDone) onDone(j);
  };
  tick();
}

// ------------------------------------------------------------ PULPIT
VIEWS.dash = async () => {
  const s = await api("/api/status");
  STATUS = s; RISK_NAMES = s.risk_names;
  const c = s.counts;
  let ins = null, projects = [], changes = [];
  if (c.projects) [ins, projects, changes] = await Promise.all([api("/api/insights").catch(() => null), api("/api/projects"), api("/api/changes").catch(() => [])]);
  const maxR = Math.max(1, ...s.by_risk.map((r) => r.n));
  const hero = c.projects && ins ? heroBlock(ins, projects, changes) : `
    <section class="hero empty"><div class="hero-l"><h1 class="hero-h">Jak naprawdę kończą się inwestycje publiczne?</h1>
      <p class="hero-p">Risk Miner składa ogłoszenia z BZP w historię każdej umowy — koszt, termin, zmiany i ich przyczyny — i na tej podstawie ocenia nową inwestycję, zanim ogłosisz przetarg.</p>
      <div class="row"><button class="btn primary big" id="b-sample-bzp2">Wczytaj 22 projekty z prawdziwymi danymi BZP</button><span class="muted small">ok. 5 sekund · działa bez internetu</span></div></div></section>`;
  $("#main").innerHTML = `${hero}
    ${c.projects ? flowStrip(c, changes, s) : ""}
    ${c.projects ? mapBlock(projects) : ""}
    <div id="insights">${ins ? insightsCard(ins) : ""}</div>
    <h2 id="dane">Dane i zasilanie bazy</h2>
    <div class="grid g2">
      <div class="card">
        <h3 style="margin-top:0">Zasil bazę</h3>
        <p class="muted small">Plik organizatora (.xlsx/.csv) lub inny plik z podobnymi kolumnami. Po imporcie system sam wyszuka ogłoszenia w BZP, powiąże je z projektami i przeanalizuje.</p>
        <div class="drop" id="drop">Upuść plik z rekordami lub <label class="btn sm">wybierz<input type="file" id="f-import" accept=".xlsx,.csv" hidden></label></div>
        <div class="row" style="margin-top:10px">
          <button class="btn primary" id="b-sample-bzp" title="Rekordy organizatora + prawdziwa kopia 198 ogłoszeń BZP pobrana z API — działa bez sieci, wynik powtarzalny">Demo na prawdziwych danych BZP (22 projekty, offline)</button>
          <button class="btn" id="b-sample">Pakiet organizatora — BZP na żywo</button>
          <label class="row small"><input type="checkbox" id="c-enrich" checked> od razu wzbogać z BZP</label>
        </div>
        <div class="row" style="margin-top:8px"><button class="btn" id="b-enrich-all" ${c.projects ? "" : "disabled"}>Wzbogać wszystkie projekty z BZP/TED</button></div>
        <div id="job"></div>
      </div>
      <div class="card">
        <h3 style="margin-top:0">Zdarzenia ryzyka w bazie wg katalogu</h3>
        ${s.by_risk.length ? `<table>${s.by_risk.map((r) => `<tr><td style="width:55%">${riskLabel(r.risk_code)}</td><td><div class="bar" title="${r.n}"><i style="width:${(r.n / maxR) * 100}%"></i></div></td><td class="num">${r.n}</td><td class="num small muted">${r.approved} zatw.</td></tr>`).join("")}</table>` : `<div class="empty">Brak zdarzeń — zasil bazę.</div>`}
      </div>
    </div>
    <h2>Ostatnie operacje</h2>
    <div class="card" style="padding:0">${historyTable((s.recent || []).slice(0, 8))}</div>`;
  const doImport = async (file) => {
    const enrich = $("#c-enrich").checked ? "?enrich=1" : "";
    const r = await guard(() => api("/api/import" + enrich, { method: "POST", body: file, headers: { "X-Filename": encodeURIComponent(file.name) } }));
    toast(`Zaimportowano: ${r.created} nowych, ${r.updated} zaktualizowanych`);
    if (r.job_id) watchJob(r.job_id, $("#job"), () => VIEWS.dash());
    else VIEWS.dash();
  };
  $("#f-import").onchange = (e) => e.target.files[0] && doImport(e.target.files[0]);
  dropzone($("#drop"), (files) => doImport(files[0]));
  $("#b-sample").onclick = async () => {
    const r = await guard(() => post("/api/import-sample" + ($("#c-enrich").checked ? "?enrich=1" : "")));
    toast(`Pakiet organizatora: ${r.created} nowych, ${r.updated} zaktualizowanych`);
    if (r.job_id) watchJob(r.job_id, $("#job"), () => VIEWS.dash()); else VIEWS.dash();
  };
  const demo = async () => {
    const r = await guard(() => post("/api/import-sample?enrich=1&bzp=1"));
    toast(`Wczytano kopię BZP i ${r.created + r.updated} rekordów — trwa wzbogacanie`);
    if (r.job_id) { $("#dane").scrollIntoView({ behavior: "smooth" }); watchJob(r.job_id, $("#job"), () => VIEWS.dash()); } else VIEWS.dash();
  };
  $("#b-sample-bzp").onclick = demo;
  if ($("#b-sample-bzp2")) $("#b-sample-bzp2").onclick = demo;
  $("#b-enrich-all").onclick = async () => { const r = await guard(() => post("/api/enrich", {})); watchJob(r.job_id, $("#job"), () => VIEWS.dash()); };
  animateHero();
};

// ---- pulpit: bohater (plan → rzeczywistość) i przepływ danych
function heroBlock(ins, projects, changes) {
  const c = ins.rcf.cost, t = ins.rcf.time;
  const pts = projects.filter((p) => p.metrics && p.metrics.cost_dev_pct != null && p.metrics.delay_days != null && p.metrics.planned_duration_days)
    .map((p) => ({ id: p.id, rid: p.record_id, city: p.city || p.beneficiary_name, name: p.name, x: p.metrics.delay_days / p.metrics.planned_duration_days, y: p.metrics.cost_dev_pct, v: p.metrics.contract_value || 1, unverified: !!p.n_links_proposed }));
  const both = pts.filter((p) => p.x > 0.005 && p.y > 0.005).length;
  const W = 560, H = 380, L = 62, R = 18, T = 18, B = 40;
  const xmax = Math.max(1.2, ...pts.map((p) => p.x)) * 1.05, xmin = Math.min(-0.15, ...pts.map((p) => p.x));
  const ymax = Math.max(0.45, ...pts.map((p) => p.y)) * 1.08, ymin = Math.min(-0.15, ...pts.map((p) => p.y)) * 1.1;
  const X = (v) => L + ((v - xmin) / (xmax - xmin)) * (W - L - R), Y = (v) => T + ((ymax - v) / (ymax - ymin)) * (H - T - B);
  const vmax = Math.max(...pts.map((p) => p.v));
  let g = `<rect x="${X(0)}" y="${T}" width="${W - R - X(0)}" height="${Y(0) - T}" fill="#e34948" opacity=".06"/>
    <text x="${W - R - 8}" y="${T + 16}" text-anchor="end" font-size="12" font-weight="700" fill="#b42318">drożej i dłużej: ${both} z ${pts.length}</text>`;
  for (const tx of [0, 0.5, 1, 1.5, 2, 2.5, 3]) if (tx <= xmax) g += `<line x1="${X(tx)}" x2="${X(tx)}" y1="${T}" y2="${H - B}" stroke="${VZ.grid}" ${tx ? "" : 'stroke="#9aa8b6"'}/><text x="${X(tx)}" y="${H - B + 16}" font-size="11" text-anchor="middle" fill="${VZ.muted}">${tx ? "+" + Math.round(tx * 100) + "%" : "plan"}</text>`;
  for (const ty of [-0.4, -0.2, 0, 0.2, 0.4]) if (ty >= ymin && ty <= ymax) g += `<line x1="${L}" x2="${W - R}" y1="${Y(ty)}" y2="${Y(ty)}" stroke="${ty ? VZ.grid : "#9aa8b6"}"/><text x="${L - 6}" y="${Y(ty) + 4}" font-size="11" text-anchor="end" fill="${VZ.muted}">${ty ? (ty > 0 ? "+" : "−") + Math.abs(Math.round(ty * 100)) + "%" : "plan"}</text>`;
  g += `<text x="${(L + W - R) / 2}" y="${H - 6}" font-size="11.5" text-anchor="middle" fill="${VZ.ink}">czas realizacji względem umowy →</text>
    <text transform="translate(12 ${(T + H - B) / 2}) rotate(-90)" font-size="11.5" text-anchor="middle" fill="${VZ.ink}">koszt względem umowy →</text>`;
  pts.forEach((p, i) => {
    const late = p.x > 0.005, over = p.y > 0.005;
    const col = late && over ? VZ.late : !late && !over ? VZ.early : VZ.plan;
    const r = 4.5 + 6 * Math.sqrt(p.v / vmax);
    g += `<line class="arr" style="--d:${i * 35}ms" x1="${X(0)}" y1="${Y(0)}" x2="${X(p.x)}" y2="${Y(p.y)}" stroke="${col}" stroke-opacity=".28" stroke-width="1.5"/>`;
    g += `<a href="#/projekt/${p.id}"><circle class="dot" style="--d:${i * 35}ms" cx="${X(p.x)}" cy="${Y(p.y)}" r="${r}" fill="${p.unverified ? "#fff" : col}" stroke="${p.unverified ? col : "#fff"}" stroke-width="2" data-tip="<b>${esc(p.rid)} · ${esc(p.city)}</b><br>${esc(p.name.slice(0, 90))}<br>koszt ${pp(p.y, 1)} · czas ${pp(p.x, 0)}${p.unverified ? "<br><i>dopasowanie do weryfikacji</i>" : ""}<br><u>kliknij, aby otworzyć</u>"/></a>`;
  });
  g += `<circle cx="${X(0)}" cy="${Y(0)}" r="5" fill="${VZ.ink}"/><text x="${X(0) + 8}" y="${Y(0) + 16}" font-size="11.5" font-weight="700" fill="${VZ.ink}">plan</text>`;
  const top = (ins.register.rows || []).slice().sort((a, b) => b.k - a.k)[0];
  return `<section class="hero">
    <div class="hero-l">
      <h1 class="hero-h"><span class="hn">${c.share_over_raw[0]} z ${c.share_over_raw[1]}</span> umów kosztowało więcej, niż podpisano. <span class="hn">${t.share_over_raw[0]} z ${t.share_over_raw[1]}</span> skończyło się po terminie.</h1>
      <p class="hero-p">To nie szacunek ani model — to ${c.n} prawdziwych umów wodno-kanalizacyjnych, złożonych automatycznie z ${num(STATUS.counts.notices)} ogłoszeń w BZP. Typowo: <b>${pp(c.p50, 1)}</b> kosztu i <b>${pp(t.p50, 0)}</b> czasu; w co piątej umowie ponad <b>${pp(c.p80, 0)}</b> i <b>${pp(t.p80, 0)}</b>.${top ? ` Najczęstsza przyczyna zmian: ${esc(top.name.toLowerCase())}.` : ""}</p>
      <div class="hero-cta"><a class="btn primary big" href="#/nowa">Sprawdź swoją inwestycję</a><a class="btn big" href="#/zmiany">${(changes.length || STATUS.counts.changes) ? `Przejrzyj ${num(changes.length || STATUS.counts.changes)} zmian umów` : "Przejrzyj zmiany umów"}</a></div>
      <p class="small muted" style="margin-top:12px">Każda kropka to jedna umowa — kliknij, aby zobaczyć jej historię, oś czasu i źródła w BZP.</p>
    </div>
    <div class="hero-r"><svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Plan a rzeczywistość: koszt i czas 22 umów">${g}</svg>
      <div class="legend small"><span><i style="background:${VZ.late}"></i>drożej i dłużej</span><span><i style="background:${VZ.plan}"></i>jedno z dwóch</span><span><i style="background:${VZ.early}"></i>w planie</span><span><i class="hollow"></i>do weryfikacji</span><span>wielkość = wartość umowy</span></div></div>
  </section>`;
}
function flowStrip(c, changes, s) {
  const steps = [
    { n: c.notices, l: "ogłoszeń BZP", d: "pobrane i powiązane po identyfikatorach", go: "#/raporty" },
    { n: c.contracts, l: "umów", d: "koszt i termin: plan → wykonanie", go: "#/projekty" },
    { n: changes.length || c.changes || 0, l: "zmian umów", d: "przyczyna, podstawa z art. 455, koszt", go: "#/zmiany" },
    { n: c.events, l: "zdarzeń ryzyka", d: `${c.events_approved} zatwierdzonych przez eksperta`, go: "#/ekspert" },
    { n: c.analyses, l: "analiz nowych inwestycji", d: "prognoza P80, audyt umowy, termin dofinansowania", go: "#/nowa" },
  ];
  return `<section class="flow" aria-label="Jak działa Risk Miner">${steps.map((x, i) => `<a class="fs" href="${x.go}"><span class="fn">${num(x.n)}</span><span class="fl">${esc(x.l)}</span><span class="fd">${esc(x.d)}</span></a>${i < steps.length - 1 ? '<span class="fa" aria-hidden="true"></span>' : ""}`).join("")}</section>`;
}
function animateHero() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const h = $(".hero-r svg");
  if (h) { h.classList.add("anim"); requestAnimationFrame(() => requestAnimationFrame(() => h.classList.add("go"))); }
}

// ---- biblioteka zmian umów
VIEWS.changes = async () => {
  const [rows, st] = await Promise.all([api("/api/changes"), api("/api/status")]);
  RISK_NAMES = st.risk_names;
  const risks = [...new Set(rows.map((r) => r.risk_code).filter(Boolean))].sort();
  const bases = [...new Set(rows.map((r) => r.basis).filter(Boolean))].sort();
  $("#main").innerHTML = `<h1>Biblioteka zmian umów</h1>
    <p class="sub">Wszystkie zmiany umów z BZP w jednym miejscu: co się stało, na jakiej podstawie zmieniono umowę i ile to kosztowało. Wpisz problem, który Cię niepokoi (np. „grunt”, „służebność”, „Wody Polskie”, „pogoda”), i zobacz, jak poradzili sobie inni.</p>
    <div class="row filt"><input id="cq" class="grow" placeholder="Szukaj w przyczynach i opisach zmian…"><select id="cr"><option value="">każda kategoria ryzyka</option>${risks.map((r) => `<option value="${r}">${r} ${esc(RISK_NAMES[r] || "")}</option>`).join("")}</select><select id="cb"><option value="">każda podstawa prawna</option>${bases.map((b) => `<option>${esc(b)}</option>`).join("")}</select></div>
    <div id="csum" class="csum"></div><div id="clist"></div>`;
  const render = () => {
    const q = foldq($("#cq").value.trim()), rk = $("#cr").value, bs = $("#cb").value;
    const vis = rows.filter((r) => (!rk || r.risk_code === rk) && (!bs || r.basis === bs) && (!q || q.split(/\s+/).every((w) => foldq([r.cause, r.description, r.project, r.city, r.record_id, r.risk_name].join(" ")).includes(w))));
    const tot = vis.reduce((a, r) => a + (r.cost || 0), 0);
    const fs = vis.filter((r) => r.foreseen).length;
    $("#csum").innerHTML = `<span><b>${vis.length}</b> zmian w <b>${new Set(vis.map((r) => r.record_id)).size}</b> projektach</span><span>koszt zmian: <b>${pln(tot)}</b></span><span>przewidziane w umowie: <b>${vis.length ? Math.round((fs / vis.length) * 100) : 0}%</b></span>`;
    $("#clist").innerHTML = vis.map((r) => `<article class="chg">
      <div class="chg-h">${riskLabel(r.risk_code)}<span class="grow"></span>${r.cost ? `<span class="chg-c">+${pln(r.cost)}${r.cost_pct ? ` <span>(${pp(r.cost_pct, 1)} umowy)</span>` : ""}</span>` : ""}${r.delay_days ? `<span class="chg-c">+${r.delay_days} dni</span>` : ""}</div>
      <p class="chg-t">${esc((r.cause && r.cause.length > 25 ? r.cause : r.description || "").replace(/\[data zmiany.*?\]/, "").slice(0, 420))}</p>
      <div class="chg-m"><a href="#/projekt/${r.project_id}"><b>${esc(r.record_id)}</b> · ${esc(r.city || r.beneficiary || "")}</a><span class="pill ${r.foreseen ? "p-ok" : "p-warn"}" title="${esc(r.basis_meaning || "")}">${esc(r.basis || "podstawa nieokreślona")}${r.basis_meaning ? " — " + esc(r.basis_meaning) : ""}</span>${r.part ? `<span class="pill p-grey">część ${r.part}</span>` : ""}<span class="grow"></span>${r.url ? `<a href="${esc(r.url)}" target="_blank" rel="noopener" class="small">${esc(r.notice_number || "ogłoszenie")} ${r.notice_date ? "z " + dpl(r.notice_date) : ""} ↗</a>` : `<span class="small muted">${esc(r.notice_number || "")}</span>`}</div>
    </article>`).join("") || `<div class="empty">Brak zmian dla tego filtra. Wyczyść wyszukiwanie albo wybierz inną kategorię.</div>`;
  };
  ["cq", "cr", "cb"].forEach((id) => ($("#" + id).oninput = render));
  render();
};
const kpi = (v, l) => `<div class="card kpi"><div class="v">${num(v)}</div><div class="l">${esc(l)}</div></div>`;
function dropzone(el, cb) {
  el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("hover"); });
  el.addEventListener("dragleave", () => el.classList.remove("hover"));
  el.addEventListener("drop", (e) => { e.preventDefault(); el.classList.remove("hover"); if (e.dataTransfer.files.length) cb([...e.dataTransfer.files]); });
}
function historyTable(rows) {
  if (!rows || !rows.length) return `<div class="empty">Brak operacji.</div>`;
  return `<table><tr><th>Czas</th><th>Kto</th><th>Operacja</th><th>Obiekt</th><th>Komentarz</th></tr>${rows.map((r) => `<tr><td class="small">${dt(r.ts)}</td><td>${esc(r.actor)}</td><td class="code">${esc(r.action)}</td><td class="small">${esc(r.entity)} ${esc(r.entity_id || "")}</td><td class="small">${esc(r.comment || "")}</td></tr>`).join("")}</table>`;
}

// ------------------------------------------------------------ BAZA PRZYPADKÓW
VIEWS.projects = async () => {
  const rows = await api("/api/projects");
  $("#main").innerHTML = `
    <div class="row"><div class="grow"><h1>Baza przypadków</h1><p class="sub">Projekty z powiązanymi postępowaniami, ogłoszeniami, umowami, zmianami i zdarzeniami. Kliknij wiersz, aby zobaczyć przebieg i źródła.</p></div>
    <input id="q" placeholder="Szukaj: nazwa, gmina, kod…" style="width:280px"><a class="btn" href="/api/export/projects?format=csv">Eksport CSV</a></div>
    <div class="card" style="padding:0;overflow:auto"><table id="tbl"><thead><tr><th>Kod</th><th>Przedsięwzięcie</th><th>Odbiorca</th><th>Podsektor</th><th>Identyfikator</th><th>Wzbogacenie</th><th class="num">Ogł.</th><th class="num">Wartość umowy</th><th class="num">Odchylenie kosztu</th><th class="num">Opóźnienie</th><th class="num">Zdarzenia</th></tr></thead><tbody></tbody></table></div>`;
  const render = (f = "") => {
    const fl = f.toLowerCase();
    $("#tbl tbody").innerHTML = rows.filter((p) => !fl || (p.name + p.beneficiary_name + p.record_id + (p.voivodeship || "")).toLowerCase().includes(fl)).map((p) => `
      <tr class="click" onclick="location.hash='#/projekt/${p.id}'">
        <td class="code">${esc(p.record_id)}${p.is_exemplar ? ' <span class="pill p-acc">wzorcowy</span>' : ""}</td>
        <td><b>${esc(p.name)}</b><div class="small muted">${esc(p.status || "")} · ${esc(p.formula || "")}${p.length_km ? " · " + num(p.length_km, 2) + " km" : ""}</div></td>
        <td>${esc(p.beneficiary_name)}<div class="small muted">${esc(p.voivodeship || "")}</div></td>
        <td class="small">${esc(p.subsector_main || "")}</td>
        <td class="small">${esc(p.public_id_type || "")}<div class="code">${esc(p.public_id_normalized || p.public_id || "")}</div></td>
        <td>${enrichPill(p.enrich_status)}${p.n_links_proposed ? ` <span class="pill p-warn">${p.n_links_proposed} niepewne</span>` : ""}</td>
        <td class="num">${p.n_notices}</td>
        <td class="num">${pln(p.metrics.contract_value)}</td>
        <td class="num">${pct(p.metrics.cost_dev_pct)}</td>
        <td class="num">${days(p.metrics.delay_days)}</td>
        <td class="num">${p.n_events}${p.n_proposed ? ` <span class="pill p-warn">${p.n_proposed}</span>` : ""}</td>
      </tr>`).join("") || `<tr><td colspan="11"><div class="empty">Brak projektów — zaimportuj plik na pulpicie.</div></td></tr>`;
  };
  render();
  $("#q").oninput = (e) => render(e.target.value);
};
const enrichPill = (s) => {
  const m = { "wzbogacony": "p-ok", "nowy": "p-grey", "w toku": "p-info", "brak dopasowania": "p-warn", "błąd źródła": "p-bad", "błąd": "p-bad" };
  return `<span class="pill ${m[s] || "p-grey"}">${esc(s || "—")}</span>`;
};

// ------------------------------------------------------------ PROJEKT
let PTAB = "przebieg";
VIEWS.project = async (args) => {
  const pid = args[0];
  const d = await api(`/api/projects/${pid}`);
  RISK_NAMES = d.risk_names;
  rememberProject(d.project);
  const p = d.project, m = d.metrics;
  const nProp = d.events.filter((e) => e.status === "proposed").length;
  $("#main").innerHTML = `
    <a href="#/projekty" class="small">← baza przypadków</a>
    <h1 style="margin-top:6px">${esc(p.name)}</h1>
      <p class="sub">${esc(p.beneficiary_name)} · NIP ${esc(p.beneficiary_id || "—")} ${p.nip_valid ? '<span class="pill p-ok">NIP poprawny</span>' : '<span class="pill p-bad">NIP niezweryfikowany</span>'} · ${esc(p.city || "")}, ${esc(p.voivodeship || "")} · <span class="code">${esc(p.record_id)}</span> · ${esc(p.subsector_main || "")} · ${esc(p.formula || "")}${p.is_exemplar ? ' <span class="pill p-acc">wzorcowy</span>' : ""}</p>
      <div class="row" style="margin-bottom:14px">
        <button class="btn primary" id="b-enrich">Wzbogać z BZP/TED</button>
        <button class="btn" id="b-check">Sprawdź aktualizacje</button>
        <button class="btn" id="b-ex">${p.is_exemplar ? "Usuń oznaczenie wzorcowy" : "Oznacz jako wzorcowy"}</button>
        <a class="btn" href="/api/projects/${pid}/export">Eksport JSON</a>
        <a class="btn" href="/api/projects/${pid}/export?format=csv">Zdarzenia CSV</a>
      </div>
    <div id="job"></div>
    ${d.monitor.filter((x) => x.kind === "jakość danych").map((x) => `<div class="flag wysoki" style="margin:0 0 10px"><b>Problem w danych wejściowych</b> <span class="small">${esc(x.message)}</span></div>`).join("")}
    ${m.scope_note ? `<div class="hint" style="margin-bottom:10px">${esc(m.scope_note)}</div>` : ""}
    ${projectStory(d)}
    <div class="grid g6">
      ${kpi2(pln(m.contract_value), "wartość umów (brutto)", m.basis.contract_value.length ? "z ogłoszeń o wyniku" : "")}
      ${kpi2(pln(m.final_paid), "wypłacono wykonawcom", "ogłoszenie o wykonaniu umowy")}
      ${kpi2(pct(m.cost_dev_pct), "odchylenie kosztu", m.cost_dev_method || "brak danych")}
      ${kpi2(m.planned_duration_days ? num(m.planned_duration_days) + " dni" : "—", "termin umowny", m.signed_date ? `${m.signed_date} → ${m.planned_end_date || "?"}` : "")}
      ${kpi2(days(m.delay_days), "opóźnienie", m.delay_method || "brak danych")}
      ${kpi2(m.n_offers ?? "—", "liczba ofert", m.project_value ? "wartość projektu " + pln(m.project_value) : "")}
    </div>
    <div class="tabs" id="ptabs">
      ${["przebieg:Przebieg i źródła", "koszty:Koszty i terminy", "zdarzenia:Zdarzenia i ryzyka" + (nProp ? ` (${nProp})` : ""), "dokumenty:Dokumenty i braki", "powiazania:Powiązania", "dane:Dane projektu", "historia:Historia i monitoring"].map((t) => { const [k, l] = t.split(":"); return `<button data-t="${k}" class="${PTAB === k ? "active" : ""}">${esc(l)}</button>`; }).join("")}
    </div>
    <div id="ptab"></div>`;
  $$("#ptabs button").forEach((b) => (b.onclick = () => { PTAB = b.dataset.t; VIEWS.project(args); }));
  $("#b-enrich").onclick = async () => { const r = await guard(() => post(`/api/projects/${pid}/enrich`)); watchJob(r.job_id, $("#job"), () => VIEWS.project(args)); };
  $("#b-check").onclick = async () => { const r = await guard(() => post(`/api/projects/${pid}/check`)); toast(`Nowe ogłoszenia: ${r.new_notices}, nowe zdarzenia: ${r.new_events}`); VIEWS.project(args); };
  $("#b-ex").onclick = async () => { await guard(() => post("/api/exemplar", { entity: "project", id: pid, value: !p.is_exemplar })); VIEWS.project(args); };
  const T = $("#ptab");
  const tabs = {
    przebieg: () => tabPrzebieg(d, T),
    koszty: () => tabKoszty(d, T, args),
    zdarzenia: () => tabZdarzenia(d, T, args),
    dokumenty: () => tabDokumenty(d, T, args),
    powiazania: () => tabPowiazania(d, T, args),
    dane: () => tabDane(d, T, args),
    historia: () => tabHistoria(d, T),
  };
  (tabs[PTAB] || tabs.przebieg)();
};
const FEAT = { text: "treść", subsector: "podsektor", work_type: "rodzaj prac", formula: "formuła", value: "wartość", length: "długość", region: "region", exemplar: "wzorcowy" };
const kpi2 = (v, l, s) => `<div class="card kpi"><div class="v" style="font-size:20px">${esc(v)}</div><div class="l">${esc(l)}</div><div class="small muted">${esc(s || "")}</div></div>`;

function tabPrzebieg(d, T) {
  const p = d.project;
  if (!d.procurements.length) {
    T.innerHTML = `<div class="empty">Brak powiązanych postępowań. Uruchom „Wzbogać z BZP/TED”${d.links.some((l) => l.status === "proposed") ? " lub zweryfikuj kandydatów w zakładce Powiązania" : ""}.</div>${p.enrich_log ? `<h3>Dziennik ostatniego wzbogacenia</h3><pre class="log">${esc(p.enrich_log)}</pre>` : ""}`;
    return;
  }
  T.innerHTML = timelineSvg(d) + `
    <div class="node"><div class="t">Projekt: ${esc(p.name)}</div><div class="small muted">${esc(p.public_id_type)}: <span class="code">${esc(p.public_id)}</span> · źródło rekordu: ${srcLink(d.sources, p.source_id)}</div>
    ${p.annotation ? `<div class="quote">${esc(p.annotation)}</div>` : ""}</div>
    <div class="tree">${d.procurements.map((pr) => `
      <div class="node"><div class="row"><div class="grow"><div class="t">Postępowanie ${esc(pr.bzp_number || "")}</div><div>${esc(pr.title || "")}</div>
      <div class="small muted">${esc(pr.organization_name || "")} · CPV ${cpvShort(pr.cpv)} · publikacja ${dt(pr.publication_date)} ${pr.tender_id ? `· <span class="code">${esc(pr.tender_id)}</span>` : ""}</div></div>
      <div>${pr.link ? `${statusPill(pr.link.status)} ${confPill(pr.link.confidence)}` : ""}</div></div>
      ${pr.link ? `<div class="small muted">Podstawa dopasowania: ${pr.link.reasons.map(esc).join("; ")}</div>` : ""}
      <div class="tree">
        ${pr.notices.map((n) => `<div class="node"><div class="row"><div class="grow"><b>${esc(n.label)}</b> <span class="code">${esc(n.notice_number || "")}</span> <span class="small muted">${dt(n.publication_date)}</span></div><div>${n.link ? statusPill(n.link.status) + " " + confPill(n.link.confidence) : ""} <button class="btn sm" onclick="showNotice(${n.id})">treść</button> ${n.url ? `<a class="btn sm" href="${esc(n.url)}" target="_blank" rel="noopener">BZP ↗</a>` : ""}</div></div>
          ${n.link && n.link.reasons.length ? `<div class="small muted">${n.link.reasons.map(esc).join("; ")}</div>` : ""}</div>`).join("")}
        ${pr.contracts.map((c) => `<div class="node" style="background:#fbfdf9;${d.metrics.scope_part && c.part && Number(c.part) !== Number(d.metrics.scope_part) ? "opacity:.55" : ""}"><div class="t">Umowa${c.part ? " (część " + c.part + ")" : ""}: ${esc(c.contractor_name || "wykonawca nieznany")}${d.metrics.scope_part && c.part && Number(c.part) !== Number(d.metrics.scope_part) ? ' <span class="pill p-grey">poza zakresem rekordu</span>' : ""}</div>
          <div class="kv small" style="margin-top:6px"><div>Wartość umowy</div><div>${pln(c.value_gross)}</div><div>Data zawarcia</div><div>${esc(c.signed_date || "—")}</div><div>Termin umowny</div><div>${esc(c.planned_end_date || "—")}</div><div>Wykonanie</div><div>${esc(c.actual_end_date || "—")}</div><div>Wypłacono</div><div>${pln(c.final_paid)}</div><div>Należyte wykonanie</div><div>${esc(c.performed_properly || "—")}</div><div>Umowa zmieniona</div><div>${esc(c.changed || "—")}</div></div>
          ${c.changes.length ? `<h3>Zmiany umowy</h3>${c.changes.map((ch) => `<div class="quote"><b>${esc(ch.change_date || "")}</b> ${esc(ch.legal_basis || "")} — ${esc((ch.description || "").slice(0, 400))}</div>`).join("")}` : ""}</div>`).join("")}
      </div></div>`).join("")}</div>`;
}
window.showNotice = async (id) => {
  const n = await api(`/api/notices/${id}`);
  modal(`<h2>${esc(n.label)} ${esc(n.notice_number || "")}</h2><p class="small muted">Źródło: ${n.url ? `<a href="${esc(n.url)}" target="_blank">${esc(n.url)}</a>` : "—"} · pobrano ${dt(n.source && n.source.fetched_at)} · API: <span class="code">${esc(n.source && n.source.meta ? JSON.parse(n.source.meta).api_url || "" : "")}</span></p><pre class="log" style="max-height:60vh;background:#f7f9fb;color:#1b2430">${esc(n.text || "(brak treści)")}</pre>`);
};

function factTable(facts, sources, editable = true) {
  if (!facts.length) return `<div class="empty">Brak faktów.</div>`;
  const label = { project_value: "wartość przedsięwzięcia", funding: "dofinansowanie", contract_value: "wartość umowy / cena oferty wybranej", final_paid: "łącznie wypłacono", offer_min: "oferta najtańsza", offer_max: "oferta najdroższa", n_offers: "liczba ofert", signed_date: "data zawarcia umowy", planned_end_date: "termin umowny", planned_duration_days: "okres realizacji (dni)", actual_end_date: "data wykonania", performed_properly: "wykonana należycie", performed_on_time: "wykonana w terminie", contract_changed: "umowa zmieniona", penalties: "kary umowne", estimated_value_net: "wartość zamówienia (netto)", budget_amount: "kwota na sfinansowanie", contractor: "wykonawca" };
  return `<table><tr><th>Fakt</th><th>Wartość</th><th>VAT</th><th>Źródło i cytat</th><th>Pewność</th><th>Status</th>${editable ? "<th></th>" : ""}</tr>${facts.map((f) => `
    <tr><td>${esc(label[f.key] || f.key)}</td><td class="num">${f.unit === "PLN" ? pln(f.value_num) : esc(f.value_text ?? num(f.value_num))}</td><td class="small">${esc(f.vat || "")}</td>
    <td class="small">${srcLink(sources, f.source_id, f.page)}<div class="quote">${esc(f.quote || "")}</div></td><td>${confPill(f.confidence)}<div class="small muted">${esc(methodLabel(f.method))}</div></td><td>${statusPill(f.status)}</td>
    ${editable ? `<td><div class="row"><button class="btn sm ok" onclick="factDecide(${f.id},'approved')">✓</button><button class="btn sm" onclick="factEdit(${f.id},'${esc(String(f.value_text ?? f.value_num ?? ""))}')">popraw</button><button class="btn sm bad" onclick="factDecide(${f.id},'rejected')">✗</button></div></td>` : ""}</tr>`).join("")}</table>`;
}
window.factDecide = async (id, decision, value) => { await guard(() => post(`/api/facts/${id}/decide`, { decision, value }), "Zapisano decyzję"); router(); };
window.factEdit = (id, cur) => { const v = prompt("Poprawna wartość:", cur); if (v !== null) factDecide(id, "approved", v); };

function tabKoszty(d, T) {
  const m = d.metrics;
  T.innerHTML = `
    <div class="grid g2"><div class="layer calc"><span class="tag">Obliczenia</span>
      <div class="kv"><div>Wartość umów</div><div>${pln(m.contract_value)} <span class="small muted">(suma ${m.basis.contract_value.length} faktów)</span></div>
      <div>Wypłacono</div><div>${pln(m.final_paid)}</div><div>Odchylenie kosztu</div><div><b>${pct(m.cost_dev_pct)}</b> <span class="small muted">${esc(m.cost_dev_method || "")}</span></div>
      <div>Zawarcie → termin umowny</div><div>${esc(m.signed_date || "—")} → ${esc(m.planned_end_date || "—")} (${m.planned_duration_days ? num(m.planned_duration_days) + " dni" : "—"})</div>
      <div>Faktyczne wykonanie</div><div>${esc(m.actual_end_date || "—")} (${m.actual_duration_days ? num(m.actual_duration_days) + " dni" : "—"})</div>
      <div>Opóźnienie</div><div><b>${days(m.delay_days)}</b> <span class="small muted">${esc(m.delay_method || "")}</span></div>
      <div>Koszt na km</div><div>${pln(m.cost_per_km)} ${d.project.length_km ? `<span class="small muted">(${num(d.project.length_km, 2)} km)</span>` : ""}</div></div>
      <p class="small muted">Kwoty brutto porównywane z brutto; wartość zamówienia (netto) nie jest mieszana z cenami ofert. Wartość projektu ≠ wartość umowy z wykonawcą. Odrzucone przez eksperta fakty nie są brane pod uwagę.</p></div>
    <div class="layer src"><span class="tag">Dane źródłowe</span><p class="small muted">Fakty wyodrębnione z ogłoszeń i dokumentów. Zatwierdź, popraw lub odrzuć — wyliczenia aktualizują się automatycznie.</p></div></div>
    <h3>Fakty o kosztach i terminach</h3><div class="card" style="padding:0;overflow:auto">${factTable(d.facts, d.sources)}</div>`;
}

function eventCard(e, sources, opts = {}) {
  const imp = [e.cost_impact ? "koszt: " + pln(e.cost_impact) : "", e.delay_days ? "czas: " + days(e.delay_days) : ""].filter(Boolean).join(" · ");
  return `<div class="ev ${esc(e.status)}" id="ev-${e.id}"><div class="h">${riskLabel(e.risk_code)}${e.event_type ? ` <span class="pill p-grey code">${esc(e.event_type)}</span>` : ""}<b>${esc(e.title || "")}</b><span class="grow"></span>${confPill(e.confidence)}${statusPill(e.status)}${e.is_exemplar ? '<span class="pill p-acc">wzorcowe</span>' : ""}</div>
    ${opts.project ? `<div class="small"><a href="#/projekt/${e.project_id}">${esc(e.record_id)} — ${esc(e.pname)}</a></div>` : ""}
    <div class="quote">${esc(e.quote || e.snippet || "")}</div>
    <div class="small muted">Źródło: ${srcLink(sources, e.source_id, e.page) || "—"} · metoda: ${esc(methodLabel(e.method))}${e.rule_id ? ` (<span class="code">${esc(e.rule_id)}</span>)` : ""}${imp ? " · skutek: " + imp : ""}${e.cause ? " · przyczyna: " + esc(e.cause) : ""}${e.mitigation ? " · działanie: " + esc(e.mitigation) : ""}${e.reviewer ? ` · decyzja: ${esc(e.reviewer)} ${dt(e.reviewed_at)}` : ""}${e.review_comment ? " — " + esc(e.review_comment) : ""}</div>
    <div class="acts"><button class="btn sm ok" onclick="evDecide(${e.id},'approved')">Zatwierdź</button><button class="btn sm" onclick="evEdit(${e.id})">Popraw…</button><button class="btn sm bad" onclick="evDecide(${e.id},'rejected')">Odrzuć</button><button class="btn sm" onclick="markEx('event',${e.id},${e.is_exemplar ? "false" : "true"})">${e.is_exemplar ? "nie wzorcowe" : "wzorcowe"}</button></div></div>`;
}
window.evDecide = async (id, decision) => {
  const comment = decision === "rejected" ? prompt("Powód odrzucenia (opcjonalnie):") : null;
  if (comment === null && decision === "rejected") return;
  await guard(() => post(`/api/events/${id}/decide`, { decision, comment }), decision === "approved" ? "Zatwierdzono" : "Odrzucono");
  const el = $("#ev-" + id); if (el) { el.className = "ev " + decision; } refreshBadges();
};
window.markEx = async (entity, id, value) => { await guard(() => post("/api/exemplar", { entity, id, value }), "Zapisano"); router(); };
window.evEdit = async (id) => {
  const k = await api("/api/knowledge");
  const e = (window._EVENTS || {})[id] || {};
  modal(`<h2>Popraw i zatwierdź zdarzenie</h2>
    <div class="grid g2"><label class="f">Kategoria ryzyka<select id="e-risk">${k.risks.map((r) => `<option value="${r.code}" ${r.code === e.risk_code ? "selected" : ""}>${r.code} ${esc(r.name)}${r.status !== "approved" ? " (" + r.status + ")" : ""}</option>`).join("")}</select></label>
    <label class="f">Typ zdarzenia<select id="e-type"><option value="">— sygnał ryzyka —</option>${k.event_types.map((t) => `<option value="${t.code}" ${t.code === e.event_type ? "selected" : ""}>${t.code} ${esc(t.name)}</option>`).join("")}</select></label></div>
    <label class="f">Opis zdarzenia<input id="e-title" value="${esc(e.title || "")}"></label>
    <div class="grid g3"><label class="f">Skutek kosztowy (zł)<input id="e-cost" value="${esc(e.cost_impact ?? "")}"></label><label class="f">Opóźnienie (dni)<input id="e-delay" value="${esc(e.delay_days ?? "")}"></label><label class="f">Skuteczność działań<select id="e-eff"><option></option>${["skuteczne", "częściowo skuteczne", "nieskuteczne", "brak danych"].map((x) => `<option ${e.mitigation_effective === x ? "selected" : ""}>${x}</option>`).join("")}</select></label></div>
    <label class="f">Przyczyna<input id="e-cause" value="${esc(e.cause || "")}"></label>
    <label class="f">Działania zaradcze<input id="e-mit" value="${esc(e.mitigation || "")}"></label>
    <label class="f">Komentarz eksperta<input id="e-com"></label>
    <div class="row" style="margin-top:12px"><button class="btn primary" id="e-save">Zatwierdź z poprawkami</button></div>`);
  $("#e-save").onclick = async () => {
    const n = (v) => (v === "" ? null : Number(String(v).replace(/\s/g, "").replace(",", ".")));
    const changes = { risk_code: $("#e-risk").value, event_type: $("#e-type").value || null, title: $("#e-title").value, cost_impact: n($("#e-cost").value), delay_days: n($("#e-delay").value), cause: $("#e-cause").value || null, mitigation: $("#e-mit").value || null, mitigation_effective: $("#e-eff").value || null };
    await guard(() => post(`/api/events/${id}/decide`, { decision: "approved", changes, comment: $("#e-com").value }), "Zapisano");
    closeModal(); router();
  };
};

function tabZdarzenia(d, T, args) {
  window._EVENTS = Object.fromEntries(d.events.map((e) => [e.id, e]));
  const groups = {};
  d.events.forEach((e) => (groups[e.status === "rejected" ? "rejected" : e.status === "proposed" ? "proposed" : "approved"] = groups[e.status === "rejected" ? "rejected" : e.status === "proposed" ? "proposed" : "approved"] || []).push(e));
  T.innerHTML = `<div class="row"><div class="grow hint">Każde wskazanie ma postać: sygnał w dokumencie → możliwe zdarzenie → możliwy wpływ. Zdarzenia z ogłoszeń o zmianie/wykonaniu umowy to zdarzenia zmaterializowane; z SWZ/PFU/PPU — sygnały potencjalne.</div>
    <button class="btn" id="b-add">+ Dodaj zdarzenie ręcznie</button>${(groups.proposed || []).length ? `<button class="btn ok" id="b-all">Zatwierdź wszystkie wyliczone (${(groups.proposed || []).filter((e) => e.method === "computed").length})</button>` : ""}</div>
    <h3>Do weryfikacji (${(groups.proposed || []).length})</h3>${(groups.proposed || []).map((e) => eventCard(e, d.sources)).join("") || `<div class="empty">Brak.</div>`}
    <h3>Zatwierdzone (${(groups.approved || []).length})</h3>${(groups.approved || []).map((e) => eventCard(e, d.sources)).join("") || `<div class="empty">Brak.</div>`}
    <details><summary>Odrzucone (${(groups.rejected || []).length})</summary>${(groups.rejected || []).map((e) => eventCard(e, d.sources)).join("")}</details>`;
  const ball = $("#b-all");
  if (ball) ball.onclick = async () => { const ids = groups.proposed.filter((e) => e.method === "computed").map((e) => e.id); await guard(() => post("/api/events/bulk", { ids, decision: "approved", comment: "zatwierdzenie zbiorcze — zdarzenia wyliczone z danych BZP" }), "Zatwierdzono"); VIEWS.project(args); };
  $("#b-add").onclick = async () => {
    const k = await api("/api/knowledge");
    modal(`<h2>Nowe zdarzenie (wpis eksperta)</h2>
      <div class="grid g2"><label class="f">Kategoria ryzyka<select id="m-risk">${k.risks.filter((r) => r.status === "approved").map((r) => `<option value="${r.code}">${r.code} ${esc(r.name)}</option>`).join("")}</select></label>
      <label class="f">Typ zdarzenia<select id="m-type"><option value="">—</option>${k.event_types.map((t) => `<option value="${t.code}">${t.code} ${esc(t.name)}</option>`).join("")}</select></label></div>
      <label class="f">Opis<input id="m-title"></label><label class="f">Cytat / uzasadnienie<textarea id="m-quote" style="min-height:70px"></textarea></label>
      <div class="grid g3"><label class="f">Skutek kosztowy (zł)<input id="m-cost"></label><label class="f">Opóźnienie (dni)<input id="m-delay"></label><label class="f">Źródło (URL)<input id="m-url"></label></div>
      <label class="f">Przyczyna<input id="m-cause"></label><label class="f">Działania zaradcze<input id="m-mit"></label>
      <div class="row" style="margin-top:12px"><button class="btn primary" id="m-save">Zapisz</button></div>`);
    $("#m-save").onclick = async () => {
      const n = (v) => (v === "" ? null : Number(v.replace(/\s/g, "").replace(",", ".")));
      await guard(() => post(`/api/projects/${args[0]}/events`, { risk_code: $("#m-risk").value, event_type: $("#m-type").value || null, title: $("#m-title").value, quote: $("#m-quote").value, cost_impact: n($("#m-cost").value), delay_days: n($("#m-delay").value), source_url: $("#m-url").value || null, cause: $("#m-cause").value || null, mitigation: $("#m-mit").value || null }), "Dodano");
      closeModal(); VIEWS.project(args);
    };
  };
}

function tabDokumenty(d, T, args) {
  const pid = args[0];
  T.innerHTML = `<div class="grid g2"><div class="card"><h3>Dodaj dokumenty</h3>
      <p class="small muted">PDF (z warstwą tekstową${STATUS && STATUS.capabilities.ocr ? " lub skan — OCR" : ""}), DOCX, XLSX, CSV, HTML. System rozpozna typ dokumentu i fazę, wyodrębni fakty i zdarzenia, porówna je z dotychczasową wiedzą (potwierdzenia / sprzeczności).</p>
      <div class="drop" id="ddrop">Upuść pliki lub <label class="btn sm">wybierz<input type="file" id="dfile" multiple hidden></label></div>
      <div class="row" style="margin-top:10px"><input id="durl" class="grow" placeholder="lub adres URL dokumentu (BIP, NIK, KIO…)"><button class="btn" id="bdurl">Pobierz</button></div>
      <div id="dres"></div></div>
    <div class="card"><h3>Kompletność materiału</h3><table>${d.completeness.map((c) => `<tr><td>${c.status === "jest w paczce" ? '<span class="pill p-ok">jest</span>' : '<span class="pill p-warn">brak w paczce</span>'}</td><td><b>${esc(c.label)}</b><div class="small muted">${esc(c.phase)}${c.note ? " — " + esc(c.note) : ""}</div></td></tr>`).join("")}</table></div></div>
    <h3>Dokumenty projektu</h3>${d.documents.length ? `<div class="card" style="padding:0"><table><tr><th>Plik</th><th>Typ</th><th>Faza</th><th class="num">Strony</th><th>Źródło</th><th></th></tr>${d.documents.map((x) => `<tr><td>${esc(x.filename)}${x.ocr_used ? ' <span class="pill p-info">OCR</span>' : ""}</td><td>${esc(x.doc_type)}</td><td class="small">${esc(x.phase)}</td><td class="num">${x.n_pages}</td><td class="small">${srcLink(d.sources, x.source_id)}</td><td><button class="btn sm" onclick="showDoc(${x.id})">podgląd</button></td></tr>`).join("")}</table></div>` : `<div class="empty">Brak dokumentów.</div>`}`;
  const send = async (files) => {
    const out = [];
    for (const f of files) {
      const r = await guard(() => upload(`/api/projects/${pid}/documents`, f));
      out.push(`<div class="quote"><b>${esc(f.name)}</b> → ${esc(r.doc_type)}${r.duplicate ? " (już był w bazie)" : `: ${r.pages} str., ${r.new_events} nowych sygnałów, ${r.new_facts} faktów, ${r.confirmed.length} potwierdzeń, <b>${r.contradictions.length} sprzeczności</b>${r.bzp_numbers.length ? ", numery BZP: " + r.bzp_numbers.map(esc).join(", ") : ""}${r.warning ? " — " + esc(r.warning) : ""}`}</div>`);
    }
    $("#dres").innerHTML = out.join("") + `<button class="btn sm" onclick="router()">odśwież widok</button>`;
  };
  $("#dfile").onchange = (e) => send([...e.target.files]);
  dropzone($("#ddrop"), send);
  $("#bdurl").onclick = async () => { const url = $("#durl").value.trim(); if (!url) return; const r = await guard(() => post(`/api/projects/${pid}/fetch-url`, { url })); $("#dres").innerHTML = `<div class="quote">${esc(r.doc_type)}: ${r.new_events} sygnałów, ${r.contradictions.length} sprzeczności</div>`; };
}
window.showDoc = async (id) => {
  const d = await api(`/api/documents/${id}`);
  modal(`<h2>${esc(d.filename)}</h2><p class="small muted">${esc(d.doc_type)} · ${esc(d.phase)} · ${d.n_pages} str.</p>${d.pages.map((p) => `<h3>Strona ${p.page}</h3><pre class="log" style="background:#f7f9fb;color:#1b2430;max-height:none">${esc(p.text)}</pre>`).join("")}`);
};

function linkRow(l, opts = {}) {
  const c = l.candidate || {};
  return `<div class="ev ${l.status === "auto" ? "approved" : esc(l.status)}"><div class="h"><b>${esc(l.to_type.toUpperCase())}: <span class="code">${esc(l.to_ref)}</span></b>${opts.project ? ` <a href="#/projekt/${l.project_id}" class="small">${esc(l.record_id)} — ${esc(l.pname)}</a>` : ""}<span class="grow"></span>${confPill(l.confidence)} ${statusPill(l.status)}</div>
    ${c.title ? `<div>${esc(c.title)} <span class="small muted">${esc(c.organization_name || c.buyer || "")} · ${dt(c.publication_date)}</span> ${c.url ? `<a class="small" href="${esc(c.url)}" target="_blank">otwórz ↗</a>` : ""}</div>` : ""}
    <div class="small muted">Metoda: ${esc(methodLabel(l.method))} · Przesłanki: ${(l.reasons || []).map(esc).join("; ")}</div>
    ${l.review_comment ? `<div class="small">Komentarz: ${esc(l.review_comment)}</div>` : ""}
    <div class="acts"><button class="btn sm ok" onclick="linkDecide(${l.id},'approved')">Potwierdź powiązanie</button><button class="btn sm bad" onclick="linkDecide(${l.id},'rejected')">Odrzuć</button></div></div>`;
}
window.linkDecide = async (id, decision) => {
  const comment = decision === "rejected" ? prompt("Powód odrzucenia (opcjonalnie):") : "";
  if (comment === null) return;
  await guard(() => post(`/api/links/${id}/decide`, { decision, comment }), "Zapisano decyzję");
  router();
};
function tabPowiazania(d, T) {
  T.innerHTML = `<div class="hint">Podstawowa metoda łączenia: wspólne identyfikatory (numer ogłoszenia BZP/TED, tenderId/OCID, NIP). Gdy brak klucza, system dopasowuje po zamawiającym, przedmiocie, miejscu i datach — i pokazuje podstawę oraz poziom pewności. Odrzucenie powiązania usuwa z bazy dane z niego wyprowadzone.</div>
    ${d.links.map((l) => linkRow(l)).join("") || `<div class="empty">Brak powiązań.</div>`}`;
}
function tabDane(d, T, args) {
  const p = d.project;
  T.innerHTML = `<div class="grid g2"><div class="card"><h3>Klasyfikacja (edytowalna)</h3>
    <label class="f">Podsektor główny<select id="d-sub">${["Sieć wodociągowa", "Kanalizacja sanitarna", "Oczyszczalnia ścieków", "Uzdatnianie i zaopatrzenie w wodę", "Kanalizacja deszczowa i retencja", "Inne obiekty wod-kan"].map((s) => `<option ${s === p.subsector_main ? "selected" : ""}>${s}</option>`).join("")}</select></label>
    <label class="f">Podsektory dodatkowe<input id="d-subx" value="${esc((p.subsectors_extra || []).join(", "))}"></label>
    <label class="f">Rodzaj prac<input id="d-wt" value="${esc(p.work_type || "")}"></label>
    <label class="f">Formuła<select id="d-form">${["tradycyjna (wg dokumentacji zamawiającego)", "zaprojektuj i wybuduj"].map((s) => `<option ${s === p.formula ? "selected" : ""}>${s}</option>`).join("")}</select></label>
    <label class="f">Długość sieci (km)<input id="d-len" value="${esc(p.length_km ?? "")}"></label>
    <label class="f">Opis<textarea id="d-desc">${esc(p.description || "")}</textarea></label>
    <button class="btn primary" id="d-save" style="margin-top:8px">Zapisz</button></div>
    <div class="card"><h3>Rekord źródłowy</h3><div class="kv small">${["record_id", "public_id_type", "public_id", "beneficiary_type", "teryt", "scope", "theme", "order_type", "legal_regime", "currency", "status", "record_source", "record_date", "record_version"].map((k) => `<div>${k}</div><div>${esc(p[k] ?? "—")}</div>`).join("")}</div>
    <p class="small">Źródło: ${srcLink(d.sources, p.source_id)}</p></div></div>`;
  $("#d-save").onclick = async () => {
    await guard(() => post(`/api/projects/${args[0]}/update`, { subsector_main: $("#d-sub").value, subsectors_extra: $("#d-subx").value.split(",").map((s) => s.trim()).filter(Boolean), work_type: $("#d-wt").value, formula: $("#d-form").value, length_km: $("#d-len").value || null, description: $("#d-desc").value }), "Zapisano");
    VIEWS.project(args);
  };
}
function tabHistoria(d, T) {
  T.innerHTML = `<h3>Zdarzenia monitoringu</h3>${d.monitor.length ? `<div class="card" style="padding:0"><table>${d.monitor.map((m) => `<tr><td class="small">${dt(m.created_at)}</td><td><span class="pill ${m.kind === "sprzeczność" || m.kind === "istotna zmiana" ? "p-warn" : "p-grey"}">${esc(m.kind)}</span></td><td>${esc(m.message)}</td></tr>`).join("")}</table></div>` : `<div class="empty">Brak.</div>`}
    <h3>Historia zmian projektu</h3><div class="card" style="padding:0">${historyTable(d.history)}</div>
    ${d.project.enrich_log ? `<h3>Dziennik pobierania danych</h3><pre class="log">${esc(d.project.enrich_log)}</pre>` : ""}`;
}

// ------------------------------------------------------------ PANEL EKSPERTA
let RTAB = "events";
VIEWS.review = async () => {
  const q = await api("/api/review/queue");
  RISK_NAMES = q.risk_names;
  window._EVENTS = Object.fromEntries(q.events.map((e) => [e.id, e]));
  const srcs = {};
  q.events.forEach((e) => { if (e.source) srcs[e.source.id] = e.source; });
  $("#main").innerHTML = `<h1>Panel eksperta</h1><p class="sub">Żaden wniosek AI ani reguły nie trafia do bazy doświadczeń bez decyzji eksperta. Decyzje (z historią) korygują pewność reguł w kolejnych analizach.</p>
    <div class="tabs" id="rtabs">${[["events", `Zdarzenia (${q.events.length})`], ["links", `Niepewne powiązania (${q.links.length})`], ["facts", `Fakty (${q.facts.length})`], ["contr", `Sprzeczności (${q.contradictions.length})`], ["cats", `Nowe kategorie (${q.categories.length})`], ["hist", "Historia decyzji"]].map(([k, l]) => `<button data-t="${k}" class="${RTAB === k ? "active" : ""}">${l}</button>`).join("")}</div><div id="rt"></div>`;
  $$("#rtabs button").forEach((b) => (b.onclick = () => { RTAB = b.dataset.t; VIEWS.review(); }));
  const T = $("#rt");
  if (RTAB === "events") {
    const risks = [...new Set(q.events.map((e) => e.risk_code).filter(Boolean))].sort();
    T.innerHTML = `<div class="row sticky-actions"><select id="fr" style="max-width:340px"><option value="">wszystkie kategorie</option>${risks.map((r) => `<option value="${r}">${r} ${esc(RISK_NAMES[r] || "")}</option>`).join("")}</select>
      <select id="fm"><option value="">każda metoda</option><option value="computed">wyliczone z danych</option><option value="rule">reguły</option><option value="llm">model językowy</option></select>
      <label class="small">min. pewność <input id="fc" type="number" min="0" max="100" value="0" style="width:70px">%</label><span class="grow"></span><button class="btn ok" id="bulk">Zatwierdź widoczne</button><button class="btn bad" id="bulkr">Odrzuć widoczne</button></div><div id="evl"></div>`;
    const visible = () => q.events.filter((e) => (!$("#fr").value || e.risk_code === $("#fr").value) && (!$("#fm").value || e.method === $("#fm").value) && (e.confidence || 0) * 100 >= Number($("#fc").value || 0));
    const render = () => ($("#evl").innerHTML = visible().map((e) => eventCard(e, srcs, { project: true })).join("") || `<div class="empty">Kolejka pusta.</div>`);
    ["fr", "fm", "fc"].forEach((id) => ($("#" + id).oninput = render));
    render();
    const bulk = async (decision) => { const ids = visible().map((e) => e.id); if (!ids.length || !confirm(`${decision === "approved" ? "Zatwierdzić" : "Odrzucić"} ${ids.length} zdarzeń?`)) return; await guard(() => post("/api/events/bulk", { ids, decision, comment: "decyzja zbiorcza" }), "Zapisano"); VIEWS.review(); };
    $("#bulk").onclick = () => bulk("approved");
    $("#bulkr").onclick = () => bulk("rejected");
  } else if (RTAB === "links") {
    T.innerHTML = q.links.map((l) => linkRow(l, { project: true })).join("") || `<div class="empty">Brak niepewnych powiązań.</div>`;
  } else if (RTAB === "facts") {
    T.innerHTML = `<div class="card" style="padding:0;overflow:auto">${factTable(q.facts.map((f) => ({ ...f, key: f.key + " — " + f.record_id })), {})}</div>`;
  } else if (RTAB === "contr") {
    T.innerHTML = q.contradictions.map((c) => `<div class="ev proposed"><div class="h"><b>${esc(c.record_id)}</b><span class="grow"></span><span class="pill p-warn">sprzeczność</span></div><div>${esc(c.message)}</div><div class="acts"><a class="btn sm" href="#/projekt/${c.project_id}">otwórz projekt</a><button class="btn sm" onclick="ack(${c.id})">rozstrzygnięte</button></div></div>`).join("") || `<div class="empty">Brak sprzeczności.</div>`;
  } else if (RTAB === "cats") {
    T.innerHTML = q.categories.map((c) => `<div class="ev proposed"><div class="h"><span class="code pill p-grey">${esc(c.code)}</span><b>${esc(c.name)}</b><span class="grow"></span><span class="small muted">zaproponowane przez: ${esc(c.proposed_by)}</span></div><div class="small">${esc(c.effects || "")}</div><div class="acts"><button class="btn sm ok" onclick="catDecide('${c.code}','approved')">Dodaj do katalogu</button><button class="btn sm bad" onclick="catDecide('${c.code}','rejected')">Odrzuć</button></div></div>`).join("") || `<div class="empty">Brak propozycji nowych kategorii (model językowy proponuje je, gdy zdarzenie nie pasuje do katalogu).</div>`;
  } else {
    const h = await api("/api/history?limit=300");
    T.innerHTML = `<div class="card" style="padding:0">${historyTable(h.filter((r) => /event\.|link\.|fact\.|risk\.|knowledge|exemplar/.test(r.action)))}</div>`;
  }
};
window.ack = async (id) => { await guard(() => post(`/api/monitor/events/${id}/ack`)); router(); };
window.catDecide = async (code, decision) => { await guard(() => post(`/api/knowledge/risk/${code}/decide`, { decision }), "Zapisano"); router(); };

// ------------------------------------------------------------ NOWA INWESTYCJA
const EXAMPLE = `Gmina planuje budowę sieci kanalizacji sanitarnej grawitacyjno-tłocznej o długości ok. 6,5 km wraz z dwiema przepompowniami ścieków i przyłączami do granic 140 nieruchomości w miejscowościach poza aglomeracją. Ścieki będą odprowadzane do istniejącej oczyszczalni. Trasa przebiega w pasie dróg gminnych i powiatowych, częściowo przez grunty prywatne; przewidziano przekroczenie cieku i drogi wojewódzkiej przewiertem. Szacowana wartość inwestycji: 7 800 000 zł brutto. Planowana formuła: zaprojektuj i wybuduj, termin realizacji 14 miesięcy. Inwestycja w województwie wielkopolskim. Ogłoszenie przetargu planowane na styczeń 2027. Umowa o dofinansowanie wymaga zakończenia rzeczowego projektu do 30.06.2028.`;
VIEWS.new = async (args) => {
  const list = await api("/api/analyses");
  let aid = args[0] && /^\d+$/.test(args[0]) ? Number(args[0]) : null;
  let existing = aid ? await api(`/api/analyses/${aid}`) : null;
  $("#main").innerHTML = `<h1>Analiza nowej inwestycji</h1><p class="sub no-print">Opisz planowany projekt językiem naturalnym lub wgraj jego wstępne dokumenty (koncepcja, PFU, studium). System znajdzie najbardziej zbliżone zakończone inwestycje, wyjaśni podobieństwo i przedstawi prognozę, flagi, zagadnienia do analizy i propozycje zapisów.</p>
    <div class="grid g3 no-print"><div class="card" style="grid-column:span 2">
      <label class="f">Nazwa analizy<input id="a-title" value="${esc(existing ? existing.title : "Planowana inwestycja")}"></label>
      <label class="f" style="margin-top:8px">Opis inwestycji<textarea id="a-text" style="min-height:150px">${esc(existing ? existing.input_text : "")}</textarea></label>
      <div class="row small" style="margin-top:4px"><button class="btn sm" id="a-ex">wstaw przykładowy opis</button><span class="muted">Parametry poniżej są opcjonalne — system odczyta je z opisu, jeśli je zawiera.</span></div>
      <div class="grid g3" style="margin-top:8px"><label class="f">Szacowana wartość (zł)<input id="a-val"></label><label class="f">Długość sieci (km)<input id="a-len"></label><label class="f">Województwo<input id="a-voi"></label></div>
      <div class="grid g2" style="margin-top:8px"><label class="f">Planowane ogłoszenie przetargu<input id="a-start" type="date"></label><label class="f">Termin zakończenia z umowy o dofinansowanie<input id="a-dl" type="date"></label></div>
      <div class="drop" id="adrop" style="margin-top:10px">Wstępne dokumenty (opcjonalnie): upuść pliki lub <label class="btn sm">wybierz<input type="file" id="afile" multiple hidden></label><div id="adocs" class="small"></div></div>
      <div class="row" style="margin-top:12px"><button class="btn primary" id="a-run">Analizuj</button><span id="a-st" class="muted small"></span></div>
    </div><div class="card"><h3>Poprzednie analizy</h3>${list.length ? list.map((a) => `<div><a href="#/analiza/${a.id}">#${a.id} ${esc(a.title)}</a> <span class="small muted">${dt(a.created_at)}</span></div>`).join("") : `<p class="muted">Brak.</p>`}</div></div>
    <div id="a-res"></div>`;
  const files = [];
  const showDocs = () => ($("#adocs").innerHTML = files.map((f) => "• " + esc(f.name)).join("<br>") + (existing && existing.documents.length ? "<br>" + existing.documents.map((d) => "• " + esc(d.filename) + " (zapisany)").join("<br>") : ""));
  showDocs();
  $("#afile").onchange = (e) => { files.push(...e.target.files); showDocs(); };
  dropzone($("#adrop"), (fs) => { files.push(...fs); showDocs(); });
  $("#a-ex").onclick = () => ($("#a-text").value = EXAMPLE);
  $("#a-run").onclick = async () => {
    $("#a-st").textContent = "Analiza w toku…";
    if (!aid) { const r = await guard(() => post("/api/analyses", { title: $("#a-title").value, text: $("#a-text").value })); aid = r.analysis_id; }
    for (const f of files.splice(0)) await guard(() => upload(`/api/analyses/${aid}/documents`, f));
    const r = await guard(() => post(`/api/analyses/${aid}/run`, { title: $("#a-title").value, text: $("#a-text").value, value: $("#a-val").value, length_km: $("#a-len").value, voivodeship: $("#a-voi").value, tender_start: $("#a-start").value, deadline: $("#a-dl").value }));
    $("#a-st").textContent = "";
    history.replaceState(null, "", `#/analiza/${aid}`);
    renderAnalysis(r.result, aid);
  };
  if (existing && existing.result) renderAnalysis(existing.result, aid);
};

function rangeViz(st, fmt) {
  if (!st || !st.n) return `<span class="muted">brak danych</span>`;
  const lo = Math.min(st.min, 0), hi = Math.max(st.max, 0.0001);
  const pos = (v) => ((v - lo) / (hi - lo || 1)) * 100;
  return `<div class="range" title="min ${fmt(st.min)} · p25 ${fmt(st.p25)} · mediana ${fmt(st.median)} · p75 ${fmt(st.p75)} · max ${fmt(st.max)}"><div class="iqr" style="left:${pos(st.p25)}%;width:${Math.max(1, pos(st.p75) - pos(st.p25))}%"></div><div class="med" style="left:${pos(st.median)}%"></div></div>
    <div class="small muted">min ${fmt(st.min)} · p25 ${fmt(st.p25)} · <b>mediana ${fmt(st.median)}</b> · p75 ${fmt(st.p75)} · max ${fmt(st.max)} · <b>n=${st.n}</b></div>`;
}
function renderAnalysis(r, aid) {
  const f = r.input.features, src = r.dane_zrodlowe, calc = r.obliczenia, w = r.wnioski, fc = calc.forecast;
  const lvl = (l) => (l || "").replace(/\s|–/g, "").replace("ż", "z");
  const emptyDb = !(r.dane_zrodlowe.all_ranked || []).length;
  $("#a-res").innerHTML = `${emptyDb ? `<div class="flag wysoki" style="margin-top:18px"><b>Baza przypadków jest pusta — nie ma z czym porównać.</b><div class="small">Najpierw wczytaj dane: Pulpit → „Demo na prawdziwych danych BZP (22 projekty, offline)”, poczekaj ok. 5 s, potem wróć tutaj i kliknij „Analizuj” jeszcze raz.</div><div class="row" style="margin-top:8px"><a class="btn primary" href="#/">Przejdź do pulpitu</a></div></div>` : ""}
    <div class="row" style="margin-top:18px"><h2 class="grow" style="margin:0">Wynik: ${esc(r.title)}</h2><button class="btn" onclick="window.print()">Drukuj kartę ryzyka</button><a class="btn" href="/api/analyses/${aid}/export">Eksport JSON</a><a class="btn" href="/api/analyses/${aid}/export?format=csv">Eksport CSV</a></div>
    <div class="card" style="margin-top:10px"><div class="kv small"><div>Podsektor główny</div><div><b>${esc(f.subsector_main)}</b> ${(f.subsectors_extra || []).length ? "· dodatkowe: " + f.subsectors_extra.map(esc).join(", ") : ""}</div><div>Rodzaj prac / formuła</div><div>${esc(f.work_type)} · ${esc(f.formula)}</div><div>Wartość / długość / region</div><div>${pln(f.value)} · ${f.length_km ? num(f.length_km, 2) + " km" : "—"} · ${esc(f.voivodeship || "—")}</div></div></div>
    ${verdictCard(r)}
    ${deadlineBlock(calc.reference)}
    <details class="more"><summary>Szczegóły: najbardziej podobne projekty (A) i statystyki grupy (B)</summary>
    <div class="layer src" style="margin-top:14px"><span class="tag">A. Dane źródłowe — grupa porównawcza</span>
      ${src.similar.length ? src.similar.map((s) => `<div class="node"><div class="row"><div class="grow"><a href="#/projekt/${s.project_id}"><b>${esc(s.name)}</b></a><div class="small muted">${esc(s.record_id)} · ${esc(s.beneficiary)} · ${esc(s.voivodeship || "")} · ${esc(s.subsector || "")} · ${esc(s.status || "")}</div></div>
        <div style="width:160px"><div class="small">podobieństwo ${Math.round(s.score * 100)}%</div><div class="bar"><i style="width:${s.score * 100}%"></i></div></div></div>
        <div class="small" style="margin-top:4px">${s.explanation.filter((e) => e.contribution > 0 || e.feature === "exemplar").slice(0, 5).map((e) => `<span class="pill p-grey" title="${esc(e.why)}">${esc(FEAT[e.feature] || e.feature)} +${Math.round(e.contribution * 100)} pkt</span> ${esc(e.why)}`).join("<br>")}</div>
        <div class="small muted" style="margin-top:4px">wartość umowy ${pln(s.metrics.contract_value)} · odchylenie kosztu ${pct(s.metrics.cost_dev_pct)} · opóźnienie ${days(s.metrics.delay_days)} · termin umowny ${s.metrics.planned_duration_days ? num(s.metrics.planned_duration_days) + " dni" : "—"} · ofert: ${s.metrics.n_offers ?? "—"}</div></div>`).join("") : `<div class="empty">Brak podobnych projektów w bazie.</div>`}
      ${src.risk_examples.length ? `<h3>Udokumentowane zdarzenia w grupie porównawczej</h3>${src.risk_examples.map((rk) => `<details><summary>${esc(rk.code)} ${esc(rk.name)} — ${rk.n_projects} proj. (${rk.approved} zatw., ${rk.proposed} do weryf.)${rk.cost ? " · skutki kosztowe " + pln(rk.cost) : ""}${rk.delay ? " · " + days(rk.delay) : ""}</summary>${rk.examples.map((e) => `<div class="quote"><b>${esc(e.project)}</b> ${statusPill(e.status)} ${esc(e.title)}<br>${esc(e.quote)} ${e.source_url ? `<a href="${esc(e.source_url)}" target="_blank">źródło ↗</a>` : ""}</div>`).join("")}</details>`).join("")}` : ""}
    </div>
    <div class="layer calc" style="margin-top:14px"><span class="tag">B. Obliczenia</span>
      <div class="grid g2"><div><h3>Odchylenie kosztu (zakończone, podobne)</h3>${rangeViz(calc.stats.cost_dev_pct, pct)}</div><div><h3>Opóźnienie względem terminu umownego</h3>${rangeViz(calc.stats.delay_days, days)}</div>
      <div><h3>Termin umowny w grupie</h3>${rangeViz(calc.stats.planned_duration_days, (v) => num(v) + " dni")}</div><div><h3>Koszt na km sieci</h3>${rangeViz(calc.stats.cost_per_km, pln)}</div></div>
      <p class="small muted">${esc(fc.sample_note)} Prognoza kosztu i czasu — w części B2 (cała baza ważona podobieństwem).</p>
      ${fc.cost_by_length ? `<div class="kv"><div>Kontrola krzyżowa: koszt z długości sieci</div><div><b>${pln(fc.cost_by_length[0])} – ${pln(fc.cost_by_length[2])}</b> (mediana ${pln(fc.cost_by_length[1])})<div class="small muted">${esc(fc.cost_by_length_method)}</div></div></div>` : ""}
    </div>
    </details>
    ${referenceBlock(calc.reference, f)}
    <div class="layer calc" style="margin-top:14px;overflow:auto"><span class="tag">B3. Rejestr ryzyk z wyceną</span>
      <p class="small">Ryzyka, które <b>faktycznie</b> wystąpiły w podobnych umowach (przyczyny zmian umów z formularzy BZP, dokumenty, wpisy ekspertów), z prawdopodobieństwem i skutkiem. Wartość oczekiwana = prawdopodobieństwo × mediana skutku × wartość tej inwestycji.</p>
      ${registerTable(calc.register, f.value)}${basesBars(calc.change_bases)}</div>
    <div class="layer concl" style="margin-top:14px"><span class="tag">C. Wnioski systemu (do oceny eksperta)</span>
      <p class="small muted">${esc(w.method_note)}</p>
      ${w.narrative_llm ? `<div class="hint"><b>Podsumowanie (model językowy, na podstawie danych A i B):</b><br>${esc(w.narrative_llm)}</div>` : ""}
      <h3>Czerwone flagi</h3>${w.flags.map((x) => `<div class="flag ${lvl(x.level)}"><b>${esc(x.risk_code)} ${esc(x.name || "")}</b> <span class="pill p-grey">${esc(x.level)}</span> <span class="small muted">podstawa: ${esc(x.basis)}</span><div class="small">${esc(x.why)}</div></div>`).join("") || `<div class="empty">Brak flag.</div>`}
      ${clauseAudit(w.clause_audit)}
      <h3>Rekomendowane działania i propozycje zapisów umownych</h3>${w.recommendations.map((x) => `<details open><summary>${esc(x.risk_code)} ${esc(x.name || "")}</summary><div class="grid g3 small"><div><b>Działania</b><ul>${x.mitigations.map((m) => `<li>${esc(m)}</li>`).join("")}</ul></div><div><b>Propozycje zapisów</b><ul>${x.clauses.map((m) => `<li>${esc(m)}</li>`).join("")}</ul></div><div><b>Sprawdź przed uruchomieniem</b><ul>${x.checks.map((m) => `<li>${esc(m)}</li>`).join("")}</ul></div></div></details>`).join("")}
      <h3>Zagadnienia do analizy (lista kontrolna przygotowania inwestycji)</h3>${w.checklist.map((c) => `<div class="chk">${c.covered ? '<span class="pill p-ok">jest</span>' : '<span class="pill p-warn">brak</span>'}<div>${esc(c.text)} <span class="small muted">(${esc(c.ref)})</span></div></div>`).join("")}
      ${w.signals_in_input.length ? `<h3>Sygnały ryzyka w opisie</h3>${w.signals_in_input.slice(0, 10).map((s) => `<div class="quote"><b>${esc(s.risk_code)}</b> ${esc(s.quote)}</div>`).join("")}` : ""}
    </div>`;
}

// ------------------------------------------------------------ MONITORING
VIEWS.monitor = async () => {
  const [ev, cfg] = await Promise.all([api("/api/monitor/events"), api("/api/config")]);
  $("#main").innerHTML = `<h1>Monitoring inwestycji</h1><p class="sub">Dla projektów w toku system wyszukuje nowe ogłoszenia (wynik, zmiana umowy, wykonanie) i rozpoznaje zmiany istotne dla trwającej inwestycji. Nowe dokumenty powodują ponowną analizę (potwierdzenia, sprzeczności, nowe zdarzenia).</p>
    <div class="card"><div class="row"><button class="btn primary" id="m-run">Sprawdź teraz</button><span class="muted small">Harmonogram: ${cfg.monitor.interval_minutes ? `co ${cfg.monitor.interval_minutes} min` : "wyłączony (ustaw monitor.interval_minutes w config.json)"} · ${cfg.monitor.only_unfinished ? "tylko projekty niezakończone (gdy brak — wszystkie)" : "wszystkie projekty"}</span></div><div id="job"></div></div>
    <h2>Zdarzenia</h2><div class="card" style="padding:0">${ev.length ? `<table><tr><th>Czas</th><th>Projekt</th><th>Rodzaj</th><th>Opis</th><th></th></tr>${ev.map((m) => `<tr style="${m.acknowledged ? "opacity:.55" : ""}"><td class="small">${dt(m.created_at)}</td><td><a href="#/projekt/${m.project_id}">${esc(m.record_id || "")}</a></td><td><span class="pill ${/sprzecz|istotna/.test(m.kind) ? "p-warn" : "p-grey"}">${esc(m.kind)}</span></td><td>${esc(m.message)}</td><td>${m.acknowledged ? "" : `<button class="btn sm" onclick="ack(${m.id})">przyjęte</button>`}</td></tr>`).join("")}</table>` : `<div class="empty">Brak zdarzeń monitoringu.</div>`}</div>`;
  $("#m-run").onclick = async () => { const r = await guard(() => post("/api/monitor/check-all")); watchJob(r.job_id, $("#job"), () => VIEWS.monitor()); };
};

// ------------------------------------------------------------ WIEDZA EKSPERCKA
VIEWS.knowledge = async () => {
  const k = await api("/api/knowledge");
  $("#main").innerHTML = `<h1>Wiedza ekspercka</h1><p class="sub">Katalog ryzyk, typy zdarzeń, podsektory i lista kontrolna — wszystko edytowalne bez zmian w kodzie. Wzorce to wyrażenia regularne stosowane do tekstu bez polskich znaków (np. <span class="code">opoznien</span>).</p>
    <div class="row"><button class="btn primary" id="k-new">+ Nowa kategoria ryzyka</button><button class="btn" id="k-et">+ Nowy typ zdarzenia</button><span class="grow"></span><button class="btn bad" id="k-reset">Przywróć wiedzę startową</button></div>
    <h2>Katalog ryzyk</h2><div class="card" style="padding:0"><table><tr><th>Kod</th><th>Nazwa i efekty</th><th class="num">Wzorce</th><th class="num">Działania</th><th class="num">Zapisy</th><th>Status</th><th></th></tr>${k.risks.map((r) => `<tr><td class="code">${esc(r.code)}</td><td><b>${esc(r.name)}</b><div class="small muted">${esc(r.effects || "")}</div></td><td class="num">${r.patterns.length}</td><td class="num">${r.mitigations.length}</td><td class="num">${r.clauses.length}</td><td>${statusPill(r.status)}</td><td><button class="btn sm" onclick='editRisk(${JSON.stringify(r.code)})'>edytuj</button></td></tr>`).join("")}</table></div>
    <h2>Typy zdarzeń</h2><div class="card" style="padding:0"><table><tr><th>Kod</th><th>Nazwa</th><th>Kategorie</th><th>Wzorce</th><th></th></tr>${k.event_types.map((t) => `<tr><td class="code">${esc(t.code)}</td><td>${esc(t.name)}</td><td>${t.risk_codes.map(esc).join(", ")}</td><td class="code small">${t.patterns.map(esc).join("<br>")}</td><td><button class="btn sm" onclick='editET(${JSON.stringify(t.code)})'>edytuj</button></td></tr>`).join("")}</table></div>
    <div class="grid g2"><div><h2>Opis sektora</h2><div class="card"><textarea id="k-sector">${esc(k.sector_description)}</textarea><button class="btn" id="k-sector-save">Zapisz</button></div></div>
    <div><h2>Wagi podobieństwa</h2><div class="card small">${Object.entries(k.weights).map(([a, b]) => `<div class="row"><span style="width:120px">${esc(a)}</span><div class="bar grow"><i style="width:${b * 200}%"></i></div><span>${b}</span></div>`).join("")}<p class="muted">Ustawiane w config.json → analysis.weights.</p></div></div></div>
    <h2>Podsektory i lista kontrolna (JSON)</h2><div class="grid g2"><div class="card"><textarea id="k-subs" class="code" style="min-height:220px">${esc(JSON.stringify(k.subsectors, null, 1))}</textarea><button class="btn" id="k-subs-save">Zapisz podsektory</button></div><div class="card"><textarea id="k-chk" class="code" style="min-height:220px">${esc(JSON.stringify(k.checklist, null, 1))}</textarea><button class="btn" id="k-chk-save">Zapisz listę kontrolną</button></div></div>`;
  window._K = k;
  $("#k-new").onclick = () => editRisk(null);
  $("#k-et").onclick = () => editET(null);
  $("#k-reset").onclick = async () => { if (confirm("Przywrócić katalog ryzyk, typy zdarzeń i listy do wersji startowej?")) { await guard(() => post("/api/knowledge/reset"), "Przywrócono"); VIEWS.knowledge(); } };
  $("#k-sector-save").onclick = () => guard(() => post("/api/knowledge/sector_description", { value: $("#k-sector").value }), "Zapisano");
  $("#k-subs-save").onclick = () => guard(() => post("/api/knowledge/subsectors", { value: JSON.parse($("#k-subs").value) }), "Zapisano");
  $("#k-chk-save").onclick = () => guard(() => post("/api/knowledge/checklist", { value: JSON.parse($("#k-chk").value) }), "Zapisano");
};
window.editRisk = (code) => {
  const r = (window._K.risks.find((x) => x.code === code)) || { code: "", name: "", effects: "", patterns: [], mitigations: [], clauses: [], checks: [] };
  modal(`<h2>${code ? "Edycja kategorii " + esc(code) : "Nowa kategoria ryzyka"}</h2>
    <div class="grid g3"><label class="f">Kod<input id="r-code" value="${esc(r.code)}" ${code ? "disabled" : ""} placeholder="np. R16"></label><label class="f" style="grid-column:span 2">Nazwa<input id="r-name" value="${esc(r.name)}"></label></div>
    <label class="f">Efekty / skutki<textarea id="r-eff" style="min-height:60px">${esc(r.effects || "")}</textarea></label>
    <div class="grid g2"><label class="f">Wzorce (po jednym w wierszu)<textarea id="r-pat" class="code">${esc(r.patterns.join("\n"))}</textarea></label><label class="f">Działania zaradcze<textarea id="r-mit">${esc(r.mitigations.join("\n"))}</textarea></label>
    <label class="f">Propozycje zapisów umownych<textarea id="r-cl">${esc(r.clauses.join("\n"))}</textarea></label><label class="f">Kwestie do sprawdzenia<textarea id="r-ch">${esc(r.checks.join("\n"))}</textarea></label></div>
    <div class="row" style="margin-top:10px"><button class="btn primary" id="r-save">Zapisz</button></div>`);
  $("#r-save").onclick = async () => {
    for (const line of $("#r-pat").value.split("\n").filter(Boolean)) { try { new RegExp(line); } catch (e) { return toast("Błędny wzorzec: " + line, true); } }
    await guard(() => post("/api/knowledge/risk", { code: $("#r-code").value, name: $("#r-name").value, effects: $("#r-eff").value, patterns: $("#r-pat").value, mitigations: $("#r-mit").value, clauses: $("#r-cl").value, checks: $("#r-ch").value }), "Zapisano");
    closeModal(); VIEWS.knowledge();
  };
};
window.editET = (code) => {
  const t = (window._K.event_types.find((x) => x.code === code)) || { code: "", name: "", risk_codes: [], patterns: [] };
  modal(`<h2>${code ? "Typ zdarzenia " + esc(code) : "Nowy typ zdarzenia"}</h2><div class="grid g3"><label class="f">Kod<input id="t-code" value="${esc(t.code)}" ${code ? "disabled" : ""}></label><label class="f" style="grid-column:span 2">Nazwa<input id="t-name" value="${esc(t.name)}"></label></div>
    <label class="f">Kategorie ryzyka (kody, przecinek)<input id="t-risk" value="${esc(t.risk_codes.join(", "))}"></label><label class="f">Wzorce (po jednym w wierszu)<textarea id="t-pat" class="code">${esc(t.patterns.join("\n"))}</textarea></label>
    <div class="row" style="margin-top:10px"><button class="btn primary" id="t-save">Zapisz</button></div>`);
  $("#t-save").onclick = async () => { await guard(() => post("/api/knowledge/event-type", { code: $("#t-code").value, name: $("#t-name").value, risk_codes: $("#t-risk").value, patterns: $("#t-pat").value }), "Zapisano"); closeModal(); VIEWS.knowledge(); };
};

// ------------------------------------------------------------ RAPORTY
VIEWS.reports = async () => {
  const rep = await api("/api/report/links");
  const tables = ["projects", "procurements", "notices", "contracts", "contract_changes", "facts", "events", "links", "documents", "sources", "risk_catalog", "event_types", "audit_log", "analyses"];
  $("#main").innerHTML = `<h1>Raporty i eksport</h1><p class="sub">Wyniki zapisywane są jako rekordy możliwe do filtrowania, aktualizacji i eksportu (JSON/CSV).</p>
    <div class="grid g3">${kpi(rep.summary["poprawne"], "połączeń poprawnych (pewne + zatwierdzone)")}${kpi(rep.summary["niepewne"], "połączeń niepewnych (do weryfikacji)")}${kpi(rep.summary["błędne"], "połączeń błędnych (odrzuconych)")}</div>
    <div class="row" style="margin-top:12px"><a class="btn primary" href="/api/report/links?format=csv">Raport z testu łączenia (CSV)</a><a class="btn" href="/api/report/links" target="_blank">Raport (JSON)</a></div>
    <h2>Projekty — stan łączenia</h2><div class="card" style="padding:0;overflow:auto"><table><tr><th>Kod</th><th>Nazwa</th><th>Identyfikator</th><th>Status</th><th class="num">Postęp.</th><th class="num">Ogł.</th><th class="num">Zdarz.</th><th class="num">Umowa</th><th class="num">Odch. kosztu</th><th class="num">Opóźn.</th></tr>${rep.projects.map((p) => `<tr><td class="code">${esc(p.record_id)}</td><td>${esc(p.name)}</td><td class="small">${esc(p.identyfikator)}</td><td>${enrichPill(p.status_wzbogacenia)}</td><td class="num">${p.postepowania}</td><td class="num">${p.ogloszenia}</td><td class="num">${p.zdarzenia}</td><td class="num">${pln(p.wartosc_umowy)}</td><td class="num">${pct(p.odchylenie_kosztu)}</td><td class="num">${days(p.opoznienie_dni)}</td></tr>`).join("")}</table></div>
    <h2>Eksport tabel</h2><div class="card"><table>${tables.map((t) => `<tr><td class="code">${t}</td><td><a class="btn sm" href="/api/export/${t}?format=csv">CSV</a> <a class="btn sm" href="/api/export/${t}">JSON</a></td></tr>`).join("")}</table></div>`;
};

// ------------------------------------------------------------ USTAWIENIA
VIEWS.settings = async () => {
  const cfg = await api("/api/config");
  const s = await api("/api/status");
  $("#main").innerHTML = `<h1>Ustawienia i źródła danych</h1><p class="sub">Konfiguracja w pliku <span class="code">${esc(cfg._config_path)}</span> (model, dostawca, źródła — bez zmian w kodzie). Klucze API wyłącznie w zmiennych środowiskowych.</p>
    <div class="grid g2"><div class="card"><h3>Źródła</h3><div class="kv small"><div>BZP (API)</div><div class="code">${esc(cfg.bzp.base_url)}</div><div>Zapasowe</div><div class="code">${(cfg.bzp.fallback_urls || []).map(esc).join("<br>")}</div><div>Limit zapytań</div><div>${cfg.bzp.requests_per_minute || "bez limitu"} / min (dla ezamowienia.gov.pl automatycznie 25/min)</div><div>Cache odpowiedzi</div><div>${cfg.bzp.cache ? "tak (data/cache)" : "nie"}</div><div>Kopia lokalna BZP</div><div>${s.bzp_local ? "wczytana" : "brak"}</div><div>TED</div><div>${cfg.ted.enabled ? "włączony — " + esc(cfg.ted.search_url) : "wyłączony"}</div></div></div>
    <div class="card"><h3>Model językowy i przetwarzanie danych</h3><div class="kv small"><div>Dostawca</div><div>${esc(cfg.llm.provider)}</div><div>Model</div><div>${esc(cfg.llm.model || "—")}</div><div>Adres</div><div class="code">${esc(cfg.llm.base_url || "—")}</div><div>Klucz</div><div>${cfg.llm.api_key_set ? "ustawiony (" + esc(cfg.llm.api_key_env) + ")" : "brak — LLM nieaktywny"}</div><div>Miejsce przetwarzania</div><div>${esc(cfg.llm.data_location)}</div><div>OCR</div><div>${s.capabilities.ocr ? "dostępny (tesseract)" : "niedostępny"}</div></div></div></div>
    <div class="grid g2" style="margin-top:14px"><div class="card"><h3>Test połączenia z BZP</h3><div class="row"><input id="t-num" placeholder="np. 2023/BZP 00271948/01" class="grow"><button class="btn" id="t-go">Testuj</button></div><pre class="log" id="t-out" style="display:none"></pre></div>
    <div class="card"><h3>Kopia lokalna ogłoszeń (tryb offline)</h3><p class="small muted">Wczytaj paczkę organizatora (risk_miner_bzp_kopia.zip — pliki JSON w formacie API) lub plik JSON z ogłoszeniami. Wyszukiwanie korzysta wtedy z kopii zamiast z sieci.</p><div class="row"><label class="btn">Wczytaj .zip/.json<input type="file" id="t-local" accept=".zip,.json" hidden></label><button class="btn bad" id="t-clear">Usuń kopię lokalną</button></div></div></div>
    <div class="card" style="margin-top:14px"><h3>Baza danych</h3><p class="small muted">Plik SQLite w katalogu danych. Wyczyszczenie usuwa projekty, zdarzenia i analizy (wiedza ekspercka pozostaje).</p><button class="btn bad" id="t-reset">Wyczyść bazę przypadków</button></div>`;
  $("#t-go").onclick = async () => { const o = $("#t-out"); o.style.display = "block"; o.textContent = "…"; const r = await post("/api/bzp/test", { notice_number: $("#t-num").value || null, date_from: $("#t-num").value ? null : new Date(Date.now() - 86400000 * 3).toISOString().slice(0, 10) + "T00:00:00Z" }); o.textContent = JSON.stringify(r, null, 2); };
  $("#t-local").onchange = async (e) => { const r = await guard(() => upload("/api/bzp/import-local", e.target.files[0])); toast(`Dodano ${r.added} ogłoszeń (razem ${r.total})`); VIEWS.settings(); };
  $("#t-clear").onclick = async () => { await guard(() => post("/api/bzp/clear-local"), "Usunięto"); VIEWS.settings(); };
  $("#t-reset").onclick = async () => { const c = prompt("Wpisz USUŃ, aby wyczyścić bazę przypadków:"); if (c) { await guard(() => post("/api/admin/reset", { confirm: c }), "Wyczyszczono"); location.hash = "#/"; } };
};


// ------------------------------------------------------------ WIZUALIZACJE (oś czasu, rozkład wyników, rejestr)
const VZ = { plan: "#2a78d6", late: "#e34948", early: "#008300", ink: "#1b2430", muted: "#5d6b7c", grid: "#e3e8ee" };
const pp = (v, d = 0) => (v === null || v === undefined || isNaN(v) ? "—" : (v >= 0 ? "+" : "−") + Math.abs(v * 100).toLocaleString("pl-PL", { maximumFractionDigits: d }) + "%");
const months = (dd) => (dd === null || dd === undefined ? "—" : (dd / 30.4).toLocaleString("pl-PL", { maximumFractionDigits: 1 }) + " mies.");
// jeden dymek dla wszystkich wykresów: elementy z atrybutem data-tip
(function () {
  const tip = document.createElement("div");
  tip.className = "viztip hidden";
  document.body.appendChild(tip);
  document.addEventListener("mousemove", (e) => {
    const t = e.target.closest && e.target.closest("[data-tip]");
    if (!t) return tip.classList.add("hidden");
    tip.innerHTML = t.getAttribute("data-tip");
    tip.classList.remove("hidden");
    const x = Math.min(window.innerWidth - tip.offsetWidth - 12, e.clientX + 14);
    tip.style.left = x + "px"; tip.style.top = (e.clientY + 16) + "px";
  });
})();
const dnum = (s) => (s ? Date.parse(String(s).slice(0, 10) + "T00:00:00Z") : null);

function cpvShort(cpv) {
  if (!cpv) return "—";
  const codes = String(cpv).split(/,(?=\s*\d{8}-\d)/).map((x) => x.trim()).filter(Boolean);
  return `<span title="${esc(cpv)}">${esc(codes[0])}${codes.length > 1 ? ` <span class="pill p-grey">+${codes.length - 1}</span>` : ""}</span>`;
}
function timelineSvg(d) {
  const rows = [];
  const sp = d.metrics.scope_part;
  d.procurements.forEach((pr) => pr.contracts.forEach((c) => {
    if (!c.signed_date && !c.planned_end_date) return;
    const out = sp && c.part && Number(c.part) !== Number(sp);
    rows.push({ pr, c, out, label: (c.part ? `część ${c.part} · ` : "") + (c.contractor_name || "wykonawca") + (out ? " — poza zakresem rekordu" : sp && Number(c.part) === Number(sp) ? " — zakres rekordu" : "") });
  }));
  if (!rows.length) return "";
  const all = [];
  rows.forEach(({ pr, c }) => { [pr.publication_date, c.signed_date, c.planned_end_date, c.actual_end_date, ...c.changes.map((x) => x.change_date)].forEach((x) => { const t = dnum(x); if (t) all.push(t); }); });
  const DAY = 86400000, lo = Math.min(...all) - 20 * DAY, hi = Math.max(...all) + 40 * DAY;
  const W = 860, L = 10, R = 120, rowH = 54, top = 26, H = top + rows.length * rowH + 34;
  const X = (t) => L + ((t - lo) / (hi - lo)) * (W - L - R);
  let g = "";
  const MON = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
  const short = hi - lo < 420 * DAY;
  for (let dd = new Date(lo), y = dd.getUTCFullYear(), mo = dd.getUTCMonth() + 1; Date.UTC(y, mo, 1) < hi; mo++) {
    if (mo > 11) { mo = 0; y++; }
    const t = Date.UTC(y, mo, 1);
    if (t >= hi) break;
    if (!short && mo !== 0) continue;
    const x = X(t);
    g += `<line x1="${x}" x2="${x}" y1="${top - 6}" y2="${H - 26}" stroke="${VZ.grid}"/><text x="${x + 3}" y="${top - 10}" font-size="11" fill="${VZ.muted}">${short ? MON[mo] + (mo === 0 || x < 60 ? " " + y : "") : y}</text>`;
  }
  rows.forEach(({ pr, c, label, out }, i) => {
    const y = top + i * rowH + 18;
    if (out) g += `<g opacity="0.35">`;
    const s0 = dnum(c.signed_date), pe = dnum(c.planned_end_date), ae = dnum(c.actual_end_date), pub = dnum(pr.publication_date);
    g += `<text x="${L}" y="${y - 12}" font-size="11.5" fill="${VZ.ink}">${esc(label.slice(0, 90))}</text>`;
    if (pub) g += `<circle cx="${X(pub)}" cy="${y + 5}" r="5" fill="#fff" stroke="${VZ.ink}" stroke-width="2" data-tip="<b>Ogłoszenie o zamówieniu</b><br>${esc(String(pr.publication_date).slice(0, 10))}"/>`;
    if (s0 && pe) g += `<rect x="${X(s0)}" y="${y}" width="${Math.max(2, X(pe) - X(s0))}" height="10" rx="4" fill="${VZ.plan}" data-tip="<b>Okres umowny</b><br>${esc(c.signed_date)} → ${esc(c.planned_end_date)}<br>${Math.round((pe - s0) / DAY)} dni"/>`;
    if (pe && ae) {
      const dd = Math.round((ae - pe) / DAY);
      if (dd > 0) {
        g += `<rect x="${X(pe) + 2}" y="${y}" width="${Math.max(2, X(ae) - X(pe) - 2)}" height="10" rx="4" fill="${VZ.late}" data-tip="<b>Po terminie</b><br>termin ${esc(c.planned_end_date)}, wykonanie ${esc(c.actual_end_date)}<br>+${dd} dni"/>`;
        g += `<text x="${X(ae) + 6}" y="${y + 9}" font-size="11.5" font-weight="600" fill="${VZ.ink}">+${dd} dni</text>`;
      } else {
        g += `<line x1="${X(ae)}" x2="${X(ae)}" y1="${y - 4}" y2="${y + 14}" stroke="${VZ.early}" stroke-width="3" data-tip="<b>Wykonano w terminie</b><br>${esc(c.actual_end_date)} (${dd} dni)"/>`;
        g += `<text x="${X(Math.max(ae, pe)) + 6}" y="${y + 9}" font-size="11.5" fill="${VZ.ink}">${dd === 0 ? "w terminie" : dd + " dni"}</text>`;
      }
    } else if (pe && !ae) {
      g += `<text x="${X(pe) + 6}" y="${y + 9}" font-size="11.5" fill="${VZ.muted}">w toku / brak ogłoszenia o wykonaniu</text>`;
    }
    c.changes.forEach((ch) => {
      const t = dnum(ch.change_date); if (!t) return;
      const x = X(t);
      g += `<path d="M${x} ${y - 3} l6 8 l-6 8 l-6 -8 z" fill="${VZ.ink}" stroke="#fff" stroke-width="1.5" data-tip="<b>Zmiana umowy</b> ${esc(ch.change_date)}<br>${esc(ch.legal_basis || "")}<br>${esc((ch.description || "").slice(0, 220))}"/>`;
    });
    if (out) g += `</g>`;
  });
  const ly = H - 12;
  g += `<g font-size="11" fill="${VZ.muted}"><rect x="${L}" y="${ly - 8}" width="22" height="8" rx="3" fill="${VZ.plan}"/><text x="${L + 28}" y="${ly}">okres umowny</text>
    <rect x="${L + 120}" y="${ly - 8}" width="22" height="8" rx="3" fill="${VZ.late}"/><text x="${L + 148}" y="${ly}">po terminie</text>
    <path d="M${L + 236} ${ly - 10} l5 6 l-5 6 l-5 -6 z" fill="${VZ.ink}"/><text x="${L + 248}" y="${ly}">zmiana umowy</text>
    <circle cx="${L + 352}" cy="${ly - 4}" r="4.5" fill="#fff" stroke="${VZ.ink}" stroke-width="2"/><text x="${L + 362}" y="${ly}">ogłoszenie o zamówieniu</text></g>`;
  return `<div class="card tl" style="margin-bottom:12px"><h3 style="margin-top:0">Oś czasu realizacji</h3><svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Oś czasu umów projektu">${g}</svg></div>`;
}

// rozkład wyników w klasie referencyjnej: każda kropka = jedna umowa, linie = P50/P80/P90
function distSvg(dist, fmt) {
  if (!dist || !dist.n) return `<div class="empty">Brak umów z wynikiem realizacji.</div>`;
  const pts = dist.points;
  const vals = pts.map((p) => p.value);
  let lo = Math.min(0, ...vals), hi = Math.max(dist.p90 || 0, ...vals);
  const pad = (hi - lo) * 0.06 || 0.05; lo -= pad; hi += pad;
  const W = 640, L = 14, R = 14, base = 128, H = 168;
  const X = (v) => L + ((v - lo) / (hi - lo)) * (W - L - R);
  const wmax = Math.max(...pts.map((p) => p.weight)) || 1;
  const placed = [];
  let g = "";
  // oś i zero
  g += `<line x1="${L}" x2="${W - R}" y1="${base}" y2="${base}" stroke="${VZ.grid}"/>`;
  const step = niceStep((hi - lo) / 6);
  for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) {
    g += `<line x1="${X(t)}" x2="${X(t)}" y1="${base}" y2="${base + 4}" stroke="${VZ.muted}"/><text x="${X(t)}" y="${base + 17}" font-size="11" text-anchor="middle" fill="${VZ.muted}">${fmt(t)}</text>`;
  }
  g += `<line x1="${X(0)}" x2="${X(0)}" y1="44" y2="${base}" stroke="${VZ.muted}" stroke-width="1" stroke-dasharray="1 3"/>`;
  let lastX = -1e9;
  [["P50", dist.p50], ["P80", dist.p80], ["P90", dist.p90]].forEach(([k, v], i) => {
    if (v === null || v === undefined) return;
    const x = X(v), left = x - lastX < 64 || x > W - 70;
    g += `<line x1="${x}" x2="${x}" y1="${12 + i * 12}" y2="${base}" stroke="${VZ.ink}" stroke-width="${k === "P80" ? 2 : 1}" stroke-dasharray="${k === "P80" ? "" : "4 3"}"/><text x="${left ? x - 4 : x + 4}" y="${14 + i * 12}" text-anchor="${left ? "end" : "start"}" font-size="11" font-weight="${k === "P80" ? 700 : 500}" fill="${VZ.ink}">${k} ${fmt(v)}</text>`;
    lastX = x;
  });
  pts.forEach((p) => {
    const r = 4 + 3 * Math.sqrt(p.weight / wmax);
    const x = X(p.value);
    let y = base - r - 3;
    while (placed.some((q) => Math.abs(q.x - x) < q.r + r + 1 && Math.abs(q.y - y) < q.r + r + 1)) y -= 4;
    placed.push({ x, y, r });
    const tip = `<b>${esc(p.record_id)}</b><br>${fmt(p.value)}<br>podobieństwo ${Math.round(p.score * 100)}% · waga ${p.weight.toFixed(2)}${p.verified ? "" : "<br><i>dopasowanie BZP do weryfikacji</i>"}`;
    g += `<circle cx="${x}" cy="${y}" r="${r}" fill="${p.verified ? VZ.plan : "#fff"}" stroke="${p.verified ? "#fff" : VZ.plan}" stroke-width="2" data-tip="${esc(tip)}"/>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(dist.label)}">${g}</svg>
    <div class="small muted">Każda kropka = jedna umowa (większa = bardziej podobna); pusta = powiązanie z BZP do weryfikacji; kropkowana linia = plan (0%). ${dist.share_over_raw ? `Powyżej planu: <b>${dist.share_over_raw[0]} z ${dist.share_over_raw[1]}</b>.` : ""} n=${dist.n}, n<sub>eff</sub>=${num(dist.n_eff, 1)}${dist.p80_ci ? ` · P80 w przedziale ${fmt(dist.p80_ci[0])} … ${fmt(dist.p80_ci[1])} (bootstrap)` : ""}</div>`;
}
function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const n = raw / p;
  return (n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10) * p;
}

function registerTable(reg, value) {
  if (!reg || !reg.rows || !reg.rows.length) return `<div class="empty">Brak zmaterializowanych ryzyk w danych.</div>`;
  const maxP = Math.max(...reg.rows.map((r) => r.probability)) || 1;
  return `<table><tr><th>Ryzyko</th><th>Prawdopodobieństwo</th><th class="num">Skutek kosztowy<div class="small muted">mediana, % umowy</div></th><th class="num">Wydłużenie<div class="small muted">mediana</div></th><th class="num">Wartość oczekiwana${value ? "<div class=\"small muted\">dla tej inwestycji</div>" : ""}</th><th>Jak zmieniano umowy</th></tr>
    ${reg.rows.map((r) => `<tr><td>${riskLabel(r.code)}<details><summary class="small">przykłady (${r.examples.length})</summary>${r.examples.map((e) => `<div class="quote small"><b>${esc(e.project)}</b> ${esc(e.title)}<br>${esc(e.cause)}</div>`).join("")}</details></td>
      <td style="min-width:150px"><div class="row" style="gap:6px"><div class="bar grow" data-tip="${esc(r.projects.join(", "))}"><i style="width:${(r.probability / maxP) * 100}%;background:${VZ.plan}"></i></div><b>${Math.round(r.probability * 100)}%</b></div><div class="small muted">${r.k} z ${r.n} umów</div></td>
      <td class="num">${r.impact_cost_pct === null ? "—" : pp(r.impact_cost_pct, 1)}<div class="small muted">${r.n_cost_obs ? "n=" + r.n_cost_obs : ""}</div></td>
      <td class="num">${r.impact_delay_days ? Math.round(r.impact_delay_days) + " dni" : "—"}</td>
      <td class="num"><b>${r.emv_pln ? pln(r.emv_pln) : r.emv_pct ? pp(r.emv_pct, 1) : "—"}</b>${r.emv_days ? `<div class="small muted">${Math.round(r.emv_days)} dni</div>` : ""}</td>
      <td class="small">${r.bases.map((b) => `${esc(b.basis)} <span class="muted">(${esc(b.meaning || "")})</span> ×${b.n}`).join("<br>") || "—"}</td></tr>`).join("")}</table>
    <p class="small muted">${esc(reg.method)}</p>`;
}
function basesBars(b) {
  if (!b || !b.n) return "";
  return `<h3>Na jakiej podstawie zmieniano umowy (${b.n} zmian w BZP)</h3>${b.rows.map((r) => `<div class="row small" style="gap:8px;margin:3px 0"><span style="width:300px"><b>${esc(r.basis)}</b> <span class="muted">${esc(r.meaning)}</span></span><div class="bar grow"><i style="width:${r.share * 100}%;background:${VZ.plan}"></i></div><span style="width:70px" class="num">${r.n} · ${Math.round(r.share * 100)}%</span></div>`).join("")}<p class="small muted">${esc(b.note)}</p>`;
}

function insightsCard(ins) {
  const c = ins.rcf.cost, t = ins.rcf.time, td = ins.rcf.tender;
  if (!c.n && !t.n) return "";
  const top = (ins.register.rows || []).slice().sort((a, b) => b.k - a.k).slice(0, 2);
  const lessons = [
    td.n ? `Przetarg zwykle wychodzi <b>taniej niż kosztorys</b> (mediana ${pp(td.p50, 0)}) — ale to nie są wolne pieniądze:` : "",
    c.n ? `<b>${c.share_over_raw[0]} z ${c.share_over_raw[1]}</b> umów kosztowało ostatecznie więcej niż w umowie; żeby budżet wystarczył w 8 na 10 przypadków, potrzeba <b>${pp(c.p80, 0)}</b> rezerwy.` : "",
    t.n ? `<b>${t.share_over_raw[0]} z ${t.share_over_raw[1]}</b> umów skończyło się po terminie — bezpieczny harmonogram to umowny czas <b>${pp(t.p80, 0)}</b>.` : "",
    top.length ? `Najczęstsze przyczyny zmian umów: <b>${top.map((x) => esc(x.name.toLowerCase())).join("</b> oraz <b>")}</b>.` : "",
  ].filter(Boolean);
  return `<h2>Czego uczy baza — szczegóły</h2>
    <div class="grid g2"><div class="card"><h3 style="margin-top:0">Koszt: rozliczenie vs wartość umowy</h3>${distSvg(c, (v) => pp(v))}</div>
      <div class="card"><h3 style="margin-top:0">Czas: faktyczny vs umowny</h3>${distSvg(t, (v) => pp(v))}</div></div>
    <div class="grid g2" style="margin-top:12px"><div class="card">${basesBars(ins.bases)}</div>
      <div class="card"><h3 style="margin-top:0">Wykryte problemy w danych wejściowych (${ins.data_issues.length})</h3>${ins.data_issues.map((x) => `<div class="quote small"><a href="#/projekt/${x.project_id}"><b>${esc(x.record_id)}</b></a> ${esc(x.message)}</div>`).join("") || `<div class="empty">Brak.</div>`}</div></div>
    <div class="card" style="margin-top:12px;overflow:auto"><h3 style="margin-top:0">Ryzyka, które się zmaterializowały — z wyceną</h3>${registerTable(ins.register)}</div>`;
}

function clauseAudit(a) {
  if (!a) return "";
  const st = { "jest": "p-ok", "brak": "p-warn", "niepełna": "p-warn", "wyłączona": "p-bad", "do przemyślenia": "p-info", "nie oceniono": "p-grey" };
  return `<h3>Audyt klauzul projektu umowy</h3><div class="hint">${esc(a.summary)}${a.months ? ` Okres realizacji odczytany z materiałów: <b>${a.months} mies.</b>` : ""}</div>
    <table class="audit" style="margin-top:8px"><tr><th>Status</th><th>Klauzula</th><th>W materiałach</th><th>Dlaczego (dane z podobnych umów)</th></tr>
    ${a.rows.map((r) => `<tr><td><span class="pill ${r.legal_gap ? "p-bad" : st[r.status] || "p-grey"}">${r.legal_gap ? "⚠ " : ""}${esc(r.status)}</span>${r.required ? `<div class="small muted" style="margin-top:4px">wymóg ustawowy</div>` : ""}</td>
      <td><b>${esc(r.id)} ${esc(r.name)}</b><div class="small muted">${esc(r.ref)} · ${r.risks.map(esc).join(", ")}</div>${r.required_text ? `<div class="small">${esc(r.required_text)}</div>` : ""}${r.note ? `<div class="small" style="color:var(--bad)">${esc(r.note)}</div>` : ""}
        <details><summary class="small">propozycja zapisu</summary><div class="small">${esc(r.model)}</div></details></td>
      <td class="small">${r.evidence ? `<div class="quote">${esc(r.evidence.quote)}</div><span class="muted">${esc(r.evidence.doc || "")}${r.evidence.page ? ", s. " + r.evidence.page : ""}</span>` : `<span class="muted">${r.status === "nie oceniono" ? "—" : "nie znaleziono"}</span>`}</td>
      <td class="small">${r.data_why.map(esc).join("<br>") || (r.required ? "wymóg ustawowy — obowiązuje niezależnie od danych historycznych" : '<span class="muted">brak przypadków w bazie</span>')}</td></tr>`).join("")}</table>
    <p class="small muted">${esc(a.disclaimer)}</p>`;
}

function referenceBlock(ref, f) {
  if (!ref || !ref.rcf) return "";
  const R = ref.rcf, res = R.result || {}, ct = res.contract || {};
  const mln = (v) => (v === null || v === undefined ? "—" : (v / 1e6).toLocaleString("pl-PL", { maximumFractionDigits: 2 }) + " mln zł");
  let lead = "";
  if (res.p80 && f.value) {
    lead += res.p80.uplift <= 0
      ? `Szacunek <b>${mln(f.value)}</b>: w podobnych przypadkach ostateczny koszt był niższy od szacunku — P80 to <b>${mln(res.p80.budget_raw)}</b> (${pp(res.p80.uplift, 1)}), więc szacunek wystarczyłby w ponad 80% przypadków. `
      : `Szacunek <b>${mln(f.value)}</b> jest za niski w ponad 20% podobnych przypadków — zaplanuj rezerwę <b>${pln(res.reserve_p80)}</b> (${pp(res.p80.uplift, 1)}). `;
  }
  if (ct.p80 !== undefined) lead += `Po przetargu${ct.expected_price ? ` (typowa cena ofert ≈ <b>${mln(ct.expected_price)}</b>)` : ""} utrzymaj rezerwę <b>${pp(ct.p80, 1)}</b> ceny umowy${ct.reserve_p80_pln ? ` (≈ <b>${pln(ct.reserve_p80_pln)}</b>)` : ""} — oszczędności przetargowych nie zwalniaj w całości. `;
  if (res.time_p80) lead += `Czas realizacji: zaplanuj <b>${months(res.time_p80.days)}</b> (P80) zamiast ${months(ref.duration_days_input)}`;
  const rowsT = ["p50", "p80", "p90"].map((q) => `<tr><td><b>${q.toUpperCase()}</b>${q === "p80" ? ' <span class="pill p-info">poziom planistyczny</span>' : ""}</td>
      <td class="num">${res[q] ? pp(res[q].uplift, 1) : "—"}</td><td class="num">${res[q] ? `<b>${pln(res[q].budget_raw)}</b>` : "—"}</td>
      <td class="num">${ct[q] !== undefined ? `<b>${pp(ct[q], 1)}</b>` : "—"}</td>
      <td class="num">${res["time_" + q] ? pp(res["time_" + q].uplift) : "—"}</td><td class="num">${res["time_" + q] ? `<b>${months(res["time_" + q].days)}</b>` : "—"}</td></tr>`).join("");
  return `<div class="layer calc" style="margin-top:14px"><span class="tag">B2. Prognoza referencyjna — jak skończyły się podobne umowy</span>
    <p class="small">Zamiast prognozować „od zera”, system sprawdza, <b>jak naprawdę skończyły się umowy z bazy</b> (wypłata i data wykonania z ogłoszeń o wykonaniu umowy w BZP), ważąc je podobieństwem do tej inwestycji.</p>
    ${lead ? `<div class="hint">${lead}</div>` : ""}
    <table style="margin-top:8px"><tr><th>Poziom</th><th class="num">Koszt końcowy vs szacunek</th><th class="num">Prognozowany koszt końcowy</th><th class="num">Rezerwa od ceny umowy</th><th class="num">Narzut czasu</th><th class="num">Czas realizacji</th></tr>${rowsT}</table>
    <p class="small muted">Podstawa etapu szacunku: ${esc(res.estimate_basis || "—")}. ${res.tender_note ? esc(res.tender_note) : ""}</p>
    <div class="grid g3" style="margin-top:8px"><div><h3>Rozliczenie vs szacunek inwestora</h3>${distSvg(R.total, (v) => pp(v))}</div><div><h3>Rozliczenie vs cena umowy</h3>${distSvg(R.cost, (v) => pp(v))}</div><div><h3>Czas faktyczny vs umowny</h3>${distSvg(R.time, (v) => pp(v))}</div></div>
    <p class="small muted">Pewność: <b>${esc(R.confidence)}</b>. ${esc(R.method)}</p></div>`;
}

// ------------------------------------------------------------ CZYTELNE PODSUMOWANIA (werdykt analizy, historia projektu)
const mlnz = (v) => (v === null || v === undefined ? "—" : (Math.abs(v) >= 1e6 ? (v / 1e6).toLocaleString("pl-PL", { maximumFractionDigits: 2 }) + " mln zł" : Math.round(v / 1000).toLocaleString("pl-PL") + " tys. zł"));
const dpl = (s) => (s ? String(s).slice(0, 10).split("-").reverse().join(".") : "—");
function deadlineBlock(ref) {
  const F = ref && ref.funding;
  if (!F) return "";
  const DAY = 86400000, t0 = Date.parse(F.start + "T00:00:00Z");
  const dl = F.deadline ? Date.parse(F.deadline + "T00:00:00Z") : null;
  const ends = F.paths.map((p) => t0 + p.days * DAY);
  const naive = Date.parse(F.naive_finish + "T00:00:00Z");
  const lo = t0, hi = Math.max(...ends, dl || 0, naive) + 60 * DAY;
  const W = 860, L = 16, R = 20, base = 120, H = 170;
  const X = (t) => L + ((t - lo) / (hi - lo)) * (W - L - R);
  const MON = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
  let g = `<line x1="${L}" x2="${W - R}" y1="${base}" y2="${base}" stroke="${VZ.grid}"/>`;
  for (let d = new Date(lo); d.getTime() < hi; d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1))) {
    if (d.getUTCMonth() % 6) continue;
    const x = X(d.getTime());
    g += `<line x1="${x}" x2="${x}" y1="${base}" y2="${base + 4}" stroke="${VZ.muted}"/><text x="${x}" y="${base + 17}" font-size="11" text-anchor="${x < 40 ? "start" : "middle"}" fill="${VZ.muted}">${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}</text>`;
  }
  g += `<circle cx="${X(t0)}" cy="${base}" r="5" fill="#fff" stroke="${VZ.ink}" stroke-width="2" data-tip="<b>Ogłoszenie przetargu</b><br>${dpl(F.start)}"/><text x="${X(t0) + 8}" y="${base - 8}" font-size="11" fill="${VZ.ink}">start ${dpl(F.start)}</text>`;
  if (dl) g += `<rect x="${X(dl)}" y="14" width="${Math.max(0, W - R - X(dl))}" height="${base - 14}" fill="${VZ.late}" opacity="0.07"/><line x1="${X(dl)}" x2="${X(dl)}" y1="10" y2="${base}" stroke="${VZ.late}" stroke-width="2"/><text x="${X(dl) + 5}" y="22" font-size="11.5" font-weight="700" fill="${VZ.late}">termin dofinansowania ${dpl(F.deadline)}</text>`;
  g += `<line x1="${X(naive)}" x2="${X(naive)}" y1="40" y2="${base}" stroke="${VZ.muted}" stroke-dasharray="4 3"/><text x="${X(naive) - 5}" y="50" text-anchor="end" font-size="11" fill="${VZ.muted}">„na papierze” ${dpl(F.naive_finish)}</text>`;
  const placed = [];
  F.paths.forEach((p) => {
    const x = X(t0 + p.days * DAY), r = 5;
    let y = base - r - 3;
    while (placed.some((q) => Math.abs(q.x - x) < 2 * r + 1 && Math.abs(q.y - y) < 2 * r + 1)) y -= 6;
    placed.push({ x, y });
    const late = dl && t0 + p.days * DAY > dl;
    g += `<circle cx="${x}" cy="${y}" r="${r}" fill="${p.verified ? (late ? VZ.late : VZ.plan) : "#fff"}" stroke="${p.verified ? "#fff" : late ? VZ.late : VZ.plan}" stroke-width="2" data-tip="<b>${esc(p.record_id)}</b> — gdyby ta inwestycja przebiegła jak ta umowa<br>przetarg ${p.tender_days} dni + realizacja → koniec ${dpl(new Date(t0 + p.days * DAY).toISOString())}${late ? "<br><b>po terminie dofinansowania</b>" : ""}"/>`;
  });
  const pm = F.p_miss;
  const head = F.deadline
    ? `<div class="bigq ${pm >= 0.5 ? "bad" : pm >= 0.2 ? "warn" : "ok"}"><span class="pct">${Math.round(pm * 100)}%</span><span>ryzyka, że inwestycja <b>nie zdąży przed ${dpl(F.deadline)}</b> — tak skończyło się ${F.k_miss[0]} z ${F.k_miss[1]} podobnych przebiegów.</span></div>`
    : `<div class="hint">Podaj termin zakończenia z umowy o dofinansowanie (pole nad przyciskiem „Analizuj” albo w opisie), aby policzyć ryzyko utraty dofinansowania.</div>`;
  const tips = [];
  if (F.deadline) {
    tips.push(`„Na papierze” (przetarg ~${Math.round(F.tender.p50 || 45)} dni + ${months(F.planned_days)} realizacji) koniec wypada <b>${dpl(F.naive_finish)}</b>, ale w 8 na 10 podobnych przebiegów dopiero do <b>${dpl(F.finish.p80)}</b>.`);
    if (F.start_too_late) tips.push(`Żeby mieć 80% szans na zakończenie w terminie, przetarg trzeba by ogłosić najpóźniej <b>${dpl(F.latest_start_p80)}</b> — ${Date.parse(F.latest_start_p80) < Date.now() ? "ta data już minęła" : "to wcześniej niż planujesz"}.`);
    else tips.push(`Najpóźniejszy bezpieczny (P80) termin ogłoszenia przetargu: <b>${dpl(F.latest_start_p80)}</b>.`);
    if (F.max_planned_days_p80 && F.max_planned_days_p80 < F.planned_days) tips.push(`Przy tym starcie umowny czas realizacji musiałby wynosić ok. <b>${months(F.max_planned_days_p80)}</b> — jeśli to nierealne: podziel zamówienie na części, ogłoś przetarg wcześniej albo wynegocjuj dłuższy termin w umowie o dofinansowanie.`);
    else if (!F.max_planned_days_p80) tips.push(`Żaden realny czas realizacji nie daje 80% szans przy tym starcie — potrzebny wcześniejszy przetarg, podział na części albo zmiana terminu w umowie o dofinansowanie.`);
  }
  return `<div class="layer concl" style="margin-top:14px"><span class="tag">Czy zdążysz przed końcem dofinansowania?</span>
    ${head}${tips.length ? `<ul class="todo">${tips.map((x) => `<li>${x}</li>`).join("")}</ul>` : ""}
    <svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Rozkład dat zakończenia">${g}</svg>
    <div class="small muted">Każda kropka = data końca, gdyby ta inwestycja przebiegła jak jedna z podobnych umów z BZP (czerwona = po terminie; pusta = powiązanie do weryfikacji). n=${F.n}, n<sub>eff</sub>=${num(F.n_eff, 1)}. ${esc(F.method)}</div></div>`;
}

function verdictCard(r) {
  const f = r.input.features, calc = r.obliczenia, w = r.wnioski;
  const R = (calc.reference || {}).rcf;
  if (!R || !R.n_class) return "";
  const res = R.result || {}, ct = res.contract || {};
  const reg = (calc.register || {}).rows || [];
  const audit = w.clause_audit || { rows: [] };
  const gaps = audit.rows.filter((x) => x.legal_gap);
  const weak = audit.rows.filter((x) => !x.legal_gap && ["brak", "niepełna", "wyłączona", "do przemyślenia"].includes(x.status) && x.probability >= 0.1);
  const tiles = [];
  // 1. budżet
  if (res.p80 && f.value) {
    const ok = res.p80.uplift <= 0;
    tiles.push({ tone: ok ? "ok" : "bad", label: "Budżet", big: ok ? "Szacunek wystarczy" : "Za mało o " + mlnz(res.reserve_p80),
      small: ok ? `w 8 na 10 podobnych przypadków koszt końcowy ≤ ${mlnz(res.p80.budget_raw)}` : `w 8 na 10 podobnych przypadków potrzeba do ${mlnz(res.p80.budget)}` });
  }
  if (ct.p80 !== undefined) tiles.push({ tone: ct.p80 > 0.1 ? "warn" : "ok", label: "Po przetargu", big: `Zostaw ${pp(ct.p80, 0)} rezerwy`,
    small: `od ceny umowy${ct.reserve_p80_pln ? ` (≈ ${mlnz(ct.reserve_p80_pln)})` : ""} — ${R.cost.share_over_raw ? R.cost.share_over_raw[0] + " z " + R.cost.share_over_raw[1] : "większość"} umów kosztowało więcej niż w umowie` });
  if (res.time_p80 && calc.reference.duration_days_input) {
    const late = res.time_p80.uplift > 0.15;
    tiles.push({ tone: late ? "bad" : "ok", label: "Termin", big: `Planuj ${months(res.time_p80.days)}`, small: `zamiast ${months(calc.reference.duration_days_input)} — ${R.time.share_over_raw ? R.time.share_over_raw[0] + " z " + R.time.share_over_raw[1] : ""} podobnych umów skończyło się po terminie` });
  }
  const FD = (calc.reference || {}).funding;
  if (FD && FD.deadline) tiles.unshift({ tone: FD.p_miss >= 0.5 ? "bad" : FD.p_miss >= 0.2 ? "warn" : "ok", label: "Dofinansowanie", big: `${Math.round(FD.p_miss * 100)}% ryzyka utraty`,
    small: `nie zdąży przed ${dpl(FD.deadline)} w ${FD.k_miss[0]} z ${FD.k_miss[1]} podobnych przebiegów; realnie koniec do ${dpl(FD.finish.p80)} (P80)` });
  if (reg[0]) tiles.push({ tone: "warn", label: "Największe ryzyko", big: reg[0].name, small: `${reg[0].k} z ${reg[0].n} podobnych umów${reg[0].emv_pln ? ` · średnio ok. ${mlnz(reg[0].emv_pln)} na projekt` : ""}` });
  tiles.push(audit.has_contract
    ? { tone: gaps.length ? "bad" : weak.length ? "warn" : "ok", label: "Projekt umowy", big: gaps.length ? `${gaps.length} ${gaps.length === 1 ? "brak wymagany" : "braki wymagane"} prawem` : weak.length ? `${weak.length} luk do uzupełnienia` : "Bez istotnych luk", small: gaps.map((x) => x.ref).join(", ") || "sprawdzono 14 klauzul" }
    : { tone: "grey", label: "Projekt umowy", big: "Nie wgrano", small: "dodaj PPU/SWZ, aby sprawdzić klauzule" });
  // lista działań
  const todo = [];
  if (FD && FD.deadline && FD.p_miss >= 0.2) todo.push(`<b>Ratuj termin dofinansowania:</b> ${FD.start_too_late ? `przetarg należało ogłosić do ${dpl(FD.latest_start_p80)}` : `ogłoś przetarg najpóźniej ${dpl(FD.latest_start_p80)}`} — rozważ podział na części, wcześniejszy start albo aneks do umowy o dofinansowanie.`);
  gaps.forEach((x) => todo.push(`<b>Popraw umowę:</b> ${esc(x.name)} — ${esc(x.ref)}${x.note ? ` (${esc(x.note)})` : ""}.`));
  weak.slice(0, 3).forEach((x) => todo.push(`<b>Dopisz do umowy:</b> ${esc(x.name)}${x.data_why.length ? ` <span class="muted">(w podobnych umowach: ${esc((x.data_why[0].split(": ").slice(1).join(": ") || x.data_why[0]).split(";")[0].replace(" podobnych umów", ""))})</span>` : ""}.`));
  if (res.time_p80 && res.time_p80.uplift > 0.15) todo.push(`<b>Wydłuż harmonogram</b> do ok. ${months(res.time_p80.days)} albo zaplanuj, co zrobisz przy opóźnieniu (kamienie milowe, kary za etapy).`);
  if (ct.p80 > 0.1) todo.push(`<b>Nie zwalniaj oszczędności z przetargu</b> — zostaw rezerwę ok. ${pp(ct.p80, 0)} ceny umowy na zmiany w trakcie budowy.`);
  if (reg[0]) todo.push(`<b>Sprawdź przed przetargiem:</b> ${esc(reg[0].name.toLowerCase())} — w podobnych umowach to najdroższe ryzyko.`);
  return `<div class="verdict"><div class="vh"><div><div class="eyebrow">Odpowiedź w 30 sekund</div><h2>Jak może pójść ta inwestycja — na podstawie ${R.n_class} prawdziwych umów z BZP</h2></div></div>
    <div class="vtiles">${tiles.map((t) => `<div class="vt ${t.tone}"><div class="vl">${esc(t.label)}</div><div class="vb">${esc(t.big)}</div><div class="vs">${esc(t.small)}</div></div>`).join("")}</div>
    ${todo.length ? `<h3>Co zrobić przed ogłoszeniem przetargu</h3><ol class="todo">${todo.slice(0, 6).map((x) => `<li>${x}</li>`).join("")}</ol>` : ""}
    <p class="small muted">Jak czytać: <b>P80</b> = wartość, która wystarczyła w 8 na 10 podobnych przypadkach. Szczegóły, obliczenia i cytaty ze źródeł — poniżej.</p></div>`;
}

function projectStory(d) {
  const m = d.metrics;
  const cs = [];
  d.procurements.forEach((pr) => pr.contracts.forEach((c) => { if (!m.scope_part || !c.part || Number(c.part) === Number(m.scope_part)) cs.push(c); }));
  if (!cs.length) return "";
  const c = cs[0];
  const parts = [];
  parts.push(`Umowę${c.contractor_name ? ` z wykonawcą <b>${esc(c.contractor_name)}</b>` : ""} podpisano <b>${dpl(m.signed_date)}</b> na <b>${mlnz(m.contract_value)}</b>${m.planned_end_date ? `, z terminem do <b>${dpl(m.planned_end_date)}</b>` : ""}${m.n_offers ? ` (ofert w przetargu: ${m.n_offers})` : ""}.`);
  if (m.actual_end_date) {
    const dd = m.delay_days;
    const when = dd > 0 ? `<b class="neg">${dd} dni po terminie</b>` : dd < 0 ? `<b class="pos">${-dd} dni przed terminem</b>` : `<b class="pos">w terminie</b>`;
    parts.push(`Wykonano ją <b>${dpl(m.actual_end_date)}</b> — ${when}${m.final_paid ? `; zapłacono <b>${mlnz(m.final_paid)}</b> (${m.cost_dev_pct > 0.005 ? `<b class="neg">${pp(m.cost_dev_pct, 1)}</b>` : m.cost_dev_pct < -0.005 ? `<b>${pp(m.cost_dev_pct, 1)}</b>` : "tyle, ile w umowie"} wobec umowy)` : ""}.`);
  } else parts.push("W BZP nie ma jeszcze ogłoszenia o wykonaniu umowy — realizacja w toku albo brak publikacji.");
  const ch = cs.flatMap((x) => x.changes || []);
  if (ch.length) {
    const causes = ch.slice(0, 3).map((x) => {
      const t = (x.description || "").replace(/\s+/g, " ").replace(/\[data zmiany.*?\]/, "").trim();
      return `<li>${esc(t.slice(0, 160))}${t.length > 160 ? "…" : ""} <span class="muted small">(${esc(x.legal_basis || "podstawa nieokreślona")})</span></li>`;
    }).join("");
    parts.push(`Umowę zmieniano <b>${ch.length} ${ch.length === 1 ? "raz" : "razy"}</b>. Powody:<ul>${causes}</ul>`);
  } else if (m.actual_end_date) parts.push("Umowy nie zmieniano.");
  const issues = d.monitor.filter((x) => x.kind === "jakość danych");
  return `<div class="story"><div class="eyebrow">Historia projektu w skrócie</div><div class="st">${parts.join(" ")}</div>${issues.length ? `<div class="small" style="color:var(--bad);margin-top:6px">⚠ ${esc(issues[0].message)}</div>` : ""}<div class="small muted" style="margin-top:6px">Złożone automatycznie z ogłoszeń BZP (bez modelu językowego) — każda liczba ma źródło w zakładkach poniżej.</div></div>`;
}

// ------------------------------------------------------------ MENU: zwijanie, ostatnio oglądane, wyszukiwarka (Ctrl/⌘+K), puls
function pulseActive() {
  const n = $("#nav a.active .pn");
  if (!n || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  n.classList.remove("pulse"); void n.offsetWidth; n.classList.add("pulse");
}
function setRail(on) {
  $(".layout").classList.toggle("rail", on);
  try { localStorage.setItem("rm_rail", on ? "1" : ""); } catch (e) {}
  $("#collapse").setAttribute("aria-label", on ? "Rozwiń menu" : "Zwiń menu");
}
function rememberProject(p) {
  let r = [];
  try { r = JSON.parse(localStorage.getItem("rm_recent") || "[]"); } catch (e) {}
  r = [{ id: String(p.id), record_id: p.record_id, name: p.name, city: p.city }, ...r.filter((x) => x.id !== String(p.id))].slice(0, 4);
  try { localStorage.setItem("rm_recent", JSON.stringify(r)); } catch (e) {}
  renderRecent();
}
function renderRecent() {
  let r = [];
  try { r = JSON.parse(localStorage.getItem("rm_recent") || "[]"); } catch (e) {}
  $("#recent-grp").hidden = !r.length;
  $("#recent").innerHTML = r.map((x) => `<a href="#/projekt/${esc(x.id)}" data-v="recent" data-pid="${esc(x.id)}" data-rid="${esc((x.record_id || "").replace(/^RM-\d{4}-0*/, ""))}" title="${esc(x.name)}"><span class="pn" aria-hidden="true"></span><span class="rid">${esc((x.record_id || "").replace("RM-2026-", ""))}</span><span class="nl"><span class="nt">${esc(x.city || x.record_id)}</span><span class="nh">${esc(x.name)}</span></span></a>`).join("");
  const h = location.hash.split("/");
  $$("#recent a").forEach((a) => a.classList.toggle("active", h[1] === "projekt" && a.dataset.pid === h[2]));
}

const CMD = { open: false, items: [], sel: 0, projects: null };
const foldq = (t) => (t || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/ł/g, "l");
async function openCmd() {
  CMD.open = true; CMD.sel = 0;
  $("#cmd").classList.remove("hidden");
  $("#cmd-q").value = ""; $("#cmd-q").focus();
  renderCmd();
  try { CMD.projects = await api("/api/projects"); renderCmd(); } catch (e) {}
}
function closeCmd() { CMD.open = false; $("#cmd").classList.add("hidden"); }
function renderCmd() {
  const q = foldq($("#cmd-q").value.trim());
  const acts = [
    { t: "Analizuj nową inwestycję", s: "opis + projekt umowy → prognoza, ryzyka, audyt klauzul", go: "#/nowa", k: "akcja" },
    { t: "Wczytaj demo na prawdziwych danych BZP", s: "22 projekty, 198 ogłoszeń, bez internetu", run: async () => { location.hash = "#/"; const r = await guard(() => post("/api/import-sample?enrich=1&bzp=1")); toast("Wczytuję dane…"); if (r.job_id) setTimeout(() => router(), 4500); }, k: "akcja" },
    ...$$("#nav a[data-v]").filter((a) => a.dataset.v !== "recent").map((a) => ({ t: $(".nt", a).textContent, s: $(".nh", a).textContent, go: a.getAttribute("href"), k: "strona" })),
  ];
  const projs = (CMD.projects || []).map((p) => ({ t: `${p.record_id} · ${p.beneficiary_name}`, s: p.name, go: `#/projekt/${p.id}`, k: "projekt",
    meta: p.metrics && p.metrics.cost_dev_pct != null ? `${pct(p.metrics.cost_dev_pct)} · ${days(p.metrics.delay_days)}` : "",
    hay: foldq([p.record_id, p.name, p.beneficiary_name, p.city, p.voivodeship, p.public_id, p.public_id_normalized].join(" ")) }));
  const match = (x) => !q || q.split(/\s+/).every((w) => (x.hay || foldq(x.t + " " + x.s)).includes(w));
  CMD.items = [...acts.filter(match), ...projs.filter(match)].slice(0, 12);
  CMD.sel = Math.min(CMD.sel, Math.max(0, CMD.items.length - 1));
  $("#cmd-list").innerHTML = CMD.items.map((x, i) => `<div class="ci ${i === CMD.sel ? "sel" : ""}" role="option" aria-selected="${i === CMD.sel}" data-i="${i}"><span class="ck ${x.k}">${esc(x.k)}</span><span class="ct"><b>${esc(x.t)}</b><span>${esc(x.s || "")}</span></span>${x.meta ? `<span class="cm">${esc(x.meta)}</span>` : ""}</div>`).join("")
    || `<div class="cempty">Nic nie pasuje do „${esc($("#cmd-q").value)}”. Spróbuj nazwy gminy albo kodu, np. RM-2026-003.</div>`;
  $$("#cmd-list .ci").forEach((el) => { el.onclick = () => runCmd(Number(el.dataset.i)); el.onmousemove = () => { if (CMD.sel !== Number(el.dataset.i)) { CMD.sel = Number(el.dataset.i); renderCmd(); } }; });
}
function runCmd(i) {
  const x = CMD.items[i]; if (!x) return;
  closeCmd();
  if (x.run) x.run(); else location.hash = x.go;
}
document.addEventListener("keydown", (e) => {
  const typing = /INPUT|TEXTAREA|SELECT/.test((e.target || {}).tagName || "");
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); CMD.open ? closeCmd() : openCmd(); return; }
  if (!CMD.open && !typing && e.key === "/") { e.preventDefault(); openCmd(); return; }
  if (!CMD.open && !typing && e.key === "[") { setRail(!$(".layout").classList.contains("rail")); return; }
  if (!CMD.open) return;
  if (e.key === "Escape") { closeCmd(); }
  else if (e.key === "ArrowDown") { e.preventDefault(); CMD.sel = Math.min(CMD.items.length - 1, CMD.sel + 1); renderCmd(); $("#cmd-list .sel")?.scrollIntoView({ block: "nearest" }); }
  else if (e.key === "ArrowUp") { e.preventDefault(); CMD.sel = Math.max(0, CMD.sel - 1); renderCmd(); $("#cmd-list .sel")?.scrollIntoView({ block: "nearest" }); }
  else if (e.key === "Enter") { e.preventDefault(); runCmd(CMD.sel); }
});
$("#cmd-q").addEventListener("input", () => { CMD.sel = 0; renderCmd(); });
$("#cmd").addEventListener("click", (e) => { if (e.target.id === "cmd") closeCmd(); });
$("#open-cmd").onclick = openCmd;
$("#collapse").onclick = () => setRail(!$(".layout").classList.contains("rail"));
if (/Mac|iPhone|iPad/.test(navigator.platform || "")) { /* ⌘K */ } else { $$("kbd").forEach((k) => { if (k.textContent === "⌘K") k.textContent = "Ctrl K"; }); }
try { if (localStorage.getItem("rm_rail")) setRail(true); } catch (e) {}
renderRecent();

// ------------------------------------------------------------ MAPA POLSKI
// kontur Polski (lon, lat) — uproszczony, do orientacji; położenie projektów wg siedziby gminy (przybliżone)
const PL_OUTLINE = [[14.22,53.93],[14.8,54.05],[15.57,54.18],[16.3,54.4],[16.85,54.59],[17.55,54.76],[18.33,54.83],[18.6,54.72],[18.8,54.61],[18.55,54.42],[18.65,54.37],[19.0,54.35],[19.65,54.45],[20.5,54.40],[21.5,54.33],[22.79,54.36],[23.32,54.25],[23.5,53.95],[23.92,53.6],[23.6,53.1],[23.94,52.7],[23.17,52.28],[23.65,52.08],[23.55,51.6],[23.9,51.0],[24.14,50.86],[23.6,50.4],[22.7,49.95],[22.9,49.5],[22.56,49.08],[21.5,49.4],[20.9,49.33],[20.07,49.18],[19.5,49.6],[18.85,49.5],[18.0,50.0],[17.6,50.27],[16.9,50.45],[16.2,50.6],[15.0,51.0],[14.82,50.87],[15.0,51.25],[14.7,51.6],[14.6,52.0],[14.55,52.6],[14.14,52.86],[14.4,53.3],[14.22,53.93]];
const PL_CITIES = { "Warszawa": [21.01, 52.23], "Kraków": [19.94, 50.06], "Gdańsk": [18.65, 54.35], "Wrocław": [17.03, 51.11], "Poznań": [16.93, 52.41], "Lublin": [22.57, 51.25], "Szczecin": [14.55, 53.43], "Białystok": [23.16, 53.13], "Łódź": [19.46, 51.76], "Katowice": [19.02, 50.26] };
const GMINY = { "Oława": [17.29, 50.94], "Zagrodno": [15.86, 51.18], "Czernikowo": [18.94, 52.95], "Zławieś Wielka": [18.36, 53.08], "Gościeradów Ukazowy": [22.02, 50.87], "Gościeradów": [22.02, 50.87], "Kamionka": [22.48, 51.49], "Biecz": [21.26, 49.73], "Zakrzew": [21.0, 51.44], "Grodzisko Dolne": [22.46, 50.17], "Sanok": [22.2, 49.56], "Kartuzy": [18.2, 54.33], "Bestwina": [19.07, 49.9], "Bobrowniki": [19.0, 50.38], "Elbląg": [19.4, 54.16], "Miłakowo": [20.07, 54.02], "Kleszczewo": [17.16, 52.34], "Zduny": [17.38, 51.65], "Poznań": [16.93, 52.41], "Nowogard": [15.12, 53.67], "Wolin": [14.62, 53.84] };
const WOJ = { "dolnośląskie": [16.4, 51.1], "kujawsko-pomorskie": [18.5, 53.0], "lubelskie": [22.9, 51.2], "lubuskie": [15.3, 52.2], "łódzkie": [19.4, 51.6], "małopolskie": [20.2, 49.9], "mazowieckie": [21.1, 52.4], "opolskie": [17.9, 50.6], "podkarpackie": [22.1, 50.0], "podlaskie": [22.9, 53.3], "pomorskie": [17.9, 54.2], "śląskie": [19.0, 50.4], "świętokrzyskie": [20.8, 50.8], "warmińsko-mazurskie": [20.8, 53.8], "wielkopolskie": [17.3, 52.3], "zachodniopomorskie": [15.5, 53.6] };
function mapBlock(projects) {
  const W = 560, H = 500, pad = 18, k = Math.cos((52 * Math.PI) / 180);
  const lo0 = 14.0, lo1 = 24.3, la0 = 48.9, la1 = 55.0;
  const sx = (W - 2 * pad) / ((lo1 - lo0) * k), sy = (H - 2 * pad) / (la1 - la0), s = Math.min(sx, sy);
  const X = (lon) => pad + (lon - lo0) * k * s, Y = (lat) => pad + (la1 - lat) * s;
  const used = {};
  const pts = projects.map((p) => {
    const m = p.metrics || {};
    let c = GMINY[p.city] || GMINY[(p.beneficiary_name || "").replace(/^Gmina\s+/, "")] || WOJ[(p.voivodeship || "").toLowerCase()];
    if (!c) return null;
    const key = c.join(",");
    const n = (used[key] = (used[key] || 0) + 1) - 1;
    const x = X(c[0]) + (n ? 11 * Math.cos(n * 2.1) : 0), y = Y(c[1]) + (n ? 11 * Math.sin(n * 2.1) : 0);
    const late = m.delay_days > 0, over = m.cost_dev_pct > 0.005, known = m.cost_dev_pct != null || m.delay_days != null;
    const col = !known ? "#9aa8b6" : late && over ? VZ.late : !late && !over ? VZ.early : VZ.plan;
    return { p, m, x, y, col, r: 5 + 7 * Math.sqrt((m.contract_value || 1e6) / 6e6) };
  }).filter(Boolean);
  let g = `<path d="M${PL_OUTLINE.map(([a, b]) => `${X(a).toFixed(1)} ${Y(b).toFixed(1)}`).join("L")}Z" fill="#eef3f7" stroke="#b9c7d4" stroke-width="1.5" stroke-linejoin="round"/>`;
  for (const [name, [a, b]] of Object.entries(PL_CITIES)) g += `<circle cx="${X(a)}" cy="${Y(b)}" r="2.2" fill="#9aa8b6"/><text x="${X(a) + 5}" y="${Y(b) + 4}" font-size="10.5" fill="#8a98a8">${name}</text>`;
  pts.sort((a, b) => b.r - a.r).forEach((q) => {
    const m = q.m;
    g += `<a href="#/projekt/${q.p.id}"><circle cx="${q.x.toFixed(1)}" cy="${q.y.toFixed(1)}" r="${q.r.toFixed(1)}" fill="${q.col}" fill-opacity=".85" stroke="#fff" stroke-width="2" style="cursor:pointer" data-tip="<b>${esc(q.p.record_id)} · ${esc(q.p.city || "")}</b><br>${esc((q.p.name || "").slice(0, 90))}<br>umowa ${pln(m.contract_value)}<br>koszt ${pct(m.cost_dev_pct)} · termin ${days(m.delay_days)}"/></a>`;
  });
  const worst = pts.filter((q) => q.m.delay_days != null).sort((a, b) => (b.m.delay_days || 0) - (a.m.delay_days || 0)).slice(0, 3);
  const costly = pts.filter((q) => q.m.cost_dev_pct != null).sort((a, b) => b.m.cost_dev_pct - a.m.cost_dev_pct).slice(0, 3);
  const byW = {};
  pts.forEach((q) => { const w = q.p.voivodeship || "—"; (byW[w] = byW[w] || []).push(q); });
  const li = (q, v) => `<li><a href="#/projekt/${q.p.id}"><span class="mdot" style="background:${q.col}"></span><b>${esc(q.p.city || q.p.record_id)}</b> <span class="muted">${esc(q.p.record_id)}</span></a><span class="mv">${v}</span></li>`;
  return `<section class="pmap card"><div class="pmap-l"><h2 style="margin:0 0 4px">Mapa inwestycji</h2><p class="small muted" style="margin:0 0 8px">${pts.length} projektów w ${Object.keys(byW).length} województwach. Kolor jak na wykresie powyżej, wielkość = wartość umowy. Kliknij kółko, aby otworzyć projekt.</p>
      <svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Mapa projektów w Polsce">${g}</svg>
      <div class="legend small" style="padding-left:0"><span><i style="background:${VZ.late}"></i>drożej i dłużej</span><span><i style="background:${VZ.plan}"></i>jedno z dwóch</span><span><i style="background:${VZ.early}"></i>w planie</span><span>położenie wg siedziby gminy (przybliżone)</span></div></div>
    <div class="pmap-r"><h3>Najdłuższe opóźnienia</h3><ul class="mlist">${worst.map((q) => li(q, `<b class="neg">+${q.m.delay_days} dni</b>`)).join("")}</ul>
      <h3>Największe przekroczenia kosztu</h3><ul class="mlist">${costly.map((q) => li(q, `<b class="neg">${pp(q.m.cost_dev_pct, 1)}</b>`)).join("")}</ul>
      <h3>Województwa</h3><ul class="mlist">${Object.entries(byW).sort((a, b) => b[1].length - a[1].length).map(([w, qs]) => `<li><span>${esc(w)}</span><span class="mv">${qs.map((q) => `<span class="mdot" title="${esc(q.p.record_id)}" style="background:${q.col}"></span>`).join("")}</span></li>`).join("")}</ul></div></section>`;
}


// ------------------------------------------------------------ start
$("#user").value = localStorage.getItem("rm_user") || "";
const setAvatar = () => { const n = ($("#user").value || "").trim().split(/\s+/).filter(Boolean); $("#avatar").textContent = n.length ? (n[0][0] + (n[1] ? n[1][0] : "")).toUpperCase() : "?"; };
setAvatar();
$("#user").oninput = setAvatar;
$("#user").onchange = (e) => { localStorage.setItem("rm_user", e.target.value || "ekspert"); setAvatar(); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
router();
