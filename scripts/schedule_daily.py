"""Runs the full cycle every trading weekday at 4:30pm ET (after close,
with final free data). Leave running, or wire into cron/launchd later.
Usage: python scripts/schedule_daily.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from run_cycle import main as run_cycle_main
from weekly_report import main as weekly_report_main


def job():
    print("=== scheduled cycle starting ===")
    try:
        run_cycle_main()
    except Exception as e:  # a bad cycle must not kill the scheduler
        print(f"cycle failed: {e}")


if __name__ == "__main__":
    sched = BlockingScheduler(timezone="America/New_York")
    sched.add_job(job, CronTrigger(day_of_week="mon-fri", hour=16, minute=30))
    sched.add_job(weekly_report_main, CronTrigger(day_of_week="fri", hour=16, minute=45))
    print("Scheduler armed: weekdays 4:30pm ET cycle, Fridays 4:45pm ET weekly report.")
    sched.start()
