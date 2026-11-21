"""Konfiguracja: config.json (lub plik z RISKMINER_CONFIG) + nadpisania zmiennymi środowiskowymi.

Zmiana modelu językowego, dostawcy czy źródła BZP odbywa się wyłącznie w konfiguracji — bez zmian w kodzie.
"""
import copy
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "server": {"host": "127.0.0.1", "port": 8080},
    "data_dir": "data",
    "bzp": {
        # Kopia API BZP udostępniona przez organizatora (ten sam interfejs, bez limitu zapytań).
        # Produkcyjnie: "https://ezamowienia.gov.pl/mo-board/api/v1/notice" i requests_per_minute = 25.
        "base_url": "https://bzp.cytr.us/mo-board/api/v1/notice",
        "fallback_urls": ["https://ezamowienia.gov.pl/mo-board/api/v1/notice"],
        "notice_url_template": "https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/id/{objectId}",
        "requests_per_minute": 0,
        "timeout_s": 30,
        "page_size": 500,
        "max_pages": 20,
        # typy sprawdzone na API (inne nazwy, np. ContractModificationNotice, API odrzuca kodem 400)
        "related_notice_types": [
            "TenderResultNotice",
            "AgreementUpdateNotice",
            "ContractPerformingNotice",
            "NoticeUpdateNotice",
        ],
        "search_window_years_after": 4,
        "cache": True,
    },
    "ted": {
        "enabled": True,
        "search_url": "https://api.ted.europa.eu/v3/notices/search",
        "query_template": "FT ~ (\"{nip}\")",
        "notice_url_template": "https://ted.europa.eu/pl/notice/-/detail/{publication_number}",
        "timeout_s": 30,
    },
    "llm": {
        # provider: "none" | "openai" (także zgodne: Ollama, vLLM, LM Studio, Azure-compat) | "anthropic"
        "provider": "none",
        "model": "",
        "base_url": "",
        "api_key_env": "RISKMINER_LLM_API_KEY",
        "temperature": 0.0,
        "max_tokens": 1500,
        "timeout_s": 90,
        "data_location": "nie dotyczy (LLM wyłączony)",
        "max_chars_per_document": 60000,
    },
    "monitor": {"interval_minutes": 0, "only_unfinished": True},
    "analysis": {
        "top_k": 6,
        "min_similarity": 0.15,
        "weights": {
            "text": 0.40,
            "subsector": 0.20,
            "work_type": 0.08,
            "formula": 0.08,
            "value": 0.12,
            "length": 0.07,
            "region": 0.05,
        },
    },
    "link_auto_accept_confidence": 0.95,
}


def _merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load():
    path = os.environ.get("RISKMINER_CONFIG") or os.path.join(BASE_DIR, "config.json")
    cfg = DEFAULTS
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg = _merge(DEFAULTS, json.load(f))
    cfg = copy.deepcopy(cfg)
    env = os.environ
    if env.get("RISKMINER_PORT"):
        cfg["server"]["port"] = int(env["RISKMINER_PORT"])
    if env.get("RISKMINER_HOST"):
        cfg["server"]["host"] = env["RISKMINER_HOST"]
    if env.get("RISKMINER_BZP_URL"):
        cfg["bzp"]["base_url"] = env["RISKMINER_BZP_URL"]
    for key in ("provider", "model", "base_url"):
        ek = "RISKMINER_LLM_" + key.upper()
        if env.get(ek):
            cfg["llm"][key] = env[ek]
    data_dir = cfg["data_dir"]
    if not os.path.isabs(data_dir):
        data_dir = os.path.join(BASE_DIR, data_dir)
    cfg["data_dir"] = data_dir
    os.makedirs(os.path.join(data_dir, "cache", "bzp"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "cache", "ted"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "documents"), exist_ok=True)
    cfg["_config_path"] = path
    return cfg


def public_view(cfg):
    """Konfiguracja do pokazania w UI — bez sekretów."""
    v = copy.deepcopy(cfg)
    key_env = v["llm"].get("api_key_env")
    v["llm"]["api_key_set"] = bool(key_env and os.environ.get(key_env))
    return v


CFG = None


def get():
    global CFG
    if CFG is None:
        CFG = load()
    return CFG
