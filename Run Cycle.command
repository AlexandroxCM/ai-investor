#!/bin/zsh
# Double-click to run one full trading cycle, then keep the window open.
cd "$(dirname "$0")"
python scripts/run_cycle.py
echo ""
echo "Cycle complete. Press Enter to close."
read
