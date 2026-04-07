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
    parser.add_argument("--goal", default="", help="High-level goal for the scheduler")
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
    parser.add_argument(
        "--news-free-test",
        action="store_true",
        help="Run a multi-scenario scheduler test focused on news-page related capabilities.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="How many runs to execute per scenario in --news-free-test mode.",
    )
    return parser.parse_args()


def _format_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _run_scheduler_once(client: TestClient, *, goal: str, actors: list[str]) -> dict:
    payload = {
        "goal": goal,
        "actors": actors,
    }
    response = client.post("/api/v1/ai/scheduler/run", json=payload)
    if response.status_code >= 400:
        raise RuntimeError(f"Scheduler call failed: HTTP {response.status_code} {response.text}")
    return response.json()


def _print_single_run(data: dict) -> None:
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


def _run_news_free_test(client: TestClient, *, actors: list[str], iterations: int) -> None:
    caps_resp = client.get("/api/v1/ai/capabilities")
    if caps_resp.status_code >= 400:
        raise RuntimeError(f"Failed to list capabilities: HTTP {caps_resp.status_code} {caps_resp.text}")
    capability_names = {item.get("name", "") for item in caps_resp.json()}

    required = {"news.publish_article", "netdisk.upload_file", "netdisk.create_share_link", "forum.create_thread"}
    missing = sorted(required - capability_names)
    print("News scheduler freedom test started.")
    print(f"registered_capabilities={len(capability_names)}")
    print(f"required_capabilities_present={not missing}")
    if missing:
        print(f"missing_required_capabilities={missing}")

    scenarios = [
        {
            "name": "news_only",
            "goal": "Publish a community news article about unusual activity in town.",
            "expect": {"news.publish_article"},
        },
        {
            "name": "news_with_share",
            "goal": "Upload evidence to netdisk, create a share link, and publish a news article that references the share_id.",
            "expect": {"news.publish_article", "netdisk.upload_file", "netdisk.create_share_link"},
        },
        {
            "name": "forum_netdisk_news",
            "goal": "Create a forum thread with evidence from netdisk and then publish a news article cross-referencing the thread and share.",
            "expect": {"news.publish_article", "forum.create_thread", "netdisk.upload_file", "netdisk.create_share_link"},
        },
    ]

    iterations = max(1, iterations)
    total_runs = 0
    success_runs = 0
    news_success_runs = 0

    for scenario in scenarios:
        print("\n----------------------------------------")
        print(f"scenario: {scenario['name']}")
        print(f"goal: {scenario['goal']}")
        matched_expected_count = 0

        for idx in range(1, iterations + 1):
            total_runs += 1
            try:
                data = _run_scheduler_once(client, goal=scenario["goal"], actors=actors)
            except Exception as exc:
                print(f"  run#{idx}: failed_to_call_scheduler -> {exc}")
                continue

            status = data.get("status")
            results = data.get("results", [])
            executed = [item.get("capability", "") for item in results]
            executed_set = set(executed)
            if status == "success":
                success_runs += 1

            news_steps = [item for item in results if item.get("capability") == "news.publish_article"]
            news_ok = any(step.get("status") == "success" for step in news_steps)
            if news_ok:
                news_success_runs += 1

            expected = scenario["expect"]
            expected_covered = expected.issubset(executed_set)
            if expected_covered:
                matched_expected_count += 1

            print(
                f"  run#{idx}: status={status} news_ok={news_ok} expected_covered={expected_covered} "
                f"executed={executed}"
            )

        print(f"scenario_result: matched_expected={matched_expected_count}/{iterations}")

    print("\n========================================")
    print("news_free_test_summary")
    print(f"total_runs={total_runs}")
    print(f"scheduler_success_runs={success_runs}")
    print(f"news_publish_success_runs={news_success_runs}")
    print("note=This is an empirical runtime test. It can indicate scheduling freedom/coverage, not prove absolute completeness.")


def main() -> None:
    args = parse_args()

    if args.spawn_probability is not None:
        clamped = max(0.0, min(1.0, args.spawn_probability))
        os.environ["SCHEDULER_NEW_ACTOR_PROBABILITY"] = str(clamped)

    from app.main import create_app

    app = create_app()
    client = TestClient(app)

    actors = [item.strip() for item in args.actors.split(",") if item.strip()]
    if args.news_free_test:
        _run_news_free_test(client, actors=actors, iterations=args.iterations)
        return

    if not args.goal.strip():
        raise SystemExit("--goal is required unless --news-free-test is enabled")

    data = _run_scheduler_once(client, goal=args.goal, actors=actors)
    _print_single_run(data)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(
            [
                "--news-free-test",
                "--iterations",
                "1",
                "--spawn-probability",
                "0.3",
            ]
        )
    main()
