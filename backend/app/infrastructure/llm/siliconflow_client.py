from __future__ import annotations

import json
from urllib import error, request

from app.domain.models import DraftPostPlan
from app.infrastructure.llm.base import AbstractLLMClient


class SiliconFlowLLMClient(AbstractLLMClient):
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        base_url: str,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.max_attempts = max(1, max_attempts)

    def generate_forum_post(self, plan: DraftPostPlan) -> str:
        payload = self._build_payload(plan)
        last_error = "unknown error"
        for _attempt in range(1, self.max_attempts + 1):
            content, error_reason = self._call_model(payload)
            if content is not None and content.strip():
                return content.strip()
            last_error = error_reason or "invalid or empty forum post response"

        raise RuntimeError(
            f"SiliconFlow forum post generation failed after {self.max_attempts} attempts: {last_error}"
        )

    def _build_payload(self, plan: DraftPostPlan) -> dict:
        facts = list(plan.facts)
        referenced_resource = None
        if plan.referenced_resource is not None:
            referenced_resource = {
                "resource_id": plan.referenced_resource.resource_id,
                "resource_type": plan.referenced_resource.resource_type,
                "title": plan.referenced_resource.title,
                "access_code": plan.referenced_resource.access_code,
                "site_id": plan.referenced_resource.site_id,
                "metadata": plan.referenced_resource.metadata,
            }

        system_prompt = (
            "You are a forum post generator for a multi-site AI society simulation. "
            "Write only the final publishable forum post in Chinese or English as appropriate to the provided facts. "
            "Do not output JSON, meta commentary, prompt text, or instructions. "
            "Do not invent facts that are not present in the input."
        )
        user_prompt = {
            "agent_name": plan.agent.display_name,
            "topic": plan.topic,
            "facts": facts,
            "referenced_resource": referenced_resource,
        }
        return {
            "model": self.model_name,
            "temperature": 0.6,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
            ],
        }

    def _call_model(self, payload: dict) -> tuple[str | None, str | None]:
        endpoint = f"{self.base_url}/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=60) as response:
                response_text = response.read().decode("utf-8")
        except TimeoutError:
            return None, "timeout"
        except error.HTTPError as exc:
            try:
                body_preview = exc.read().decode("utf-8", errors="replace")[:400]
            except Exception:
                body_preview = "<unavailable>"
            return None, f"http {exc.code}: {body_preview}"
        except error.URLError as exc:
            return None, f"url_error: {exc.reason}"

        try:
            data = json.loads(response_text)
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                return None, "forum_post_not_string"
            return content, None
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return None, f"response_parse_error: {exc}"