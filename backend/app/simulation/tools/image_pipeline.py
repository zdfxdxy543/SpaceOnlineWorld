from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from urllib import error, request as urllib_request
from uuid import uuid4

from app.domain.events import StoryEvent
from app.simulation.protocol import (
    ActionRequest,
    CapabilitySpec,
    ConsistencyCheckResult,
    FactExecutionResult,
    PublicationResult,
)
from app.simulation.tools.workflow import AbstractCapabilityWorkflow, FiveStageToolExecutor


BACKEND_ROOT = Path(__file__).resolve().parents[3]
IMAGE_SAVE_DIR = BACKEND_ROOT / "storage" / "netdisk" / "ai_images"
IMAGE_SAVE_DIR.mkdir(parents=True, exist_ok=True)


class ImagePipelineToolExecutor(FiveStageToolExecutor):
    def __init__(self, content_generator) -> None:
        super().__init__(workflows=[ImageGenerationWorkflow()], content_generator=content_generator)

class ImageGenerationWorkflow(AbstractCapabilityWorkflow):
    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="image.generate",
            site="ai_image",
            description="使用硅基流动平台大模型API生成图片并保存本地",
            input_schema={
                "prompt": "string",
                "width": "integer optional",
                "height": "integer optional"
            },
            read_only=False,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        prompt = str(request.payload.get("prompt", "")).strip()
        width = int(request.payload.get("width", 512))
        height = int(request.payload.get("height", 512))
        if not prompt:
            raise ValueError("image.generate requires non-empty prompt")
        draft_id = str(uuid4())
        return FactExecutionResult(
            capability=request.capability,
            site="ai_image",
            actor_id=request.actor_id,
            facts=[f"图片生成草稿={draft_id}"],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="图片生成草稿已创建，等待内容生成。",
                    metadata={"draft_id": draft_id},
                )
            ],
            output={"draft_id": draft_id, "status": "draft_created"},
            generation_context={
                "draft_id": draft_id,
                "prompt": prompt,
                "width": width,
                "height": height,
            },
            requires_content_generation=False,
        )

    def publish(self, request: ActionRequest, fact_result: FactExecutionResult, validation_result: ConsistencyCheckResult) -> PublicationResult:
        draft_id = fact_result.output["draft_id"]
        context = fact_result.generation_context
        image_data, image_url = self._call_siliconflow_image_api(
            prompt=str(context.get("prompt", "")),
            width=int(context.get("width", 512)),
            height=int(context.get("height", 512)),
        )
        file_name = f"ai_image_{draft_id}.png"
        local_path = IMAGE_SAVE_DIR / file_name
        if image_data:
            with open(local_path, "wb") as file_obj:
                file_obj.write(self._decode_base64_image(str(image_data)))
        elif image_url:
            with urllib_request.urlopen(str(image_url), timeout=90) as response:
                with open(local_path, "wb") as file_obj:
                    file_obj.write(response.read())
        else:
            raise ValueError("No image data to save.")
        return PublicationResult(
            output={
                "draft_id": draft_id,
                "file_name": file_name,
                "local_path": str(local_path),
                "image_url": f"/api/v1/ai_image/{file_name}",
                "publication_status": "published",
            },
            facts=[f"已生成图片={file_name}"],
            events=[
                StoryEvent(
                    name="ContentPublished",
                    detail="AI图片已生成并保存到本地。",
                    metadata={"file_name": file_name, "local_path": str(local_path)},
                )
            ],
        )

    def _call_siliconflow_image_api(self, *, prompt: str, width: int, height: int) -> tuple[str | None, str | None]:
        api_key = os.getenv("SILICONFLOW_API_KEY", "sk-vxnqqulpbrduxkhpxmsfebvhyvwdxjebofqcjtdsjrggebvv").strip()
        if not api_key:
            raise ValueError("SILICONFLOW_API_KEY is missing")

        base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
        image_model = os.getenv("SILICONFLOW_IMAGE_MODEL", "Kwai-Kolors/Kolors")
        endpoint = f"{base_url}/images/generations"
        payload = {
            "model": image_model,
            "prompt": prompt,
            "size": f"{max(64, width)}x{max(64, height)}",
            "response_format": "url",
        }

        http_request = urllib_request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(http_request, timeout=90) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            try:
                body_preview = exc.read().decode("utf-8", errors="replace")[:400]
            except Exception:
                body_preview = "<unavailable>"
            raise RuntimeError(f"SiliconFlow image HTTP {exc.code}: {body_preview}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"SiliconFlow image URL error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("SiliconFlow image request timeout") from exc

        candidates = data.get("data") if isinstance(data, dict) else None
        if not isinstance(candidates, list) or not candidates:
            raise RuntimeError("SiliconFlow image response missing data list")

        first = candidates[0] if isinstance(candidates[0], dict) else {}
        image_url = first.get("url")
        image_data = first.get("b64_json") or first.get("base64")
        if image_url:
            return None, str(image_url)
        if image_data:
            return str(image_data), None
        raise RuntimeError("SiliconFlow image response missing url and b64_json")

    @staticmethod
    def _decode_base64_image(raw_image_data: str) -> bytes:
        payload = raw_image_data.strip()
        if payload.startswith("data:") and "," in payload:
            payload = payload.split(",", 1)[1]
        return base64.b64decode(payload)
