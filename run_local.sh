#!/bin/sh
cd "$(dirname "$0")" || exit 1
VLUX_SQLITE_PATH="$(pwd)/storage/vlux_clean.sqlite3" VLUX_MODE=local VLUX_DB=sqlite VLUX_HOST=127.0.0.1 VLUX_PORT=8765 python3 backend/app.py
