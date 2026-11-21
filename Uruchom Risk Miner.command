#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
export RISKMINER_OPEN_BROWSER=1
exec ./run.sh
