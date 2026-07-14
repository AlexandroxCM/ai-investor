"""Installs a macOS launchd job: daily cycle 1:35pm PT (4:35pm ET) weekdays,
plus the weekly report after Friday's cycle. Survives reboots; runs with no
terminal open (Mac must be awake). Usage:
    python scripts/install_autostart.py            # install + load
    python scripts/install_autostart.py remove     # uninstall
Logs land in runs/autostart.log."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLIST = Path.home() / "Library/LaunchAgents/com.ai-investor.daily.plist"
PYTHON = sys.executable

DAY_ENTRIES = "\n".join(
    f"    <dict><key>Weekday</key><integer>{d}</integer>"
    f"<key>Hour</key><integer>13</integer>"
    f"<key>Minute</key><integer>35</integer></dict>"
    for d in range(1, 6))

SHELL_CMD = (f"cd {ROOT} && {PYTHON} scripts/run_cycle.py >> runs/autostart.log 2>&1; "
             f"if [ $(date +%u) = 5 ]; then sleep 900 && {PYTHON} "
             f"scripts/weekly_report.py >> runs/autostart.log 2>&1; fi")

TEMPLATE = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ai-investor.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string><string>-c</string>
    <string>{SHELL_CMD}</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
{DAY_ENTRIES}
  </array>
</dict></plist>
"""


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "remove":
        subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
        PLIST.unlink(missing_ok=True)
        print("Autostart removed.")
        return
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_text(TEMPLATE)
    subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
    result = subprocess.run(["launchctl", "load", str(PLIST)],
                            capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Autostart installed: weekdays 1:35pm PT (4:35pm ET).")
        print(f"Plist: {PLIST}")
        print(f"Logs:  {ROOT}/runs/autostart.log")
        print("Remove with: python scripts/install_autostart.py remove")
    else:
        print(f"launchctl load failed: {result.stderr}")


if __name__ == "__main__":
    main()
