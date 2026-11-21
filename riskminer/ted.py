"""Klient TED (Tenders Electronic Daily) — API wyszukiwania v3 (bez klucza).

Wykorzystywany dla postępowań publikowanych na poziomie UE. Zapytanie (składnia expert search TED)
jest szablonem w konfiguracji, np. FT ~ ("9121715754") — wyszukiwanie pełnotekstowe NIP zamawiającego.
"""
import json
import os
import urllib.request

from . import config
from .util import now_iso, sha256

FIELDS = ["publication-number", "notice-title", "buyer-name", "publication-date", "notice-type", "buyer-country"]


def search(nip=None, name=None, limit=20, log=None):
    cfg = config.get()["ted"]
    if not cfg.get("enabled"):
        return [], None, None
    query = cfg["query_template"].format(nip=nip or "", name=(name or "").replace('"', ""))
    body = {"query": query, "fields": FIELDS, "limit": limit, "page": 1, "scope": "ALL", "paginationMode": "PAGE_NUMBER"}
    payload = json.dumps(body).encode("utf-8")
    cp = os.path.join(config.get()["data_dir"], "cache", "ted", sha256(payload)[:32] + ".json")
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as f:
            c = json.load(f)
        return c["items"], c["url"], c["fetched_at"]
    req = urllib.request.Request(cfg["search_url"], data=payload, method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=cfg.get("timeout_s", 30)) as r:
        data = json.loads(r.read().decode("utf-8"))
    items = []
    for n in data.get("notices", []):
        pub = n.get("publication-number")
        title = n.get("notice-title")
        if isinstance(title, dict):
            title = title.get("pol") or title.get("eng") or next(iter(title.values()), None)
        buyer = n.get("buyer-name")
        if isinstance(buyer, dict):
            buyer = buyer.get("pol") or next(iter(buyer.values()), None)
        if isinstance(buyer, list):
            buyer = ", ".join(map(str, buyer))
        if isinstance(title, list):
            title = " ".join(map(str, title))
        items.append({
            "publication_number": pub, "title": title, "buyer": buyer,
            "publication_date": (n.get("publication-date") or "")[:10], "notice_type": n.get("notice-type"),
            "url": cfg["notice_url_template"].format(publication_number=pub),
        })
    fetched = now_iso()
    with open(cp, "w", encoding="utf-8") as f:
        json.dump({"items": items, "url": cfg["search_url"] + " q=" + query, "fetched_at": fetched}, f, ensure_ascii=False)
    if log:
        log(f"TED: {query} -> {len(items)}")
    return items, cfg["search_url"] + " q=" + query, fetched
