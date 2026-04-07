# Space Colony World Requirements

This document records the next-stage product direction for OnlineWorld.

## World Direction

The project should evolve into a space-colony-era web ecosystem with multiple interconnected sites:

- News site for official reports, incident updates, and final conclusions
- Forum for public discussion, speculation, analysis, and user uploads
- Additional sites later for logistics, shipping, archives, and official notices

The tone should feel like a living information network inside a large colonized space civilization, similar to an event chain in Elite Dangerous.

This is not limited to one scenario type. The same system should be able to support an open-ended range of story seeds and incident classes, including but not limited to:

- Missing cargo ships
- City conflicts and civic unrest
- Space exploration anomalies
- Strange or unexplained star systems
- Political disputes
- Corporate intrigue
- Scientific discoveries
- Frontier incidents

The intent is to preserve infinite imaginative breadth while keeping every event type grounded in the same persistent world model.

## Core Event Flow

1. A news story breaks, such as a missing cargo ship.
2. Forum discussion begins immediately.
3. Users post analysis, charts, images, logs, and evidence.
4. Official information is gradually revealed through subsequent reports.
5. Valuable forum findings are folded back into later news coverage.
6. The final news item closes the loop with a conclusion, possibly including wreckage images, logs, or black-box summaries.

Any future event category should be able to follow this same loop, even if the initial trigger is a riot, a deep-space discovery, a diplomatic crisis, or a strange stellar signal.

## World Simulation Requirements

### Person / User Database

Every character or user should be stored in the database with stable identity and social data, including:

- Real name
- Occupation
- Username / handle
- Gender
- Personality traits
- Background / role in society
- Any other attributes needed for long-term simulation

These records should support continuous identity across posts, news events, and future stories.

### Location Database

The world should not be limited to a fixed map. A dedicated location database is needed to store places where events may occur, including:

- Stations
- Docks
- Habitats
- Trade hubs
- Research sites
- Remote or newly discovered locations

The location system should be able to expand over time with a probability-based growth process, so the universe can naturally become larger as the simulation advances.

## Story Consistency Rules

- News should be able to reference useful forum discoveries.
- Forum discussion should be able to influence later official coverage.
- Evidence uploaded by users should remain visible as part of the event history.
- Final conclusions should feel earned through accumulated public and official information.

## Immediate Design Targets

- Define a persistent character table.
- Define a persistent location table.
- Define how locations are added over time.
- Define how news, forum posts, uploads, and official notices share event context.
- Keep the event chain consistent across all sites.

## Phase-1 Backend Start (Implemented)

The first backend foundation step has started with persistent world APIs:

- `GET /api/v1/world/characters`
	- Returns persistent character records (real_name, handle, occupation, gender, personality traits, status).
- `GET /api/v1/world/locations`
	- Returns current known space locations.
- `POST /api/v1/world/locations/expand`
	- Probabilistically expands the location set to grow the world over time.

These are base-world capabilities intended to support many event classes, not only missing-ship incidents.