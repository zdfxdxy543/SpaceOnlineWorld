from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run story scheduler and print generated content/results.")
    parser.add_argument("--goal", required=True, help="High-level goal for the scheduler")
    parser.add_argument(
        "--actors",
        default="",
        help="Comma-separated actor ids, e.g. aria,milo. Leave empty to auto-select.",
    )
    parser.add_argument(
        "--spawn-probability",
        type=float,
        default=None,
        help="Optional override for SCHEDULER_NEW_ACTOR_PROBABILITY (0.0 to 1.0).",
    )
    return parser.parse_args()


def _format_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def main() -> None:
    args = parse_args()

    if args.spawn_probability is not None:
        clamped = max(0.0, min(1.0, args.spawn_probability))
        os.environ["SCHEDULER_NEW_ACTOR_PROBABILITY"] = str(clamped)

    from app.main import create_app

    app = create_app()
    client = TestClient(app)

    actors = [item.strip() for item in args.actors.split(",") if item.strip()]
    payload = {
        "goal": args.goal,
        "actors": actors,
    }

    response = client.post("/api/v1/ai/scheduler/run", json=payload)
    if response.status_code >= 400:
        print(f"Scheduler call failed: HTTP {response.status_code}")
        print(_format_json(response.json()))
        raise SystemExit(1)

    data = response.json()
    print("Scheduler run completed.")
    print(f"story_id: {data.get('story_id')}")
    print(f"status: {data.get('status')}")
    print(f"spawn_triggered: {data.get('spawn_triggered')}")
    print(f"spawned_actor_id: {data.get('spawned_actor_id')}")

    results = data.get("results", [])
    print(f"steps_executed: {len(results)}")
    for idx, item in enumerate(results, start=1):
        capability = item.get("capability")
        status = item.get("status")
        facts = item.get("facts", [])
        print(f"[{idx}] {capability} -> {status} | facts={len(facts)}")

    print("\nFull scheduler response:")
    print(_format_json(data))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(
            [
                "--goal",
                "Generate a story about something suspicious.",
                "--spawn-probability",
                "0.3",
            ]
        )
    main()
