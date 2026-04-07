from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quick launcher for OnlineWorld backend")
    parser.add_argument("--host", default="127.0.0.1", help="Uvicorn host")
    parser.add_argument("--port", type=int, default=8000, help="Uvicorn port")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto reload")
    parser.add_argument("--init-db", action="store_true", help="Run DB initialization before server start")
    return parser.parse_args()


def run_init_db(backend_dir: Path) -> None:
    init_script = backend_dir / "scripts" / "init_db.py"
    command = [sys.executable, str(init_script)]
    subprocess.run(command, cwd=str(backend_dir), check=True)


def run_server(host: str, port: int, reload_enabled: bool, backend_dir: Path) -> None:
    if reload_enabled:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "runserver:app",
            "--host",
            host,
            "--port",
            str(port),
            "--reload",
        ]
        subprocess.run(command, cwd=str(backend_dir), check=True)
        return

    from runserver import app as asgi_app

    uvicorn.run(asgi_app, host=host, port=port, reload=False)


def main() -> None:
    args = parse_args()
    backend_dir = Path(__file__).resolve().parent

    if args.init_db:
        print("[startup] Initializing database...")
        run_init_db(backend_dir)

    print(
        f"[startup] Starting backend at http://{args.host}:{args.port} "
        f"(reload={'off' if args.no_reload else 'on'})"
    )
    run_server(args.host, args.port, not args.no_reload, backend_dir)


if __name__ == "__main__":
    main()
