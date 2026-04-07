from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(slots=True)
class DatabaseSessionManager:
    database_url: str
    initialized: bool = False

    def connect(self) -> sqlite3.Connection:
        sqlite_path = self.sqlite_path()
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(sqlite_path))
        connection.row_factory = sqlite3.Row
        return connection

    def mark_initialized(self) -> None:
        self.initialized = True

    def sqlite_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Only sqlite database URLs are supported in the current setup")
        raw_path = self.database_url[len(prefix) :]
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    def describe(self) -> dict[str, str]:
        return {
            "database_url": self.database_url,
            "status": "ready" if self.initialized else "configured",
            "mode": "sqlite",
        }
