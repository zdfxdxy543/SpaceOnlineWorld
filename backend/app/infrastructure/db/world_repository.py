from __future__ import annotations

import json
import random
from itertools import count
from datetime import datetime, timezone

from app.domain.events import StoryEvent
from app.domain.models import AgentProfile, AgentSummary, SpaceLocation, WorldCharacter, WorldResource, WorldSnapshot
from app.infrastructure.db.session import DatabaseSessionManager
from app.repositories.world_repository import AbstractWorldRepository


class SQLiteWorldRepository(AbstractWorldRepository):
    def __init__(self, session_manager: DatabaseSessionManager) -> None:
        self.session_manager = session_manager
        self._resource_counter = count(1)
        self._agent_counter = count(1)
        self._legacy_agent_alias = {
            "agent-001": "aria",
            "agent-002": "milo",
            "agent-003": "eve",
        }

    def initialize(self) -> None:
        with self.session_manager.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS world_resources (
                    resource_id TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    access_code TEXT NOT NULL,
                    owner_agent_id TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    gender TEXT NOT NULL,
                    age_range TEXT NOT NULL,
                    occupation TEXT NOT NULL,
                    residence_city TEXT NOT NULL,
                    native_language TEXT NOT NULL,
                    bio TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_site_accounts (
                    agent_id TEXT NOT NULL,
                    site_code TEXT NOT NULL,
                    site_user_id TEXT NOT NULL,
                    site_username TEXT NOT NULL,
                    account_status TEXT NOT NULL,
                    trust_level INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (agent_id, site_code),
                    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
                );

                CREATE TABLE IF NOT EXISTS agent_profiles (
                    agent_id TEXT PRIMARY KEY,
                    personality_traits_json TEXT NOT NULL,
                    values_json TEXT NOT NULL,
                    hobbies_json TEXT NOT NULL,
                    work_schedule_json TEXT NOT NULL,
                    risk_preference TEXT NOT NULL,
                    trust_baseline INTEGER NOT NULL,
                    private_motives_json TEXT NOT NULL,
                    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
                );

                CREATE TABLE IF NOT EXISTS world_characters (
                    character_id TEXT PRIMARY KEY,
                    real_name TEXT NOT NULL,
                    handle TEXT NOT NULL,
                    occupation TEXT NOT NULL,
                    gender TEXT NOT NULL,
                    personality_traits_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    home_location_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS space_locations (
                    location_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    location_type TEXT NOT NULL,
                    region TEXT NOT NULL,
                    description TEXT NOT NULL,
                    discovered_at TEXT NOT NULL,
                    discovery_source TEXT NOT NULL,
                    parent_location_id TEXT,
                    expansion_tier INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                """
            )

            self._migrate_forum_users_to_agents(conn)
            self._seed_additional_agents(conn)
            self._seed_space_locations(conn)
            self._sync_world_characters_from_agents(conn)

            row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(resource_id, 7) AS INTEGER)), 0) AS max_id FROM world_resources"
            ).fetchone()
            next_id = int(row["max_id"]) + 1
            self._resource_counter = count(next_id)

            agent_row = conn.execute("SELECT COUNT(1) AS total FROM agents").fetchone()
            self._agent_counter = count(int(agent_row["total"]) + 1)
            conn.commit()

    def list_world_characters(self) -> list[WorldCharacter]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    character_id,
                    real_name,
                    handle,
                    occupation,
                    gender,
                    personality_traits_json,
                    status,
                    home_location_id,
                    created_at,
                    updated_at
                FROM world_characters
                ORDER BY character_id ASC
                """
            ).fetchall()

        result: list[WorldCharacter] = []
        for row in rows:
            try:
                personality_traits = json.loads(row["personality_traits_json"])
            except json.JSONDecodeError:
                personality_traits = []
            result.append(
                WorldCharacter(
                    character_id=row["character_id"],
                    real_name=row["real_name"],
                    handle=row["handle"],
                    occupation=row["occupation"],
                    gender=row["gender"],
                    personality_traits=personality_traits,
                    status=row["status"],
                    home_location_id=row["home_location_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        return result

    def list_space_locations(self) -> list[SpaceLocation]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    location_id,
                    name,
                    location_type,
                    region,
                    description,
                    discovered_at,
                    discovery_source,
                    parent_location_id,
                    expansion_tier,
                    metadata_json
                FROM space_locations
                ORDER BY discovered_at ASC, location_id ASC
                """
            ).fetchall()

        locations: list[SpaceLocation] = []
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"])
            except json.JSONDecodeError:
                metadata = {}
            locations.append(
                SpaceLocation(
                    location_id=row["location_id"],
                    name=row["name"],
                    location_type=row["location_type"],
                    region=row["region"],
                    description=row["description"],
                    discovered_at=row["discovered_at"],
                    discovery_source=row["discovery_source"],
                    parent_location_id=row["parent_location_id"],
                    expansion_tier=int(row["expansion_tier"]),
                    metadata=metadata,
                )
            )
        return locations

    def expand_space_locations(self, *, probability: float, max_new_locations: int) -> list[SpaceLocation]:
        if probability <= 0 or max_new_locations <= 0:
            return []

        created: list[SpaceLocation] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        location_type_pool = ["frontier_outpost", "anomaly_sector", "relay_station", "survey_zone"]
        region_pool = ["Perimeter Expanse", "Outer Rim", "Drift Corridor", "Abyssal Reach"]

        with self.session_manager.connect() as conn:
            existing_ids = {
                row["location_id"]
                for row in conn.execute("SELECT location_id FROM space_locations").fetchall()
            }
            parent_ids = list(existing_ids)

            attempts = 0
            max_attempts = max_new_locations * 12
            while len(created) < max_new_locations and attempts < max_attempts:
                attempts += 1
                if random.random() > probability:
                    continue

                index = len(existing_ids) + len(created) + 1
                location_id = f"loc-frontier-{index:04d}"
                if location_id in existing_ids:
                    continue

                name = f"Frontier-{index:04d}"
                parent_location_id = random.choice(parent_ids) if parent_ids else None
                metadata = {"seed": "probabilistic_growth", "narrative_ready": "true"}
                location = SpaceLocation(
                    location_id=location_id,
                    name=name,
                    location_type=random.choice(location_type_pool),
                    region=random.choice(region_pool),
                    description="Recently charted region with incomplete public data.",
                    discovered_at=now_iso,
                    discovery_source="probabilistic_expansion",
                    parent_location_id=parent_location_id,
                    expansion_tier=2,
                    metadata=metadata,
                )
                conn.execute(
                    """
                    INSERT INTO space_locations (
                        location_id,
                        name,
                        location_type,
                        region,
                        description,
                        discovered_at,
                        discovery_source,
                        parent_location_id,
                        expansion_tier,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        location.location_id,
                        location.name,
                        location.location_type,
                        location.region,
                        location.description,
                        location.discovered_at,
                        location.discovery_source,
                        location.parent_location_id,
                        location.expansion_tier,
                        json.dumps(location.metadata, ensure_ascii=True),
                    ),
                )
                created.append(location)
                existing_ids.add(location_id)
                parent_ids.append(location_id)

            conn.commit()

        return created

    def get_world_snapshot(self) -> WorldSnapshot:
        with self.session_manager.connect() as conn:
            thread_count = conn.execute("SELECT COUNT(1) AS count FROM threads").fetchone()["count"]
            post_count = conn.execute("SELECT COUNT(1) AS count FROM posts").fetchone()["count"]

        recent_events = [
            StoryEvent(
                name="WorldSnapshotBuilt",
                detail="世界快照已从 SQL 状态聚合。",
                metadata={"thread_count": str(thread_count), "post_count": str(post_count)},
            )
        ]
        return WorldSnapshot(
            current_tick=1,
            current_time_label="Day 1 / 08:00",
            active_sites=["forum.main", "market.square", "message.direct"],
            recent_events=recent_events,
        )

    def get_agent(self, agent_id: str) -> AgentProfile:
        resolved_id = self._legacy_agent_alias.get(agent_id, agent_id)

        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT agent_id, display_name, occupation, bio
                FROM agents
                WHERE agent_id = ?
                """,
                (resolved_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Agent not found: {agent_id}")

        return AgentProfile(
            agent_id=row["agent_id"],
            display_name=row["display_name"],
            role=row["occupation"],
            goals=[row["bio"]],
        )

    def list_agents(self) -> list[AgentSummary]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    a.agent_id,
                    a.display_name,
                    a.status,
                    a.gender,
                    a.age_range,
                    a.occupation,
                    a.residence_city,
                    a.native_language,
                    p.personality_traits_json,
                    p.values_json,
                    p.hobbies_json
                FROM agents a
                LEFT JOIN agent_profiles p ON p.agent_id = a.agent_id
                ORDER BY a.agent_id ASC
                """
            ).fetchall()

        return [
            AgentSummary(
                agent_id=row["agent_id"],
                display_name=row["display_name"],
                status=row["status"],
                gender=row["gender"],
                age_range=row["age_range"],
                occupation=row["occupation"],
                residence_city=row["residence_city"],
                native_language=row["native_language"],
                personality_traits_json=row["personality_traits_json"] or "[]",
                values_json=row["values_json"] or "[]",
                hobbies_json=row["hobbies_json"] or "[]",
            )
            for row in rows
        ]

    def agent_exists(self, agent_id: str) -> bool:
        resolved_id = self._legacy_agent_alias.get(agent_id, agent_id)
        with self.session_manager.connect() as conn:
            row = conn.execute("SELECT 1 AS exists_flag FROM agents WHERE agent_id = ?", (resolved_id,)).fetchone()
        return row is not None

    def create_cloud_resource(self, *, owner_agent_id: str, site_id: str, title: str) -> WorldResource:
        index = next(self._resource_counter)
        resource_id = f"cloud-{index:04d}"
        access_code = f"K{index:03d}X"
        metadata = {
            "download_hint": f"https://files.local/{resource_id}",
            "visibility": "shared-with-link",
        }

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO world_resources (
                    resource_id,
                    resource_type,
                    title,
                    access_code,
                    owner_agent_id,
                    site_id,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resource_id,
                    "cloud_file",
                    title,
                    access_code,
                    owner_agent_id,
                    site_id,
                    json.dumps(metadata, ensure_ascii=True),
                ),
            )
            conn.commit()

        return WorldResource(
            resource_id=resource_id,
            resource_type="cloud_file",
            title=title,
            access_code=access_code,
            owner_agent_id=owner_agent_id,
            site_id=site_id,
            metadata=metadata,
        )

    def create_random_agent(self) -> AgentSummary:
        occupations = ["夜班保安", "网络维护员", "物流分拣员", "便利店店长", "旧货修复师", "出租车司机"]
        cities = ["Linhai", "Beicheng", "Yunzhou", "Haidong", "Nanshan"]
        age_ranges = ["18-24", "25-34", "35-44"]
        genders = ["female", "male", "non-binary"]

        gender = random.choice(genders)
        agent_id, display_name = self._generate_human_identity(gender=gender)
        status = random.choice(["Online", "Away", "Busy"])
        occupation = random.choice(occupations)
        residence_city = random.choice(cities)
        age_range = random.choice(age_ranges)
        native_language = random.choice(["zh-CN", "en-US"])
        bio = f"{display_name} works as {occupation} in {residence_city} and often monitors local rumor signals."
        site_username = self._generate_site_username()
        now = datetime.now(timezone.utc).isoformat()

        personality_traits = random.sample(["curious", "cautious", "blunt", "empathetic", "meticulous"], k=2)
        values = random.sample(["safety", "truth", "privacy", "loyalty", "efficiency"], k=2)
        hobbies = random.sample(["night forums", "radio scanning", "street photography", "retro games"], k=2)

        with self.session_manager.connect() as conn:
            self._insert_agent_bundle(
                conn,
                agent_id=agent_id,
                display_name=display_name,
                status=status,
                gender=gender,
                age_range=age_range,
                occupation=occupation,
                residence_city=residence_city,
                native_language=native_language,
                bio=bio,
                personality_traits=personality_traits,
                values=values,
                hobbies=hobbies,
                site_username=site_username,
                now_iso=now,
                source="scheduler_random_spawn",
            )
            conn.commit()

        return AgentSummary(
            agent_id=agent_id,
            display_name=display_name,
            status=status,
            gender=gender,
            age_range=age_range,
            occupation=occupation,
            residence_city=residence_city,
            native_language=native_language,
            personality_traits_json=json.dumps(personality_traits, ensure_ascii=True),
            values_json=json.dumps(values, ensure_ascii=True),
            hobbies_json=json.dumps(hobbies, ensure_ascii=True),
        )

    def _generate_human_identity(self, *, gender: str) -> tuple[str, str]:
        female_first_names = ["Aria", "Eve", "Nora", "Selene", "Mia", "Lina", "Zoe", "Iris"]
        male_first_names = ["Kai", "Milo", "Noah", "Ethan", "Leo", "Evan", "Ryan", "Adam"]
        neutral_first_names = ["Alex", "River", "Sky", "Sage", "Robin", "Casey", "Jamie", "Avery"]
        last_names = ["Chen", "Lin", "Zhao", "Wang", "Liu", "Kim", "Park", "Morris", "Reed", "Clark"]

        if gender == "female":
            first_pool = female_first_names
        elif gender == "male":
            first_pool = male_first_names
        else:
            first_pool = neutral_first_names

        with self.session_manager.connect() as conn:
            for _ in range(30):
                first = random.choice(first_pool)
                last = random.choice(last_names)
                display_name = f"{first} {last}"
                base_id = first.lower()
                candidate_id = base_id
                if self._agent_id_exists(conn, candidate_id):
                    candidate_id = f"{base_id}{next(self._agent_counter):03d}"
                if not self._agent_id_exists(conn, candidate_id):
                    return candidate_id, display_name

            fallback_first = random.choice(first_pool)
            fallback_last = random.choice(last_names)
            return f"resident{next(self._agent_counter):04d}", f"{fallback_first} {fallback_last}"

    @staticmethod
    def _agent_id_exists(conn, agent_id: str) -> bool:
        row = conn.execute("SELECT 1 AS exists_flag FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        return row is not None

    @staticmethod
    def _generate_site_username() -> str:
        adjectives = ["silent", "amber", "north", "grey", "neon", "paper"]
        nouns = ["courier", "lantern", "thread", "switch", "relay", "watcher"]
        suffix = random.randint(10, 99)
        return f"{random.choice(adjectives)}_{random.choice(nouns)}_{suffix}"

    def _migrate_forum_users_to_agents(self, conn) -> None:
        count_row = conn.execute("SELECT COUNT(1) AS count FROM agents").fetchone()
        if int(count_row["count"]) > 0:
            return

        users = conn.execute(
            """
            SELECT id, name, title, status, bio
            FROM users
            ORDER BY id ASC
            """
        ).fetchall()
        if not users:
            return

        now = datetime.now(timezone.utc).isoformat()
        for row in users:
            self._insert_agent_bundle(
                conn,
                agent_id=row["id"],
                display_name=row["name"],
                status=row["status"],
                gender="unknown",
                age_range="25-34",
                occupation=row["title"],
                residence_city="unknown",
                native_language="zh-CN",
                bio=row["bio"],
                personality_traits=["observant", "cautious"],
                values=["consistency", "credibility"],
                hobbies=["forum", "investigation"],
                now_iso=now,
                source="users_migration",
            )

    def _seed_additional_agents(self, conn) -> None:
        now = datetime.now(timezone.utc).isoformat()
        seeded_agents = [
            {
                "agent_id": "nora",
                "display_name": "Nora_Signal",
                "status": "Online",
                "gender": "female",
                "age_range": "25-34",
                "occupation": "Emergency Dispatcher",
                "residence_city": "Linhai",
                "native_language": "zh-CN",
                "bio": "Tracks late-night emergency chatter and timestamps unusual reports.",
                "personality_traits": ["calm", "methodical"],
                "values": ["duty", "accuracy"],
                "hobbies": ["ham radio", "crossword"],
            },
            {
                "agent_id": "kai",
                "display_name": "Kai_Backlane",
                "status": "Away",
                "gender": "male",
                "age_range": "18-24",
                "occupation": "Bike Courier",
                "residence_city": "Beicheng",
                "native_language": "zh-CN",
                "bio": "Knows alley shortcuts and picks up fragmented gossip across districts.",
                "personality_traits": ["bold", "street-smart"],
                "values": ["speed", "loyalty"],
                "hobbies": ["fixed-gear", "retro arcades"],
            },
            {
                "agent_id": "selene",
                "display_name": "Selene_Archive",
                "status": "Busy",
                "gender": "female",
                "age_range": "35-44",
                "occupation": "Museum Cataloger",
                "residence_city": "Yunzhou",
                "native_language": "en-US",
                "bio": "Cross-checks old catalog records with current urban legends.",
                "personality_traits": ["patient", "analytical"],
                "values": ["truth", "context"],
                "hobbies": ["film photography", "microfilm"],
            },
        ]

        for item in seeded_agents:
            self._insert_agent_bundle(
                conn,
                agent_id=item["agent_id"],
                display_name=item["display_name"],
                status=item["status"],
                gender=item["gender"],
                age_range=item["age_range"],
                occupation=item["occupation"],
                residence_city=item["residence_city"],
                native_language=item["native_language"],
                bio=item["bio"],
                personality_traits=item["personality_traits"],
                values=item["values"],
                hobbies=item["hobbies"],
                now_iso=now,
                source="starter_seed",
            )

    def _seed_space_locations(self, conn) -> None:
        count_row = conn.execute("SELECT COUNT(1) AS count FROM space_locations").fetchone()
        if int(count_row["count"]) > 0:
            return

        seeded_locations = [
            (
                "loc-sol-prime",
                "Sol Prime",
                "core_world",
                "Inner Ring",
                "Administrative and media core of nearby colonies.",
                "founding_registry",
                None,
                1,
                {"security_level": "high"},
            ),
            (
                "loc-helios-gate",
                "Helios Gate",
                "trade_hub",
                "Transit Belt",
                "Major cargo gate station with dense civilian traffic.",
                "founding_registry",
                "loc-sol-prime",
                1,
                {"cargo_density": "high"},
            ),
            (
                "loc-lyra-yard",
                "Lyra Drydock",
                "industrial_dock",
                "Outer Manufacturing Arc",
                "Ship repair and debris analysis dock.",
                "founding_registry",
                "loc-helios-gate",
                1,
                {"forensics_capable": "true"},
            ),
        ]
        now_iso = datetime.now(timezone.utc).isoformat()
        for item in seeded_locations:
            conn.execute(
                """
                INSERT INTO space_locations (
                    location_id,
                    name,
                    location_type,
                    region,
                    description,
                    discovered_at,
                    discovery_source,
                    parent_location_id,
                    expansion_tier,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item[0],
                    item[1],
                    item[2],
                    item[3],
                    item[4],
                    now_iso,
                    item[5],
                    item[6],
                    item[7],
                    json.dumps(item[8], ensure_ascii=True),
                ),
            )

    def _sync_world_characters_from_agents(self, conn) -> None:
        rows = conn.execute(
            """
            SELECT
                a.agent_id,
                a.display_name,
                a.occupation,
                a.gender,
                a.status,
                a.created_at,
                a.updated_at,
                s.site_username,
                p.personality_traits_json
            FROM agents a
            LEFT JOIN agent_site_accounts s
                ON s.agent_id = a.agent_id AND s.site_code = 'forum'
            LEFT JOIN agent_profiles p
                ON p.agent_id = a.agent_id
            ORDER BY a.agent_id ASC
            """
        ).fetchall()

        default_home = conn.execute(
            "SELECT location_id FROM space_locations ORDER BY location_id ASC LIMIT 1"
        ).fetchone()
        default_home_id = default_home["location_id"] if default_home else None

        for row in rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO world_characters (
                    character_id,
                    real_name,
                    handle,
                    occupation,
                    gender,
                    personality_traits_json,
                    status,
                    home_location_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["agent_id"],
                    row["display_name"],
                    row["site_username"] or row["display_name"],
                    row["occupation"],
                    row["gender"],
                    row["personality_traits_json"] or "[]",
                    row["status"],
                    default_home_id,
                    row["created_at"],
                    row["updated_at"],
                ),
            )

    def _insert_agent_bundle(
        self,
        conn,
        *,
        agent_id: str,
        display_name: str,
        status: str,
        gender: str,
        age_range: str,
        occupation: str,
        residence_city: str,
        native_language: str,
        bio: str,
        personality_traits: list[str],
        values: list[str],
        hobbies: list[str],
        site_username: str | None = None,
        now_iso: str,
        source: str,
    ) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, name, title, join_date, posts, reputation, status, signature, bio)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                display_name,
                occupation,
                now_iso[:10],
                0,
                100,
                status,
                "Signals over noise.",
                bio,
            ),
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO agents (
                agent_id,
                display_name,
                status,
                gender,
                age_range,
                occupation,
                residence_city,
                native_language,
                bio,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                display_name,
                status,
                gender,
                age_range,
                occupation,
                residence_city,
                native_language,
                bio,
                now_iso,
                now_iso,
            ),
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO agent_site_accounts (
                agent_id,
                site_code,
                site_user_id,
                site_username,
                account_status,
                trust_level,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                "forum",
                agent_id,
                site_username or display_name,
                "active",
                50,
                json.dumps({"source": source, "gender": gender}, ensure_ascii=True),
            ),
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO agent_profiles (
                agent_id,
                personality_traits_json,
                values_json,
                hobbies_json,
                work_schedule_json,
                risk_preference,
                trust_baseline,
                private_motives_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                json.dumps(personality_traits, ensure_ascii=True),
                json.dumps(values, ensure_ascii=True),
                json.dumps(hobbies, ensure_ascii=True),
                json.dumps({"active_hours": ["08:00-22:00"]}, ensure_ascii=True),
                "medium",
                50,
                json.dumps(["maintain_safety_margin"], ensure_ascii=True),
            ),
        )
