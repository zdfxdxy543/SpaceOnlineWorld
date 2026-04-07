from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
APP_DIR = BACKEND_DIR / "app"
MAIN_FILE = APP_DIR / "main.py"


def _load_asgi_app():
    # Create a synthetic package named "app" so absolute imports like
    # "from app.api.router import ..." continue to work even with backend/app.py present.
    package = types.ModuleType("app")
    package.__path__ = [str(APP_DIR)]
    sys.modules["app"] = package

    spec = importlib.util.spec_from_file_location("app.main", MAIN_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load ASGI app module")

    module = importlib.util.module_from_spec(spec)
    sys.modules["app.main"] = module
    spec.loader.exec_module(module)
    return module.app


app = _load_asgi_app()
