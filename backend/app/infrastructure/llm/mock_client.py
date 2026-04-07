from __future__ import annotations

from app.domain.models import DraftPostPlan
from app.infrastructure.llm.base import AbstractLLMClient


class MockLLMClient(AbstractLLMClient):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def generate_forum_post(self, plan: DraftPostPlan) -> str:
        opening = f"大家好，我是{plan.agent.display_name}。关于“{plan.topic}”，我先把当前确认过的内容贴出来。"

        lines = [opening]
        for fact in plan.facts:
            lines.append(f"- {fact}")

        if plan.referenced_resource is not None:
            lines.append(
                "文件已经实际上传到共享网盘："
                f"ID={plan.referenced_resource.resource_id}，"
                f"提取码={plan.referenced_resource.access_code}。"
            )

        lines.append("如果后续有人发现矛盾信息，我会继续补充事件链。")
        return "\n".join(lines)
