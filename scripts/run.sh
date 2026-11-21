#!/usr/bin/env bash
# Risk Miner — uruchomienie (macOS / Linux). Wymaga Pythona 3.9+.
set -e
cd "$(dirname "$0")/.."
[ -f config.json ] || cp config.example.json config.json
PY=python3
if ! "$PY" -c "import pypdf" 2>/dev/null; then
  if [ -x ".venv/bin/python" ] && .venv/bin/python -c "import pypdf" 2>/dev/null; then
    PY=".venv/bin/python"
  elif ! "$PY" -m pip install --user -q -r requirements-optional.txt 2>/dev/null; then
    if "$PY" -m venv .venv 2>/dev/null && .venv/bin/python -m pip install -q -r requirements-optional.txt 2>/dev/null; then
      PY=".venv/bin/python"
    else
      echo "(pypdf niezainstalowany — PDF przez pdftotext/OCR, jeśli dostępne)"
    fi
  fi
fi
echo "Otwórz: http://127.0.0.1:${RISKMINER_PORT:-8080}"
exec "$PY" app.py
