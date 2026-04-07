from __future__ import annotations

import argparse
import json
import os
import random
import sys
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient


@dataclass(slots=True)
class DispatchProbabilities:
    new_story: float
    new_long_arc: float
    continue_long_arc: float

    def normalize(self) -> "DispatchProbabilities":
        total = self.new_story + self.new_long_arc + self.continue_long_arc
        if total <= 0:
            return DispatchProbabilities(0.5, 0.3, 0.2)
        return DispatchProbabilities(
            self.new_story / total,
            self.new_long_arc / total,
            self.continue_long_arc / total,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Dispatch scheduler runs with probabilities across: new story line, "
            "new long arc, continue long arc."
        )
    )
    parser.add_argument("--actors", default="", help="Comma-separated actor ids, e.g. aria,milo")
    parser.add_argument("--cycles", type=int, default=1, help="How many dispatch cycles to run")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible dispatch")
    parser.add_argument("--new-story-prob", type=float, default=0.55, help="Probability of starting a new short story")
    parser.add_argument("--new-long-arc-prob", type=float, default=0.25, help="Probability of starting a new long arc")
    parser.add_argument(
        "--continue-long-arc-prob",
        type=float,
        default=0.20,
        help="Probability of continuing an existing long arc",
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


def _build_short_story_goal(rng: random.Random) -> str:
    samples = [
        "A normal day in town with small interpersonal misunderstandings and resolution.",
        "A busy market morning where neighbors share practical tips and updates.",
        "A community notice about transport timing changes and daily life adjustments.",
        "An evening neighborhood discussion about shared resources and routines.",
        "A quiet park afternoon where elders exchange life stories and small advice.",
        "A local bakery morning with regulars sharing greetings and daily news.",
        "A community cleanup event where residents work together to tidy public spaces.",
        "A school pickup moment with parents chatting about kids and family routines.",
        "A weekly library gathering where locals swap books and reading recommendations.",
        "A street maintenance notice informing residents of temporary route changes.",
        "A sunny balcony chat between neighbors about gardening and plant care tips.",
        "A cozy café evening where friends discuss casual daily matters and plans.",
        "A neighborhood pet walk where owners exchange animal care advice and stories.",
        "A community garden check-in where residents share harvests and growing skills.",
        "A rainy town day with locals helping each other carry bags and belongings.",
        "A corner shop chat where customers and owners discuss gentle town news.",
        "A weekend block meeting where neighbors plan small community activities.",
        "A waste collection reminder for residents to follow sorting rules and times.",
        "A calm street evening with neighbors greeting each other on the way home.",
        "A town hall brief about minor public facility updates and usage guidance.",
        "A morning bus stop chat with commuters sharing travel and work snippets.",
        "A shared laundry space talk where residents exchange household tips.",
        "A post office line moment where people chat about local events and weather.",
        "A community notice about public park maintenance and temporary closure.",
        "A lunchtime neighborhood chat about cooking recipes and family meals.",
        "A local library story hour for kids with parents chatting nearby.",
        "A town square afternoon where residents relax and share light conversations.",
        "A notice about water supply maintenance and temporary usage adjustments.",
        "A evening front-porch chat between neighbors about daily life and weather.",
        "A farmers’ market visit where vendors and buyers share fresh produce tips.",
        "A community bike ride event where locals enjoy casual conversation together.",
        "A school notice about parent-teacher meeting time and simple preparations.",
        "A laundromat afternoon where strangers exchange small friendly talks.",
        "A neighborhood watch update about safety tips and local reminders.",
        "A sunny street moment where neighbors help fix a broken bicycle together.",
        "A community notice about garbage collection schedule changes for holidays.",
        "A evening grocery run where shoppers chat about meal plans and store deals.",
        "A local park picnic with families sharing snacks and casual conversations.",
        "A town notice about street lighting repairs and nighttime safety reminders.",
        "A morning dog park visit where pet owners bond over animal stories and care.",
        "A neighborhood book club meeting where members discuss stories and opinions.",
        "A community notice about public garden planting day and volunteer calls.",
        "A rainy café stay where people share umbrellas and kind small gestures.",
        "A local hardware store chat where shoppers ask for and receive repair tips.",
        "A evening street workout where residents exercise and encourage each other.",
        "A town notice about public toilet maintenance and temporary service changes.",
        "A weekend yard sale where neighbors swap items and share life anecdotes.",
        "A school playground afternoon with kids playing and parents chatting calmly.",
        "A community notice about bus route adjustments and alternative transport tips.",
        "A late-afternoon park chat where friends discuss hobbies and weekend plans.",
        "A local pharmacy wait where people exchange health tips and gentle concerns.",
        "A neighborhood tool-sharing moment where residents borrow and lend equipment.",
        "A town notice about community garden watering rules and shared schedules.",
        "A morning bakery line where customers recommend pastries and share tastes.",
        "A evening balcony gathering where neighbors watch the sunset and chat lightly.",
        "A community notice about public bench repairs and park usage reminders.",
        "A casual street encounter where old friends catch up on recent life updates.",
        "A local library help session where volunteers assist with tech and reading.",
        "A neighborhood notice about noise guidelines for peaceful daily living.",
        "A weekend hiking trip with townsfolk sharing paths and nature observations.",
        "A town notice about parking changes near the market and shopping areas.",
        "A afternoon kitchen chat between neighbors about home cleaning and organizing.",
        "A community potluck plan where residents discuss dishes and gathering time.",
        "A morning newsstand visit where people talk about local and light headlines.",
        "A neighborhood notice about plant watering rosters for shared green spaces.",
        "A evening walk around the block where neighbors wave and exchange brief chats.",
        "A local tailor shop moment where customers talk about clothes and daily needs.",
        "A town notice about public water fountain repairs and hydration reminders.",
        "A weekend craft session where locals share DIY skills and creative ideas.",
        "A neighborhood chat about seasonal weather and home preparation tips.",
        "A community notice about lost and found items at the local park.",
        "A afternoon tea break between neighbors sharing snacks and small stories.",
        "A town notice about sidewalk repairs and pedestrian safety guidance.",
        "A morning farm visit where townsfolk learn about fresh food and farming.",
        "A evening community chat about minor local issues and friendly solutions.",
        "A neighborhood notice about package delivery tips for secure receipt.",
        "A sunny garden work where residents plant flowers and talk together calmly.",
        "A local fish market morning where buyers and sellers share cooking advice."
    ]
    return rng.choice(samples)


def _build_new_arc_goal(rng: random.Random) -> str:
    samples = [
        "Ongoing issue: repeated inventory mismatch in the canteen supply room",
        "Ongoing issue: unexplained schedule drift in the neighborhood shuttle",
        "Ongoing issue: recurring noise pattern near the community center",
        "Ongoing issue: missing maintenance logs in the transit depot",
        "Ongoing issue: persistent supply shortages in the community pantry",
        "Ongoing issue: recurring late departures of the neighborhood shuttle bus",
        "Ongoing issue: unexplained power flickers near the community center",
        "Ongoing issue: incomplete inspection records in the transit depot",
        "Ongoing issue: repeated misplacement of canteen kitchen utensils",
        "Ongoing issue: unplanned route changes in the neighborhood shuttle",
        "Ongoing issue: recurring litter accumulation near the community center",
        "Ongoing issue: missing repair reports in the transit depot workshop",
        "Ongoing issue: persistent temperature irregularities in the canteen storage",
        "Ongoing issue: unexplained passenger count discrepancies on the shuttle",
        "Ongoing issue: recurring light malfunctions outside the community center",
        "Ongoing issue: incomplete vehicle check logs in the transit depot",
        "Ongoing issue: repeated expiration of unmarked canteen supplies",
        "Ongoing issue: recurring shuttle delays during morning peak hours",
        "Ongoing issue: unexplained door malfunctions at the community center",
        "Ongoing issue: missing fuel usage records in the transit depot",
        "Ongoing issue: persistent untracked item withdrawals from the canteen",
        "Ongoing issue: unannounced shuttle cancellations on weekday evenings",
        "Ongoing issue: recurring water leakage near the community center restroom",
        "Ongoing issue: incomplete driver shift logs in the transit depot",
        "Ongoing issue: repeated packaging damage to canteen dry goods",
        "Ongoing issue: unexplained shuttle overcrowding on fixed routes",
        "Ongoing issue: recurring equipment tampering at the community center",
        "Ongoing issue: missing part replacement records in the transit depot",
        "Ongoing issue: persistent inconsistent portion counts in the canteen",
        "Ongoing issue: recurring shuttle stop skipping without notice",
        "Ongoing issue: unexplained furniture damage near the community center",
        "Ongoing issue: incomplete safety inspection forms in the transit depot",
        "Ongoing issue: repeated unlabeled food containers in the canteen",
        "Ongoing issue: unexplained shuttle engine troubles on repeated trips",
        "Ongoing issue: recurring blocked pathways around the community center",
        "Ongoing issue: missing cleaning service logs in the transit depot",
        "Ongoing issue: persistent stock discrepancies in canteen disposable goods",
        "Ongoing issue: recurring shuttle timetable conflicts with events",
        "Ongoing issue: unexplained odd odors near the community center basement",
        "Ongoing issue: incomplete tire check records in the transit depot",
        "Ongoing issue: repeated misplaced cleaning supplies in the canteen",
        "Ongoing issue: unexplained shuttle communication radio static",
        "Ongoing issue: recurring broken fixtures at the community center",
        "Ongoing issue: missing emergency drill records in the transit depot",
        "Ongoing issue: persistent overordering of unused canteen ingredients",
        "Ongoing issue: recurring shuttle key misplacement by drivers",
        "Ongoing issue: unexplained quiet hours violations near the community center",
        "Ongoing issue: incomplete waste disposal logs in the transit depot",
        "Ongoing issue: repeated understocking of essential canteen items",
        "Ongoing issue: unexplained shuttle route deviation during trips",
        "Ongoing issue: recurring lost items at the community center lost-and-found",
        "Ongoing issue: missing tool inventory logs in the transit depot garage",
        "Ongoing issue: persistent cross-contamination risks in canteen storage",
        "Ongoing issue: recurring shuttle seat damage on repeated use",
        "Ongoing issue: unexplained blocked drainage near the community center",
        "Ongoing issue: incomplete maintenance schedule logs in the transit depot",
        "Ongoing issue: repeated unrecorded canteen supply donations",
        "Ongoing issue: unexplained shuttle AC failures in hot weather",
        "Ongoing issue: recurring overgrown vegetation around the community center",
        "Ongoing issue: missing battery replacement records in the transit depot",
        "Ongoing issue: persistent mislabeled storage bins in the canteen",
        "Ongoing issue: recurring shuttle boarding confusion for elderly riders",
        "Ongoing issue: unexplained broken windows at the community center",
        "Ongoing issue: incomplete route performance logs in the transit depot",
        "Ongoing issue: repeated expired condiments in the canteen service area",
        "Ongoing issue: unexplained shuttle headlight malfunctions at night",
        "Ongoing issue: recurring missing signage at the community center",
        "Ongoing issue: missing oil change records in the transit depot vehicles",
        "Ongoing issue: persistent disorganized shelf layout in the canteen",
        "Ongoing issue: recurring shuttle timetable misprinting and errors",
        "Ongoing issue: unexplained power outlet failures at the community center",
        "Ongoing issue: incomplete passenger feedback logs in the transit depot",
        "Ongoing issue: repeated misplaced cooking equipment in the canteen",
        "Ongoing issue: unexplained shuttle Wi-Fi outages during rides",
        "Ongoing issue: recurring blocked vents near the community center hall",
        "Ongoing issue: missing equipment calibration logs in the transit depot"
    ]
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{rng.choice(samples)} [{suffix}]"


def _pick_dispatch_action(
    *,
    rng: random.Random,
    probs: DispatchProbabilities,
    has_open_arcs: bool,
) -> str:
    normalized = probs.normalize()
    thresholds = [
        ("new_story", normalized.new_story),
        ("new_long_arc", normalized.new_long_arc),
        ("continue_long_arc", normalized.continue_long_arc),
    ]
    roll = rng.random()
    cursor = 0.0
    selected = "new_story"
    for name, weight in thresholds:
        cursor += weight
        if roll <= cursor:
            selected = name
            break

    # If asked to continue but no open arcs exist, fallback to creating a new long arc.
    if selected == "continue_long_arc" and not has_open_arcs:
        return "new_long_arc"
    return selected


def _run_scheduler(client: TestClient, *, endpoint: str, goal: str, actors: list[str]) -> dict:
    payload = {"goal": goal, "actors": actors}
    response = client.post(endpoint, json=payload)
    if response.status_code >= 400:
        raise RuntimeError(f"Scheduler call failed: HTTP {response.status_code} {response.text}")
    return response.json()


def _contains_llm_failure_marker(text: str) -> bool:
    value = text.lower()
    markers = (
        "llm",
        "siliconflow",
        "planner",
        "content_generation_failed",
        "llm_planner_failed",
        "timeout",
    )
    return any(marker in value for marker in markers)


def _extract_failure_reason(report: dict) -> tuple[str, bool]:
    results = report.get("results", [])
    if not isinstance(results, list):
        return "Unknown scheduler failure", False

    for item in reversed(results):
        if not isinstance(item, dict):
            continue
        if str(item.get("status", "")).lower() != "failed":
            continue

        capability = str(item.get("capability", "unknown"))
        error_code = str(item.get("error_code", "unknown"))
        error_message = str(item.get("error_message", "")).strip() or "No error message"
        reason = f"capability={capability}, error_code={error_code}, error_message={error_message}"
        is_llm_related = _contains_llm_failure_marker(
            f"{capability} {error_code} {error_message}"
        )
        return reason, is_llm_related

    return "Scheduler status is failed but no failed action result found", False


def _show_error_popup(title: str, message: str) -> None:
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        pass


def _notify_failure(*, title: str, reason: str, show_popup: bool) -> None:
    print(f"{title}: {reason}")
    if show_popup:
        _show_error_popup(title, reason)


def main() -> None:
    args = parse_args()
    popup_on_llm_failure = os.getenv("SCHEDULER_POPUP_ON_LLM_FAILURE", "true").lower() == "true"

    if args.spawn_probability is not None:
        clamped = max(0.0, min(1.0, args.spawn_probability))
        os.environ["SCHEDULER_NEW_ACTOR_PROBABILITY"] = str(clamped)

    rng = random.Random(args.seed)
    from app.main import create_app

    app = create_app()
    client = TestClient(app)
    story_arc_service = app.state.container.story_arc_service

    actors = [item.strip() for item in args.actors.split(",") if item.strip()]
    probs = DispatchProbabilities(
        new_story=max(0.0, args.new_story_prob),
        new_long_arc=max(0.0, args.new_long_arc_prob),
        continue_long_arc=max(0.0, args.continue_long_arc_prob),
    )

    cycles = max(1, args.cycles)
    action_counts: dict[str, int] = {
        "new_story": 0,
        "new_long_arc": 0,
        "continue_long_arc": 0,
    }
    success_cycles = 0
    failed_cycles = 0
    capability_counts: dict[str, int] = {}
    start_open_arc_count = len(story_arc_service.list_open_arcs(limit=1000))

    print("Probabilistic scheduler dispatcher started.")
    print(f"cycles={cycles}")
    print(
        "probabilities(normalized)="
        f"{_format_json(asdict(probs.normalize()))}"
    )

    for cycle in range(1, cycles + 1):
        open_arcs = story_arc_service.list_open_arcs(limit=100)
        action = _pick_dispatch_action(
            rng=rng,
            probs=probs,
            has_open_arcs=bool(open_arcs),
        )

        if action == "new_story":
            endpoint = "/api/v1/ai/scheduler/run-life"
            goal = _build_short_story_goal(rng)
            selected_arc_id = ""
        elif action == "new_long_arc":
            endpoint = "/api/v1/ai/scheduler/run-life-arc"
            goal = _build_new_arc_goal(rng)
            selected_arc_id = ""
        else:
            endpoint = "/api/v1/ai/scheduler/run-life-arc"
            arc = rng.choice(open_arcs)
            goal = arc.goal_key
            selected_arc_id = arc.arc_id

        print("\n----------------------------------------")
        print(f"cycle={cycle}")
        print(f"dispatch_action={action}")
        print(f"endpoint={endpoint}")
        print(f"selected_arc_id={selected_arc_id}")
        print(f"goal={goal}")
        action_counts[action] = action_counts.get(action, 0) + 1

        try:
            report = _run_scheduler(client, endpoint=endpoint, goal=goal, actors=actors)
        except Exception as exc:
            traceback.print_exc()
            reason = str(exc).strip() or repr(exc)
            if _contains_llm_failure_marker(reason):
                _notify_failure(
                    title="LLM Scheduler Failure",
                    reason=reason,
                    show_popup=popup_on_llm_failure,
                )
            print(f"cycle_result=failed error={exc}")
            failed_cycles += 1
            continue

        if str(report.get("status", "")).lower() == "failed":
            reason, is_llm_related = _extract_failure_reason(report)
            if is_llm_related:
                _notify_failure(
                    title="LLM Scheduler Failure",
                    reason=reason,
                    show_popup=popup_on_llm_failure,
                )
            print(f"cycle_result=failed reason={reason}")
            failed_cycles += 1
            continue

        success_cycles += 1
        executed_caps = [item.get("capability", "") for item in report.get("results", [])]
        for cap in executed_caps:
            if not cap:
                continue
            capability_counts[cap] = capability_counts.get(cap, 0) + 1

        print(f"story_id={report.get('story_id')}")
        print(f"status={report.get('status')}")
        print(f"planner={report.get('planner_name')}")
        print(f"steps_executed={len(executed_caps)}")
        print(f"capabilities={executed_caps}")

    end_open_arc_count = len(story_arc_service.list_open_arcs(limit=1000))
    sorted_caps = sorted(capability_counts.items(), key=lambda item: (-item[1], item[0]))

    print("\n========================================")
    print("dispatch_summary")
    print(f"cycles_total={cycles}")
    print(f"cycles_success={success_cycles}")
    print(f"cycles_failed={failed_cycles}")
    print("action_counts=")
    print(_format_json(action_counts))
    print(f"open_arcs_start={start_open_arc_count}")
    print(f"open_arcs_end={end_open_arc_count}")
    print(f"open_arcs_delta={end_open_arc_count - start_open_arc_count}")
    print("capability_execution_counts=")
    print(_format_json({key: value for key, value in sorted_caps}))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["--cycles", "3", "--actors", "aria"])
    main()
