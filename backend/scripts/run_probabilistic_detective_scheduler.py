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


@dataclass(slots=True)
class DetectiveDispatchProbabilities:
    detective_story: float
    new_detective_long_arc: float
    continue_detective_long_arc: float

    def normalize(self) -> "DetectiveDispatchProbabilities":
        total = self.detective_story + self.new_detective_long_arc + self.continue_detective_long_arc
        if total <= 0:
            return DetectiveDispatchProbabilities(0.45, 0.30, 0.25)
        return DetectiveDispatchProbabilities(
            self.detective_story / total,
            self.new_detective_long_arc / total,
            self.continue_detective_long_arc / total,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Dispatch mystery scheduler runs with probabilities across: "
            "regular detective story, new long detective arc, continue long detective arc."
        )
    )
    parser.add_argument("--actors", default="", help="Comma-separated actor ids, e.g. aria,milo")
    parser.add_argument("--cycles", type=int, default=1, help="How many dispatch cycles to run")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible dispatch")
    parser.add_argument("--detective-story-prob", type=float, default=0.45)
    parser.add_argument("--new-detective-long-arc-prob", type=float, default=0.30)
    parser.add_argument("--continue-detective-long-arc-prob", type=float, default=0.25)
    parser.add_argument(
        "--spawn-probability",
        type=float,
        default=None,
        help="Optional override for SCHEDULER_NEW_ACTOR_PROBABILITY (0.0 to 1.0).",
    )
    return parser.parse_args()


def _format_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _build_detective_goal(rng: random.Random) -> str:
    samples = [
        "Investigate a suspicious movement pattern around the old warehouse.",
        "Investigate mismatched dockside transfer records from last night.",
        "Investigate why witness statements conflict about corridor meetings.",
        "Investigate timeline gaps in transit logs near the reported sighting.",
        "Investigate unusual surveillance footage gaps near the back alley.",
        "Investigate missing security keys from the night guard's locker.",
        "Investigate tampered financial records in the company ledger.",
        "Investigate unexplained footprints outside the locked office door.",
        "Investigate conflicting alibis for the evening of the incident.",
        "Investigate sudden cargo disappearance from the storage bay.",
        "Investigate why the building alarm failed to trigger at midnight.",
        "Investigate inconsistent visitor log entries from the previous day.",
        "Investigate strange scratch marks on the warehouse back door.",
        "Investigate disrupted communication logs during the suspicious window.",
        "Investigate unaccounted-for vehicle movements near the crime scene.",
        "Investigate misplaced evidence bags from the initial inspection.",
        "Investigate why staff access logs show an unknown login.",
        "Investigate contradictory descriptions of the unknown suspect.",
        "Investigate damaged lock mechanisms on the storage unit.",
        "Investigate missing shipment documents from the dispatch office.",
        "Investigate unusual noise reports from the rooftop after hours.",
        "Investigate gaps in witness memory about the departure time.",
        "Investigate mismatched inventory counts in the stockroom.",
        "Investigate suspicious keycard swipes outside working hours.",
        "Investigate unidentified fingerprints on the abandoned safe.",
        "Investigate faint blood traces not matching the victim's profile.",
        "Investigate why the perimeter camera stopped recording abruptly.",
        "Investigate hidden compartments in the suspect's personal bag.",
        "Investigate delayed emergency calls from the affected location.",
        "Investigate forged signatures on the confidential contract papers.",
        "Investigate unusual tire tracks near the isolated crime scene.",
        "Investigate deleted chat logs from the suspect's mobile device.",
        "Investigate unexplained power outages during the incident window.",
        "Investigate misplaced personal items in the victim's residence.",
        "Investigate suspicious third-party access to the private server.",
        "Investigate contradictory travel receipts from the key witness.",
        "Investigate broken window locks with signs of forced entry.",
        "Investigate unregistered numbers making repeated anonymous calls.",
        "Investigate missing pages from the official case file folder.",
        "Investigate chemical residues on the exterior of the trash bin.",
        "Investigate why guard patrols deviated from the standard route.",
        "Investigate hidden audio recordings found near the meeting room.",
        "Investigate mismatched weight records in the freight documents.",
        "Investigate sudden memory loss in the only eyewitness account.",
        "Investigate tampered seals on the evidence storage container.",
        "Investigate unknown footprints leading to the rooftop exit door.",
        "Investigate disrupted GPS signals during the critical time frame.",
        "Investigate fake identification used at the front desk check-in.",
        "Investigate unexplained burns on the warehouse wooden floor.",
        "Investigate conflicting shift records of the night security team.",
        "Investigate encrypted files left on the office desktop computer.",
        "Investigate misplaced tools used for lock picking and entry.",
        "Investigate why emergency exits were unlocked outside business hours.",
        "Investigate unidentified odors reported near the storage basement."
    ]
    return rng.choice(samples)


