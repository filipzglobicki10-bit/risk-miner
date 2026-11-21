#!/usr/bin/env bash
# Risk Miner — uruchomienie (macOS / Linux). Wymaga Pythona 3.9+. Brak obowiązkowych zależności.
set -e
cd "$(dirname "$0")"
[ -f config.json ] || cp config.example.json config.json
# opcjonalnie: odczyt PDF (pypdf). Bez niego PDF czytane przez pdftotext, jeśli jest w systemie.
python3 -c "import pypdf" 2>/dev/null || python3 -m pip install --user -q -r requirements-optional.txt 2>/dev/null || echo "(pypdf niezainstalowany — PDF przez pdftotext/OCR, jeśli dostępne)"
echo "Otwórz: http://127.0.0.1:${RISKMINER_PORT:-8080}"
exec python3 app.py
