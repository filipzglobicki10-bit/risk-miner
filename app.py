#!/usr/bin/env python3
"""Risk Miner — uruchomienie: python3 app.py  (wymaga Pythona 3.9+, bez dodatkowych pakietów)."""
import sys

if sys.version_info < (3, 9):
    sys.exit("Risk Miner wymaga Pythona 3.9 lub nowszego.")

from riskminer.server import serve

if __name__ == "__main__":
    serve()
