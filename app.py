#!/usr/bin/env python3
"""Risk Miner — uruchomienie: python3 app.py  (wymaga Pythona 3.9+, bez dodatkowych pakietów).

Opcja --open (lub RISKMINER_OPEN_BROWSER=1): automatycznie otwiera aplikację w przeglądarce;
jeśli serwer już działa na tym porcie, po prostu otwiera istniejącą instancję.
"""
import os
import sys
import threading
import time
import urllib.request
import webbrowser

if sys.version_info < (3, 9):
    sys.exit("Risk Miner wymaga Pythona 3.9 lub nowszego.")

from riskminer import config, server


def _is_alive(url):
    try:
        with urllib.request.urlopen(url + "/api/status", timeout=1.0) as r:
            return r.status == 200
    except Exception:
        return False


def _open_when_ready(url):
    for _ in range(75):
        if _is_alive(url):
            webbrowser.open(url)
            return
        time.sleep(0.2)


if __name__ == "__main__":
    want_open = "--open" in sys.argv or os.environ.get("RISKMINER_OPEN_BROWSER") == "1"
    cfg = config.get()
    host = cfg["server"]["host"]
    port = cfg["server"]["port"]
    browser_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    url = f"http://{browser_host}:{port}"
    if want_open:
        if _is_alive(url):
            print(f"Risk Miner już działa pod adresem {url} — otwieram przeglądarkę.")
            webbrowser.open(url)
            sys.exit(0)
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    server.serve()
