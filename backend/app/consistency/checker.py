from __future__ import annotations

import re

from app.domain.models import DraftPostPlan


class ConsistencyChecker:
    def validate_post_content(self, plan: DraftPostPlan, content: str) -> list[str]:
        violations: list[str] = []

        if plan.referenced_resource is not None:
            if plan.referenced_resource.resource_id not in content:
                violations.append("missing-resource-id")
            if plan.referenced_resource.access_code not in content:
                violations.append("missing-access-code")

        for fact in plan.facts:
            if fact not in content:
                violations.append(f"missing-fact:{fact}")

        return violations

    def validate_minimum_length(self, *, field_name: str, value: str, minimum_length: int) -> list[str]:
        if len(value.strip()) < minimum_length:
            return [f"too-short:{field_name}"]
        return []

    def validate_against_placeholders(self, *, field_name: str, value: str, placeholders: list[str]) -> list[str]:
        normalized = value.strip().lower()
        violations: list[str] = []
        for placeholder in placeholders:
            candidate = placeholder.strip().lower()
            if candidate and normalized == candidate:
                violations.append(f"generic-placeholder:{field_name}:{placeholder}")
        return violations

    def validate_required_fields(self, fields: dict[str, str], required_fields: list[str]) -> list[str]:
        violations: list[str] = []
        for field_name in required_fields:
            value = str(fields.get(field_name, "")).strip()
            if not value:
                violations.append(f"missing-field:{field_name}")
        return violations

    def detect_unresolved_references(self, fields: dict[str, str]) -> list[str]:
        violations: list[str] = []
        reference_pattern = re.compile(r"\$step[-_\w\.\[\]]+")
        legacy_pattern = re.compile(r"(thread|board|post)_from_step[-_]\d+", re.IGNORECASE)
        for field_name, raw_value in fields.items():
            value = str(raw_value)
            if reference_pattern.search(value):
                violations.append(f"unresolved-reference:{field_name}")
            if legacy_pattern.search(value):
                violations.append(f"legacy-reference:{field_name}")
        return violations

    def validate_netdisk_reference(self, *, content: str, share_id: str, access_code: str) -> list[str]:
        if not share_id and not access_code:
            return []

        violations: list[str] = []
        if share_id and share_id not in content:
            violations.append("missing-netdisk-share-id")
        if access_code and access_code not in content:
            violations.append("missing-netdisk-access-code")
        return violations

    def validate_news_references(
        self,
        *,
        content: str,
        related_thread_ids: list[str],
        related_share_ids: list[str],
    ) -> list[str]:
        violations: list[str] = []
        for thread_id in related_thread_ids:
            if thread_id and thread_id not in content:
                violations.append(f"missing-related-thread-id:{thread_id}")
        for share_id in related_share_ids:
            if share_id and share_id not in content:
                violations.append(f"missing-related-share-id:{share_id}")
        return violations
