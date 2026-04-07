from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import count

from app.infrastructure.db.session import DatabaseSessionManager


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_goal(goal: str) -> str:
    normalized = re.sub(r"\s+", " ", goal.strip().lower())
    return normalized[:300] or "daily-ongoing-event"


@dataclass(slots=True)
class StoryArcRecord:
    arc_id: str
    goal_key: str
    status: str
    created_at: str
    updated_at: str
    reveal_after: str
    clue_thread_id: str
    resolution_thread_id: str
    resolution_news_id: str
    related_share_id: str
    progression_count: int


class StoryArcService:
    def __init__(self, session_manager: DatabaseSessionManager) -> None:
        self.session_manager = session_manager
        self._arc_counter = count(1)

    def initialize(self) -> None:
        with self.session_manager.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS story_arcs (
                    arc_id TEXT PRIMARY KEY,
                    goal_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    reveal_after TEXT NOT NULL,
                    clue_thread_id TEXT NOT NULL,
                    resolution_thread_id TEXT NOT NULL,
                    resolution_news_id TEXT NOT NULL,
                    related_share_id TEXT NOT NULL,
                    progression_count INTEGER NOT NULL
                )
                """
            )
            row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(arc_id, 5) AS INTEGER)), 0) AS max_id FROM story_arcs WHERE arc_id LIKE 'arc-%'"
            ).fetchone()
            self._arc_counter = count(int(row["max_id"]) + 1)
            conn.commit()

    def get_or_create_open_arc(self, *, goal: str, reveal_after_hours: float) -> StoryArcRecord:
        goal_key = _normalize_goal(goal)
        arc = self._get_open_arc(goal_key=goal_key)
        if arc is not None:
            return arc

        now = datetime.now(timezone.utc)
        reveal_after = (now + timedelta(hours=max(0.0, reveal_after_hours))).isoformat()
        arc_id = f"arc-{next(self._arc_counter):04d}"
        now_iso = now.isoformat()
        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO story_arcs (
                    arc_id,
                    goal_key,
                    status,
                    created_at,
                    updated_at,
                    reveal_after,
                    clue_thread_id,
                    resolution_thread_id,
                    resolution_news_id,
                    related_share_id,
                    progression_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    arc_id,
                    goal_key,
                    "open",
                    now_iso,
                    now_iso,
                    reveal_after,
                    "",
                    "",
                    "",
                    "",
                    0,
                ),
            )
            conn.commit()

        created = self.get_arc(arc_id=arc_id)
        if created is None:
            raise RuntimeError("Failed to create story arc")
        return created

    def get_arc(self, *, arc_id: str) -> StoryArcRecord | None:
        with self.session_manager.connect() as conn:
            row = conn.execute("SELECT * FROM story_arcs WHERE arc_id = ?", (arc_id,)).fetchone()
        if row is None:
            return None
        return self._map_row(row)

    def list_open_arcs(self, *, limit: int = 50) -> list[StoryArcRecord]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM story_arcs
                WHERE status != 'resolved'
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [self._map_row(row) for row in rows]

    def determine_phase(self, arc: StoryArcRecord) -> str:
        if arc.status == "resolved":
            return "resolved"
        reveal_after = datetime.fromisoformat(arc.reveal_after)
        now = datetime.now(timezone.utc)
        if now >= reveal_after:
            return "resolution"
        return "investigation" if arc.progression_count > 0 else "discovery"

    def mark_progress(
        self,
        *,
        arc_id: str,
        clue_thread_id: str | None = None,
        related_share_id: str | None = None,
        resolution_thread_id: str | None = None,
        resolution_news_id: str | None = None,
        resolve: bool = False,
    ) -> StoryArcRecord:
        arc = self.get_arc(arc_id=arc_id)
        if arc is None:
            raise KeyError(f"Story arc not found: {arc_id}")

        new_status = "resolved" if resolve else arc.status
        updated_at = _now_iso()
        with self.session_manager.connect() as conn:
            conn.execute(
                """
                UPDATE story_arcs
                SET status = ?,
                    updated_at = ?,
                    clue_thread_id = ?,
                    resolution_thread_id = ?,
                    resolution_news_id = ?,
                    related_share_id = ?,
                    progression_count = ?
                WHERE arc_id = ?
                """,
                (
                    new_status,
                    updated_at,
                    (clue_thread_id if clue_thread_id is not None else arc.clue_thread_id),
                    (resolution_thread_id if resolution_thread_id is not None else arc.resolution_thread_id),
                    (resolution_news_id if resolution_news_id is not None else arc.resolution_news_id),
                    (related_share_id if related_share_id is not None else arc.related_share_id),
                    arc.progression_count + 1,
                    arc_id,
                ),
            )
            conn.commit()

        updated = self.get_arc(arc_id=arc_id)
        if updated is None:
            raise RuntimeError("Failed to load updated arc")
        return updated

    @staticmethod
    def _map_row(row) -> StoryArcRecord:
        return StoryArcRecord(
            arc_id=row["arc_id"],
            goal_key=row["goal_key"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            reveal_after=row["reveal_after"],
            clue_thread_id=row["clue_thread_id"],
            resolution_thread_id=row["resolution_thread_id"],
            resolution_news_id=row["resolution_news_id"],
            related_share_id=row["related_share_id"],
            progression_count=int(row["progression_count"]),
        )

    def _get_open_arc(self, *, goal_key: str) -> StoryArcRecord | None:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM story_arcs
                WHERE goal_key = ? AND status != 'resolved'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (goal_key,),
            ).fetchone()
        if row is None:
            return None
        return self._map_row(row)