def _build_new_detective_arc_goal(rng: random.Random) -> str:
    samples = [
        "Long-case: recurring warehouse lights after curfew",
        "Long-case: repeated unsigned transfer entries at the docks",
        "Long-case: missing surveillance intervals around station exits",
        "Long-case: witness accounts diverge on corridor rendezvous",
        "Long-case: persistent unauthorised keycard swipes at storage wings",
        "Long-case: repeated unidentified footprints near the back loading bay",
        "Long-case: ongoing gaps in night-shift security patrol logs",
        "Long-case: recurring false alarm triggers at the perimeter fence",
        "Long-case: repeated missing pages from weekly cargo manifests",
        "Long-case: persistent conflicting alibis for late-night staff",
        "Long-case: recurring unknown vehicle loitering near the warehouse",
        "Long-case: ongoing tampering with storage unit lock seals",
        "Long-case: repeated disruptions to rooftop communication signals",
        "Long-case: persistent anonymous calls to the security desk",
        "Long-case: recurring mismatches in monthly inventory counts",
        "Long-case: ongoing missing segments of dock CCTV footage",
        "Long-case: repeated unusual noises from the basement after hours",
        "Long-case: persistent unregistered access to office servers",
        "Long-case: recurring faded witness memories of night incidents",
        "Long-case: ongoing damaged locks on secondary warehouse doors",
        "Long-case: repeated unsigned notes left at the security booth",
        "Long-case: persistent power fluctuations in restricted areas",
        "Long-case: recurring discrepancies in fuel usage records",
        "Long-case: ongoing abandoned packages near station entrances",
        "Long-case: repeated unexplained lock malfunctions on secure storage doors",
        "Long-case: persistent unauthorised access attempts to confidential files",
        "Long-case: recurring cargo hold disturbances with no forced entry",
        "Long-case: ongoing discrepancies in night guard attendance records",
        "Long-case: repeated vanishing of small high-value items from stockrooms",
        "Long-case: persistent unknown radio signals interfering with security comms",
        "Long-case: recurring late-night shadows spotted near restricted zones",
        "Long-case: ongoing tampering with monthly shipment inspection reports",
        "Long-case: repeated failure of perimeter motion sensors after midnight",
        "Long-case: persistent abandoned tools near the warehouse back entrance",
        "Long-case: recurring mismatches between delivery notes and actual cargo",
        "Long-case: ongoing witness reluctance to discuss late-night dock activity",
        "Long-case: repeated discoloration marks on warehouse interior walls",
        "Long-case: persistent gaps in electronic key usage history logs",
        "Long-case: recurring unexplained odours in the underground storage level",
        "Long-case: ongoing repeated re-routing of delivery vehicles without reason",
        "Long-case: persistent damage to external security camera housings",
        "Long-case: recurring missing entries in staff overnight check-in logs",
        "Long-case: ongoing strange liquid residues found near loading bays",
        "Long-case: repeated false alerts from fire and safety systems",
        "Long-case: persistent unknown footprints inside locked storage areas",
        "Long-case: recurring delays in official incident report filings",
        "Long-case: ongoing unauthorised opening of emergency exit doors",
        "Long-case: repeated mismatched time stamps on security recordings",
        "Long-case: persistent signs of disturbance in unused office rooms"
    ]
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"detective: {rng.choice(samples)} [{suffix}]"


def _pick_action(
    *,
    rng: random.Random,
    probs: DetectiveDispatchProbabilities,
    has_open_detective_arcs: bool,
) -> str:
    normalized = probs.normalize()
    thresholds = [
        ("detective_story", normalized.detective_story),
        ("new_detective_long_arc", normalized.new_detective_long_arc),
        ("continue_detective_long_arc", normalized.continue_detective_long_arc),
    ]
    roll = rng.random()
    cursor = 0.0
    selected = "detective_story"
    for name, weight in thresholds:
        cursor += weight
        if roll <= cursor:
            selected = name
            break

    if selected == "continue_detective_long_arc" and not has_open_detective_arcs:
        return "new_detective_long_arc"
    return selected


