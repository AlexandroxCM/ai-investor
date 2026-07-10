"""Manual reset after a drawdown halt. Run this ONLY after reviewing why
the drawdown happened. Resets the halt flag AND the high-water mark to
current equity so the switch re-arms at the new level."""
import json
import sys
from pathlib import Path

state_path = Path(__file__).parent.parent / "runs" / "risk_state.json"
if not state_path.exists():
    print("No risk state file — nothing to reset.")
    sys.exit(0)

state = json.loads(state_path.read_text())
print(f"Current state: {state}")
confirm = input("Reset kill switch? Type 'yes' to confirm: ")
if confirm.strip().lower() == "yes":
    state["halted"] = False
    state["high_water_mark"] = 0.0  # re-arms at next observed equity
    state_path.write_text(json.dumps(state, indent=2))
    print("Kill switch reset. Trading re-enabled on next cycle.")
else:
    print("Aborted.")
