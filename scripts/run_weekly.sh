#!/bin/sh
cd "$(dirname "$0")/.." || exit 1
.venv/bin/python -m scripts.run_weekly
