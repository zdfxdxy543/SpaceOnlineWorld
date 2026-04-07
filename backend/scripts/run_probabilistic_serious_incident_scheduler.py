from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient


SERIOUS_INCIDENT_GOAL_PREFIX = "detective: severe-incident:"


@dataclass(slots=True)
class SeriousIncidentDispatchProbabilities:
    new_serious_long_arc: float
    continue_serious_long_arc: float

    def normalize(self) -> "SeriousIncidentDispatchProbabilities":
        total = self.new_serious_long_arc + self.continue_serious_long_arc
        if total <= 0:
            return SeriousIncidentDispatchProbabilities(0.62, 0.38)
        return SeriousIncidentDispatchProbabilities(
            self.new_serious_long_arc / total,
            self.continue_serious_long_arc / total,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Dispatch only serious-incident detective long arcs with probabilities across: "
            "new long arc, continue long arc."
        )
    )
    parser.add_argument("--actors", default="", help="Comma-separated actor ids, e.g. aria,milo")
    parser.add_argument("--cycles", type=int, default=1, help="How many dispatch cycles to run")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible dispatch")
    parser.add_argument(
        "--new-serious-long-arc-prob",
        type=float,
        default=0.62,
        help="Probability of starting a new serious-incident long arc",
    )
    parser.add_argument(
        "--continue-serious-long-arc-prob",
        type=float,
        default=0.38,
        help="Probability of continuing an existing serious-incident long arc",
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


def _build_new_serious_arc_goal(rng: random.Random) -> str:
    samples = [
        "possible sabotage around the power relay near the freight yard",
        "missing courier tied to forged transfer orders at the old exchange",
        "coordinated warehouse fire with inconsistent maintenance records",
        "repeated contamination alerts linked to tampered storage logs",
        "pattern of extortion threats targeting small logistics operators",
        "serial equipment failure that may conceal deliberate interference",
    ]
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{SERIOUS_INCIDENT_GOAL_PREFIX} {rng.choice(samples)} [{suffix}]"


def _pick_action(
    *,
    rng: random.Random,
    probs: SeriousIncidentDispatchProbabilities,
    has_open_arcs: bool,
) -> str:
    normalized = probs.normalize()
    thresholds = [
        ("new_serious_long_arc", normalized.new_serious_long_arc),
        ("continue_serious_long_arc", normalized.continue_serious_long_arc),
    ]
    roll = rng.random()
    cursor = 0.0
    selected = "new_serious_long_arc"
    for name, weight in thresholds:
        cursor += weight
        if roll <= cursor:
            selected = name
            break

    if selected == "continue_serious_long_arc" and not has_open_arcs:
        return "new_serious_long_arc"
    return selected


def _list_open_serious_arcs(story_arc_service) -> list:
    return [
        arc
        for arc in story_arc_service.list_open_arcs(limit=1000)
        if arc.goal_key.startswith(SERIOUS_INCIDENT_GOAL_PREFIX)
    ]


def _pick_existing_arc(rng: random.Random, story_arc_service, open_arcs: list):
    resolution_arcs = [arc for arc in open_arcs if story_arc_service.determine_phase(arc) == "resolution"]
    if resolution_arcs:
        return rng.choice(resolution_arcs)

    investigation_arcs = [arc for arc in open_arcs if story_arc_service.determine_phase(arc) == "investigation"]
    if investigation_arcs:
        return rng.choice(investigation_arcs)

    return rng.choice(open_arcs)


def _run_scheduler(client: TestClient, *, goal: str, actors: list[str]) -> dict:
    payload = {"goal": goal, "actors": actors}
    response = client.post("/api/v1/ai/scheduler/run-detective-arc", json=payload)
    if response.status_code >= 400:
        raise RuntimeError(f"Scheduler call failed: HTTP {response.status_code} {response.text}")
    return response.json()


def main() -> None:
    args = parse_args()

    if args.spawn_probability is not None:
        clamped = max(0.0, min(1.0, args.spawn_probability))
        os.environ["SCHEDULER_NEW_ACTOR_PROBABILITY"] = str(clamped)

    rng = random.Random(args.seed)
    from app.main import create_app

    app = create_app()
    client = TestClient(app)
    story_arc_service = app.state.container.story_arc_service

    actors = [item.strip() for item in args.actors.split(",") if item.strip()]
    probs = SeriousIncidentDispatchProbabilities(
        new_serious_long_arc=max(0.0, args.new_serious_long_arc_prob),
        continue_serious_long_arc=max(0.0, args.continue_serious_long_arc_prob),
    )

    cycles = max(1, args.cycles)
    action_counts: dict[str, int] = {
        "new_serious_long_arc": 0,
        "continue_serious_long_arc": 0,
    }
    success_cycles = 0
    failed_cycles = 0
    capability_counts: dict[str, int] = {}
    news_cycles = 0

    start_open_arc_count = len(_list_open_serious_arcs(story_arc_service))

    print("Probabilistic serious-incident detective dispatcher started.")
    print(f"cycles={cycles}")
    print(f"goal_prefix={SERIOUS_INCIDENT_GOAL_PREFIX}")
    print("probabilities(normalized)=")
    print(_format_json(asdict(probs.normalize())))

    for cycle in range(1, cycles + 1):
        open_arcs = _list_open_serious_arcs(story_arc_service)
        action = _pick_action(
            rng=rng,
            probs=probs,
            has_open_arcs=bool(open_arcs),
        )
        action_counts[action] = action_counts.get(action, 0) + 1

        if action == "new_serious_long_arc":
            goal = _build_new_serious_arc_goal(rng)
            selected_arc_id = ""
            selected_arc_phase = "discovery"
        else:
            arc = _pick_existing_arc(rng, story_arc_service, open_arcs)
            goal = arc.goal_key
            selected_arc_id = arc.arc_id
            selected_arc_phase = story_arc_service.determine_phase(arc)

        print("\n----------------------------------------")
        print(f"cycle={cycle}")
        print(f"dispatch_action={action}")
        print("endpoint=/api/v1/ai/scheduler/run-detective-arc")
        print(f"selected_arc_id={selected_arc_id}")
        print(f"selected_arc_phase={selected_arc_phase}")
        print(f"goal={goal}")

        try:
            report = _run_scheduler(client, goal=goal, actors=actors)
        except Exception as exc:
            failed_cycles += 1
            print(f"cycle_result=failed error={exc}")
            continue

        success_cycles += 1
        executed_caps = [item.get("capability", "") for item in report.get("results", [])]
        if any(cap == "news.publish_article" for cap in executed_caps):
            news_cycles += 1

        for cap in executed_caps:
            if cap:
                capability_counts[cap] = capability_counts.get(cap, 0) + 1

        print(f"story_id={report.get('story_id')}")
        print(f"status={report.get('status')}")
        print(f"planner={report.get('planner_name')}")
        print(f"steps_executed={len(executed_caps)}")
        print(f"capabilities={executed_caps}")

    end_open_arc_count = len(_list_open_serious_arcs(story_arc_service))
    sorted_caps = sorted(capability_counts.items(), key=lambda item: (-item[1], item[0]))

    print("\n========================================")
    print("serious_incident_dispatch_summary")
    print(f"cycles_total={cycles}")
    print(f"cycles_success={success_cycles}")
    print(f"cycles_failed={failed_cycles}")
    print(f"cycles_with_news={news_cycles}")
    print("action_counts=")
    print(_format_json(action_counts))
    print(f"open_serious_arcs_start={start_open_arc_count}")
    print(f"open_serious_arcs_end={end_open_arc_count}")
    print(f"open_serious_arcs_delta={end_open_arc_count - start_open_arc_count}")
    print("capability_execution_counts=")
    print(_format_json({key: value for key, value in sorted_caps}))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["--cycles", "3", "--actors", "aria"])
    main()