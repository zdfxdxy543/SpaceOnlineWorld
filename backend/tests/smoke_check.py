from __future__ import annotations

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app


def main() -> None:
    route_paths = sorted(route.path for route in app.routes)
    expected = {"/", "/api/v1/health", "/api/v1/world/demo-post", "/api/v1/world/summary"}
    missing = expected.difference(route_paths)
    if missing:
        raise SystemExit(f"Missing expected routes: {sorted(missing)}")
    print("Smoke check passed.")
    for path in route_paths:
        print(path)


if __name__ == "__main__":
    main()