def _run_scheduler(client: TestClient, *, endpoint: str, goal: str, actors: list[str]) -> dict:
    payload = {"goal": goal, "actors": actors}
    response = client.post(endpoint, json=payload)
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
    probs = DetectiveDispatchProbabilities(
        detective_story=max(0.0, args.detective_story_prob),
        new_detective_long_arc=max(0.0, args.new_detective_long_arc_prob),
        continue_detective_long_arc=max(0.0, args.continue_detective_long_arc_prob),
    )

    cycles = max(1, args.cycles)
    action_counts: dict[str, int] = {
        "detective_story": 0,
        "new_detective_long_arc": 0,
        "continue_detective_long_arc": 0,
    }
    success_cycles = 0
    failed_cycles = 0
    capability_counts: dict[str, int] = {}

    initial_open_detective_arcs = [arc for arc in story_arc_service.list_open_arcs(limit=1000) if arc.goal_key.startswith("detective:")]

    print("Probabilistic detective dispatcher started.")
    print(f"cycles={cycles}")
    print("probabilities(normalized)=")
    print(_format_json(asdict(probs.normalize())))

    for cycle in range(1, cycles + 1):
        open_detective_arcs = [
            arc for arc in story_arc_service.list_open_arcs(limit=1000) if arc.goal_key.startswith("detective:")
        ]
        action = _pick_action(
            rng=rng,
            probs=probs,
            has_open_detective_arcs=bool(open_detective_arcs),
        )
        action_counts[action] = action_counts.get(action, 0) + 1

        if action == "detective_story":
            endpoint = "/api/v1/ai/scheduler/run"
            goal = _build_detective_goal(rng)
            selected_arc_id = ""
        elif action == "new_detective_long_arc":
            endpoint = "/api/v1/ai/scheduler/run-detective-arc"
            goal = _build_new_detective_arc_goal(rng)
            selected_arc_id = ""
        else:
            endpoint = "/api/v1/ai/scheduler/run-detective-arc"
            arc = rng.choice(open_detective_arcs)
            goal = arc.goal_key
            selected_arc_id = arc.arc_id

        print("\n----------------------------------------")
        print(f"cycle={cycle}")
        print(f"dispatch_action={action}")
        print(f"endpoint={endpoint}")
        print(f"selected_arc_id={selected_arc_id}")
        print(f"goal={goal}")

        try:
            report = _run_scheduler(client, endpoint=endpoint, goal=goal, actors=actors)
        except Exception as exc:
            failed_cycles += 1
            print(f"cycle_result=failed error={exc}")
            continue

        success_cycles += 1
        executed_caps = [item.get("capability", "") for item in report.get("results", [])]
        for cap in executed_caps:
            if cap:
                capability_counts[cap] = capability_counts.get(cap, 0) + 1

        print(f"story_id={report.get('story_id')}")
        print(f"status={report.get('status')}")
        print(f"planner={report.get('planner_name')}")
        print(f"steps_executed={len(executed_caps)}")
        print(f"capabilities={executed_caps}")

    final_open_detective_arcs = [arc for arc in story_arc_service.list_open_arcs(limit=1000) if arc.goal_key.startswith("detective:")]
    sorted_caps = sorted(capability_counts.items(), key=lambda item: (-item[1], item[0]))

    print("\n========================================")
    print("detective_dispatch_summary")
    print(f"cycles_total={cycles}")
    print(f"cycles_success={success_cycles}")
    print(f"cycles_failed={failed_cycles}")
    print("action_counts=")
    print(_format_json(action_counts))
    print(f"open_detective_arcs_start={len(initial_open_detective_arcs)}")
    print(f"open_detective_arcs_end={len(final_open_detective_arcs)}")
    print(f"open_detective_arcs_delta={len(final_open_detective_arcs) - len(initial_open_detective_arcs)}")
    print("capability_execution_counts=")
    print(_format_json({key: value for key, value in sorted_caps}))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["--cycles", "3", "--actors", "aria"])
    main()
