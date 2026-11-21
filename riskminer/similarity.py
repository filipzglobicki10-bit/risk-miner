"""Wyszukiwanie podobnych inwestycji: hybryda treści (TF-IDF) i cech strukturalnych, z wyjaśnieniem wyniku."""
import json
import math
from collections import Counter

from . import config, db, rules
from .util import extract_length_km, log_ratio_sim, tokens


def project_text(p, with_docs=True):
    parts = [p.get("name") or "", p.get("description") or "", p.get("subsector_main") or ""]
    for pr in db.q("SELECT title FROM procurements WHERE project_id=?", (p["id"],)):
        parts.append(pr["title"] or "")
    if with_docs:
        for d in db.q("SELECT pages_json FROM documents WHERE project_id=?", (p["id"],)):
            pages = db.jload(d["pages_json"], [])
            parts.append(" ".join(pg["text"] for pg in pages)[:4000])
    return " ".join(parts)


class Index:
    def __init__(self, docs):
        """docs: {id: text}"""
        self.tf = {i: Counter(tokens(t)) for i, t in docs.items()}
        df = Counter()
        for c in self.tf.values():
            df.update(set(c))
        n = max(1, len(docs))
        self.idf = {t: math.log((n + 1) / (d + 1)) + 1 for t, d in df.items()}
        self.vec = {i: self._vec(c) for i, c in self.tf.items()}

    def _vec(self, counts):
        v = {t: (1 + math.log(c)) * self.idf.get(t, math.log(len(self.tf) + 1) + 1) for t, c in counts.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        return {t: x / norm for t, x in v.items()}

    def query(self, text):
        q = self._vec(Counter(tokens(text)))
        out = {}
        for i, v in self.vec.items():
            common = set(q) & set(v)
            s = sum(q[t] * v[t] for t in common)
            top = sorted(common, key=lambda t: -(q[t] * v[t]))[:6]
            out[i] = (s, top)
        return out


def features_from_text(text, extra=None):
    main, subs = rules.classify_subsectors(text)
    f = {"subsector_main": main, "subsectors_extra": subs, "work_type": rules.work_type(text), "formula": rules.formula(text),
         "length_km": extract_length_km(text)}
    f.update({k: v for k, v in (extra or {}).items() if v not in (None, "")})
    return f


def find_similar(text, feats, exclude_id=None, only_completed=False, metrics_fn=None):
    cfg = config.get()["analysis"]
    w = cfg["weights"]
    projects = db.q("SELECT * FROM projects")
    if exclude_id:
        projects = [p for p in projects if p["id"] != exclude_id]
    if not projects:
        return []
    idx = Index({p["id"]: project_text(p) for p in projects})
    tsim = idx.query(text)
    max_t = max((s for s, _ in tsim.values()), default=0) or 1
    out = []
    for p in projects:
        m = metrics_fn(p["id"]) if metrics_fn else {}
        contrib = []
        s_text, top_terms = tsim.get(p["id"], (0, []))
        s_text_n = s_text / max_t
        contrib.append(("text", w["text"] * s_text_n, f"podobieństwo treści opisu {s_text:.2f} (wspólne rdzenie słów: {', '.join(top_terms) or '—'})"))
        p_subs = set([p.get("subsector_main")] + (db.jload(p.get("subsectors_extra"), []) or []))
        q_subs = set([feats.get("subsector_main")] + (feats.get("subsectors_extra") or []))
        if p.get("subsector_main") == feats.get("subsector_main"):
            s_sub = 1.0
            why = f"ten sam podsektor główny: {p.get('subsector_main')}"
        else:
            inter = len(p_subs & q_subs)
            s_sub = 0.5 * inter / max(1, len(p_subs | q_subs))
            why = f"podsektory: {', '.join(sorted(p_subs & q_subs)) or 'brak wspólnych'}"
        contrib.append(("subsector", w["subsector"] * s_sub, why))
        s_wt = 1.0 if p.get("work_type") == feats.get("work_type") else 0.3
        contrib.append(("work_type", w["work_type"] * s_wt, f"rodzaj prac: {p.get('work_type')}"))
        s_f = 1.0 if p.get("formula") == feats.get("formula") else 0.0
        contrib.append(("formula", w["formula"] * s_f, f"formuła: {p.get('formula')}"))
        pv = m.get("value_for_comparison")
        vs = log_ratio_sim(pv, feats.get("value"))
        if vs is not None:
            contrib.append(("value", w["value"] * vs, f"wartość {pv:,.0f} zł vs {feats['value']:,.0f} zł".replace(",", " ")))
        ls = log_ratio_sim(p.get("length_km"), feats.get("length_km"), span=8)
        if ls is not None:
            contrib.append(("length", w["length"] * ls, f"długość sieci {p['length_km']:.1f} km vs {feats['length_km']:.1f} km"))
        if feats.get("voivodeship") and p.get("voivodeship"):
            same = feats["voivodeship"].lower() == p["voivodeship"].lower()
            contrib.append(("region", w["region"] * (1 if same else 0), f"województwo: {p['voivodeship']}"))
        # normalizacja do sumy wag cech, które dało się porównać
        used = {k for k, _, _ in contrib}
        denom = sum(w[k] for k in used) or 1
        score = sum(v for _, v, _ in contrib) / denom
        if p.get("is_exemplar"):
            score = min(1.0, score * 1.1)
            contrib.append(("exemplar", 0, "projekt oznaczony przez eksperta jako wzorcowy (+10%)"))
        out.append({
            "project_id": p["id"], "record_id": p["record_id"], "name": p["name"], "beneficiary": p["beneficiary_name"],
            "voivodeship": p["voivodeship"], "status": p["status"], "subsector": p["subsector_main"],
            "score": round(score, 3),
            "explanation": [{"feature": k, "contribution": round(v / denom, 3), "why": why} for k, v, why in sorted(contrib, key=lambda c: -c[1])],
            "metrics": m,
        })
    out.sort(key=lambda r: -r["score"])
    if only_completed:
        out = [r for r in out if (r["status"] or "").lower().startswith("zako")]
    return out
