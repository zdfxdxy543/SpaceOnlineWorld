from __future__ import annotations

import json
from pathlib import Path
import sys
from urllib import error, request

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.main import create_app
from app.simulation.planner import RuleBasedStoryPlanner
from app.infrastructure.llm.siliconflow_planner import SiliconFlowStoryPlanner
from app.simulation.protocol import CapabilitySpec


def send_chat_request(model_name: str, label: str) -> dict[str, str | int | bool]:
    settings = get_settings()
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": 'Return ONLY JSON: {"ok": true}',
            }
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    http_request = request.Request(
        f"{settings.siliconflow_base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.siliconflow_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=45) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {
                "label": label,
                "model": model_name,
                "ok": True,
                "http_status": response.status,
                "body_preview": body[:1000],
            }
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "label": label,
            "model": model_name,
            "ok": False,
            "http_status": exc.code,
            "reason": str(exc.reason),
            "body_preview": body[:1000],
        }
    except Exception as exc:
        return {
            "label": label,
            "model": model_name,
            "ok": False,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }


def main() -> None:
    settings = get_settings()
    results = [
        send_chat_request(settings.siliconflow_planner_model, "planner_model"),
        send_chat_request(settings.llm_model, "content_model"),
    ]

    planner = SiliconFlowStoryPlanner(
        api_key=settings.siliconflow_api_key,
        model_name=settings.siliconflow_planner_model,
        base_url=settings.siliconflow_base_url,
        fallback=RuleBasedStoryPlanner(),
    )
    capabilities = [
        CapabilitySpec(
            name="forum.read_board",
            site="forum",
            description="Read threads under a board.",
            input_schema={"board_slug": "string", "allowed_board_slugs": ["town-square"]},
            read_only=True,
        ),
        CapabilitySpec(
            name="forum.create_thread",
            site="forum",
            description="Create a thread in board with first post.",
            input_schema={
                "board_slug": "string",
                "title": "string",
                "content": "string",
                "tags": "string[] optional",
                "allowed_board_slugs": ["town-square"],
            },
            read_only=False,
        ),
    ]
    planner_payload = planner._build_payload(
        goal="整理一条新的公共线索并发到论坛",
        actors=["aria"],
        capabilities=capabilities,
    )
    results.append(send_raw_payload(settings.siliconflow_planner_model, "planner_real_payload", planner_payload))

    app = create_app()
    live_capabilities = app.state.container.tool_registry.list_capabilities()
    live_payload = planner._build_payload(
        goal="直接测试规划器",
        actors=["aria"],
        capabilities=live_capabilities,
    )
    results.append(send_raw_payload(settings.siliconflow_planner_model, "planner_live_capabilities", live_payload))
    print(json.dumps(results, ensure_ascii=False, indent=2))


def send_raw_payload(model_name: str, label: str, payload: dict) -> dict[str, str | int | bool]:
    settings = get_settings()
    http_request = request.Request(
        f"{settings.siliconflow_base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.siliconflow_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=45) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            content = parsed["choices"][0]["message"]["content"]
            parse_ok = False
            parse_error = None
            if isinstance(content, str):
                try:
                    json.loads(content)
                    parse_ok = True
                except Exception as exc:  # noqa: BLE001
                    parse_error = f"{type(exc).__name__}: {exc}"
            elif isinstance(content, dict):
                parse_ok = True
            return {
                "label": label,
                "model": model_name,
                "ok": True,
                "http_status": response.status,
                "content_parse_ok": parse_ok,
                "content_parse_error": parse_error,
                "content_preview": content[:1200] if isinstance(content, str) else json.dumps(content, ensure_ascii=False)[:1200],
            }
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "label": label,
            "model": model_name,
            "ok": False,
            "http_status": exc.code,
            "reason": str(exc.reason),
            "body_preview": body[:1000],
        }
    except Exception as exc:
        return {
            "label": label,
            "model": model_name,
            "ok": False,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }


if __name__ == "__main__":
    main()
