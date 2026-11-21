"""Baza SQLite: model danych odwzorowujący strukturę projektu i jego realizacji.

projekt 1—N postępowanie 1—N ogłoszenie
              postępowanie 1—N umowa 1—N zmiana umowy
projekt 1—N zdarzenie (ryzyko) — każde ze źródłem (dokument/ogłoszenie, strona, cytat)
projekt 1—N fakt (koszt / termin) — każdy ze źródłem
każdy rekord -> source (identyfikator źródła, link, data pobrania)
links: propozycje powiązań z poziomem pewności i podstawą dopasowania (do weryfikacji eksperckiej)
audit_log: historia wszystkich operacji i decyzji ekspertów
"""
import json
import os
import sqlite3
import threading

from . import config
from .util import now_iso

_LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- xlsx | bzp | ted | upload | url | manual | computed | llm
    title TEXT,
    url TEXT,
    ref TEXT,                        -- identyfikator w źródle (nr ogłoszenia, nazwa pliku, arkusz:wiersz)
    fetched_at TEXT,
    sha256 TEXT,
    meta TEXT
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    record_id TEXT UNIQUE,
    name TEXT NOT NULL,
    beneficiary_name TEXT,
    beneficiary_id_type TEXT,
    beneficiary_id TEXT,
    beneficiary_type TEXT,
    nip_valid INTEGER,
    country TEXT,
    teryt TEXT,
    voivodeship TEXT,
    city TEXT,
    scope TEXT,
    public_id_type TEXT,
    public_id TEXT,
    public_id_normalized TEXT,
    theme TEXT,
    order_type TEXT,
    legal_regime TEXT,
    currency TEXT,
    status TEXT,
    record_source TEXT,
    record_date TEXT,
    record_version TEXT,
    annotation TEXT,
    description TEXT,
    subsector_main TEXT,
    subsectors_extra TEXT,
    work_type TEXT,
    formula TEXT,
    length_km REAL,
    is_exemplar INTEGER DEFAULT 0,
    needs_review INTEGER DEFAULT 0,
    enrich_status TEXT,
    enrich_log TEXT,
    last_checked TEXT,
    source_id INTEGER,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS procurements (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    bzp_number TEXT,
    tender_id TEXT,
    title TEXT,
    cpv TEXT,
    order_type TEXT,
    organization_name TEXT,
    organization_nip TEXT,
    organization_id TEXT,
    publication_date TEXT,
    result TEXT,
    n_offers INTEGER,
    link_id INTEGER,
    source_id INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY,
    procurement_id INTEGER,
    project_id INTEGER,
    notice_type TEXT,
    notice_number TEXT,
    bzp_number TEXT,
    object_id TEXT,
    tender_id TEXT,
    publication_date TEXT,
    title TEXT,
    url TEXT,
    text TEXT,
    raw_json TEXT,
    link_id INTEGER,
    source_id INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY,
    procurement_id INTEGER,
    project_id INTEGER,
    part TEXT,
    contractor_name TEXT,
    contractor_nip TEXT,
    contractor_city TEXT,
    value_gross REAL,
    signed_date TEXT,
    planned_end_date TEXT,
    actual_end_date TEXT,
    final_paid REAL,
    performed_properly TEXT,
    changed TEXT,
    status TEXT,
    source_id INTEGER,
    quote TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS contract_changes (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER,
    project_id INTEGER,
    change_date TEXT,
    legal_basis TEXT,
    description TEXT,
    value_change REAL,
    term_change_days INTEGER,
    source_id INTEGER,
    notice_id INTEGER,
    document_id INTEGER,
    quote TEXT,
    fingerprint TEXT,
    status TEXT DEFAULT 'proposed',
    part INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    procurement_id INTEGER,
    contract_id INTEGER,
    key TEXT NOT NULL,               -- project_value, funding, estimated_value_net, budget_amount, offer_min, offer_max,
                                     -- n_offers, contract_value, signed_date, planned_end_date, actual_end_date, final_paid ...
    value_num REAL,
    value_text TEXT,
    unit TEXT,
    vat TEXT,                        -- netto | brutto | nd
    source_id INTEGER,
    notice_id INTEGER,
    document_id INTEGER,
    page INTEGER,
    quote TEXT,
    confidence REAL,
    method TEXT,                     -- xlsx | notice-parser | rule | llm | computed | manual
    status TEXT DEFAULT 'proposed',  -- proposed | approved | rejected | superseded
    part INTEGER,                    -- część postępowania (gdy zamówienie podzielone na części)
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    analysis_id INTEGER,
    filename TEXT,
    doc_type TEXT,
    phase TEXT,
    pages_json TEXT,                 -- [ {"page":1,"text":"..."} ]
    n_pages INTEGER,
    ocr_used INTEGER DEFAULT 0,
    is_exemplar INTEGER DEFAULT 0,
    source_id INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    procurement_id INTEGER,
    contract_id INTEGER,
    risk_code TEXT,
    event_type TEXT,
    title TEXT,
    snippet TEXT,
    quote TEXT,
    page INTEGER,
    document_id INTEGER,
    notice_id INTEGER,
    source_id INTEGER,
    cost_impact REAL,
    delay_days INTEGER,
    cause TEXT,
    mitigation TEXT,
    mitigation_effective TEXT,
    confidence REAL,
    method TEXT,                     -- rule | llm | computed | manual
    rule_id TEXT,
    fingerprint TEXT,
    status TEXT DEFAULT 'proposed',  -- proposed | approved | rejected | edited
    is_exemplar INTEGER DEFAULT 0,
    reviewer TEXT,
    review_comment TEXT,
    reviewed_at TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    from_type TEXT, from_id INTEGER,
    to_type TEXT, to_ref TEXT,
    basis TEXT,                      -- JSON: lista przesłanek dopasowania
    confidence REAL,
    method TEXT,                     -- identifier | text-match | manual
    status TEXT DEFAULT 'proposed',  -- auto | proposed | approved | rejected
    reviewer TEXT, review_comment TEXT, reviewed_at TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS risk_catalog (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    effects TEXT,
    patterns TEXT,                   -- JSON lista wyrażeń regularnych (na tekście bez polskich znaków)
    mitigations TEXT,                -- JSON lista
    clauses TEXT,                    -- JSON lista propozycji zapisów umownych
    checks TEXT,                     -- JSON lista kwestii do sprawdzenia przed uruchomieniem
    sector TEXT DEFAULT 'wod-kan',
    status TEXT DEFAULT 'approved',  -- approved | proposed | rejected
    proposed_by TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS event_types (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    risk_codes TEXT,                 -- JSON lista kodów ryzyka
    patterns TEXT,                   -- JSON
    status TEXT DEFAULT 'approved',
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS knowledge (
    key TEXT PRIMARY KEY,            -- subsectors | checklist | doc_expectations | sector_description | weights
    value TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS rule_feedback (
    id INTEGER PRIMARY KEY,
    rule_id TEXT,
    fingerprint TEXT,
    decision TEXT,                   -- approved | rejected
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY,
    title TEXT,
    input_text TEXT,
    result_json TEXT,
    status TEXT DEFAULT 'draft',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS monitor_events (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    kind TEXT,
    message TEXT,
    notice_id INTEGER,
    document_id INTEGER,
    created_at TEXT,
    acknowledged INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    kind TEXT, status TEXT, progress REAL, message TEXT, log TEXT,
    created_at TEXT, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    ts TEXT, actor TEXT, action TEXT, entity TEXT, entity_id TEXT, before TEXT, after TEXT, comment TEXT
);
CREATE INDEX IF NOT EXISTS ix_proc_project ON procurements(project_id);
CREATE INDEX IF NOT EXISTS ix_not_project ON notices(project_id);
CREATE INDEX IF NOT EXISTS ix_ev_project ON events(project_id);
CREATE INDEX IF NOT EXISTS ix_fact_project ON facts(project_id);
CREATE INDEX IF NOT EXISTS ix_link_project ON links(project_id);
CREATE INDEX IF NOT EXISTS ix_doc_project ON documents(project_id);
"""

_CONN = None


def path():
    return os.path.join(config.get()["data_dir"], "riskminer.sqlite")


def conn():
    global _CONN
    with _LOCK:
        if _CONN is None:
            _CONN = _open("WAL")
        return _CONN


def _open(mode):
    """WAL na dyskach lokalnych; na dyskach sieciowych/zamontowanych (brak mmap) tryb TRUNCATE."""
    c = sqlite3.connect(path(), check_same_thread=False, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        c.execute(f"PRAGMA journal_mode={mode}")
        c.executescript(SCHEMA)
        for table, col, typ in (("facts", "part", "INTEGER"), ("contract_changes", "part", "INTEGER"), ("contract_changes", "fingerprint", "TEXT")):
            cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
            if col not in cols:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        # Migracja starszych rekordów contract_changes, w których kolumna quote trzymała 24-znakowy hash fingerprint
        c.execute(
            "UPDATE contract_changes SET fingerprint=quote, quote=COALESCE("
            "(SELECT e.quote FROM events e WHERE e.project_id=contract_changes.project_id AND e.fingerprint=contract_changes.quote LIMIT 1), "
            "description) WHERE fingerprint IS NULL AND length(quote)=24 AND quote NOT LIKE '% %'"
        )
        c.commit()
        return c
    except sqlite3.OperationalError:
        c.close()
        if mode == "WAL":
            return _open("TRUNCATE")
        raise


def reset():
    """Usuwa bazę (używane w testach)."""
    global _CONN
    with _LOCK:
        if _CONN is not None:
            _CONN.close()
            _CONN = None
        for suffix in ("", "-wal", "-shm"):
            p = path() + suffix
            if os.path.exists(p):
                os.remove(p)


def q(sql, params=()):
    with _LOCK:
        cur = conn().execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def q1(sql, params=()):
    rows = q(sql, params)
    return rows[0] if rows else None


def x(sql, params=()):
    with _LOCK:
        c = conn()
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid


def insert(table, data):
    data = {k: _enc(v) for k, v in data.items()}
    if "created_at" in _columns(table) and "created_at" not in data:
        data["created_at"] = now_iso()
    cols = ",".join(data)
    qs = ",".join("?" for _ in data)
    return x(f"INSERT INTO {table} ({cols}) VALUES ({qs})", tuple(data.values()))


def update(table, row_id, data, key="id"):
    if not data:
        return
    data = {k: _enc(v) for k, v in data.items()}
    if "updated_at" in _columns(table) and "updated_at" not in data:
        data["updated_at"] = now_iso()
    sets = ",".join(f"{k}=?" for k in data)
    x(f"UPDATE {table} SET {sets} WHERE {key}=?", tuple(data.values()) + (row_id,))


def get(table, row_id, key="id"):
    return q1(f"SELECT * FROM {table} WHERE {key}=?", (row_id,))


_COLS = {}


def _columns(table):
    if table not in _COLS:
        _COLS[table] = [r["name"] for r in q(f"PRAGMA table_info({table})")]
    return _COLS[table]


def _enc(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return int(v)
    return v


def jload(v, default=None):
    if v is None or v == "":
        return default
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return default


def audit(action, entity, entity_id=None, before=None, after=None, comment=None, actor="system"):
    insert(
        "audit_log",
        {
            "ts": now_iso(),
            "actor": actor,
            "action": action,
            "entity": entity,
            "entity_id": str(entity_id) if entity_id is not None else None,
            "before": before,
            "after": after,
            "comment": comment,
        },
    )


def add_source(kind, title=None, url=None, ref=None, fetched_at=None, sha=None, meta=None):
    existing = None
    if url or ref:
        existing = q1(
            "SELECT * FROM sources WHERE kind=? AND IFNULL(url,'')=IFNULL(?, '') AND IFNULL(ref,'')=IFNULL(?, '')",
            (kind, url, ref),
        )
    if existing:
        if fetched_at:
            update("sources", existing["id"], {"fetched_at": fetched_at, "sha256": sha or existing["sha256"]})
        return existing["id"]
    return insert(
        "sources",
        {"kind": kind, "title": title, "url": url, "ref": ref, "fetched_at": fetched_at or now_iso(), "sha256": sha, "meta": meta},
    )
