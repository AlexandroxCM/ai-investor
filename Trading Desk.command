#!/bin/zsh
# Double-click to open the ai-investor dashboard in your browser.
cd "$(dirname "$0")"
echo "Starting audit desk — closing this window stops the dashboard."
python scripts/dashboard.py
