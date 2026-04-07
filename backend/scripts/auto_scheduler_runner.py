#!/usr/bin/env python3
"""
Auto Scheduler Runner

This script automatically runs the probabilistic schedulers on a schedule:
- run_probabilistic_scheduler: every 1 hour
- run_probabilistic_detective_scheduler: every 2 hours

Usage:
    python auto_scheduler_runner.py [--base-url BASE_URL]

Arguments:
    --base-url    Base URL of the API server (default: http://localhost:8000)
"""

from __future__ import annotations

import os
import sys
import time
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatically run probabilistic schedulers on a schedule"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL of the API server (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--actors",
        type=str,
        default="",
        help="Comma-separated actor ids (default: empty, uses all actors)",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=1,
        help="How many dispatch cycles to run per scheduler execution (default: 1)",
    )
    return parser.parse_args()


def run_scheduler(scheduler_script: str, args: argparse.Namespace) -> bool:
    """Run a scheduler script and return True if successful."""
    script_path = ROOT_DIR / "scripts" / scheduler_script
    
    if not script_path.exists():
        print(f"[ERROR] Scheduler script not found: {script_path}")
        return False
    
    cmd = [
        sys.executable,
        str(script_path),
        "--cycles", str(args.cycles),
    ]
    
    if args.actors:
        cmd.extend(["--actors", args.actors])
    
    print(f"\n{'='*60}")
    print(f"[{datetime.now(timezone.utc).isoformat()}] Running: {scheduler_script}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    
    try:
        result = subprocess.run(cmd, cwd=str(ROOT_DIR), check=False)
        if result.returncode == 0:
            print(f"[SUCCESS] {scheduler_script} completed successfully")
            return True
        else:
            print(f"[ERROR] {scheduler_script} failed with exit code {result.returncode}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to run {scheduler_script}: {e}")
        return False


def main() -> None:
    args = parse_args()
    
    print(f"\n{'='*60}")
    print("Auto Scheduler Runner Started")
    print(f"{'='*60}")
    print(f"Base URL: {args.base_url}")
    print(f"Actors: {args.actors or 'all'}")
    print(f"Cycles per run: {args.cycles}")
    print(f"Schedule:")
    print(f"  - run_probabilistic_scheduler: every 1 hour")
    print(f"  - run_probabilistic_detective_scheduler: every 2 hours")
    print(f"{'='*60}\n")
    
    scheduler_interval = 3600  # 1 hour in seconds
    detective_scheduler_interval = 7200  # 2 hours in seconds
    
    last_scheduler_run = 0.0
    last_detective_scheduler_run = 0.0
    
    start_time = time.time()
    
    while True:
        current_time = time.time()
        elapsed = current_time - start_time
        
        # Check if it's time to run the regular scheduler (every 1 hour)
        if elapsed - last_scheduler_run >= scheduler_interval:
            success = run_scheduler("run_probabilistic_scheduler.py", args)
            if success:
                last_scheduler_run = elapsed
                next_run = scheduler_interval - (elapsed % scheduler_interval)
                print(f"\n[INFO] Next regular scheduler run in {next_run / 60:.1f} minutes")
        
        # Check if it's time to run the detective scheduler (every 2 hours)
        if elapsed - last_detective_scheduler_run >= detective_scheduler_interval:
            success = run_scheduler("run_probabilistic_detective_scheduler.py", args)
            if success:
                last_detective_scheduler_run = elapsed
                next_run = detective_scheduler_interval - (elapsed % detective_scheduler_interval)
                print(f"\n[INFO] Next detective scheduler run in {next_run / 60:.1f} minutes")
        
        # Sleep for 1 minute before checking again
        time.sleep(60)
        
        # Print status every hour
        if int(elapsed) % 3600 < 60 and elapsed > 0:
            print(f"\n[STATUS] Runner has been running for {elapsed / 3600:.2f} hours")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Auto Scheduler Runner stopped by user")
        sys.exit(0)
