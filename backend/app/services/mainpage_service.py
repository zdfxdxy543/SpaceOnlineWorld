from __future__ import annotations

import json
import re
from typing import Any

from app.repositories.mainpage_repository import AbstractMainPageRepository, MainPageDraft, MainPageRecord


class MainPageService:
    def __init__(self, repository: AbstractMainPageRepository) -> None:
        self.repository = repository

    def create_page_draft(
        self,
        *,
        author_id: str,
        title: str,
        description: str,
        slug: str | None,
        style: str,
    ) -> MainPageDraft:
        clean_title = title.strip() or "Untitled Page"
        clean_description = description.strip() or "Generate a general informative page."
        clean_style = style.strip() or "world_website"
        slug_hint = (slug or clean_title).strip()

        return self.repository.create_page_draft(
            author_id=author_id,
            slug_hint=slug_hint,
            requested_title=clean_title,
            requested_description=clean_description,
            requested_style=clean_style,
        )

    def publish_page_draft(
        self,
        *,
        draft_id: str,
        title: str,
        html_content: str,
        assets: Any,
    ) -> MainPageRecord:
        normalized_title = title.strip() or "Generated Page"
        normalized_html = self._sanitize_html(html_content)
        normalized_assets_json = json.dumps(self._normalize_assets(assets), ensure_ascii=True)

        return self.repository.publish_page_draft(
            draft_id=draft_id,
            title=normalized_title,
            html_content=normalized_html,
            assets_json=normalized_assets_json,
        )

    def get_page_by_slug(self, *, slug: str) -> MainPageRecord | None:
        return self.repository.get_page_by_slug(slug=slug.strip())

    def list_pages(self, *, limit: int = 50) -> list[MainPageRecord]:
        return self.repository.list_pages(limit=limit)

    @staticmethod
    def _sanitize_html(value: str) -> str:
        html = value.strip()
        if not html:
            raise ValueError("Generated html_content is empty")

        # Remove script blocks to reduce XSS risk from generated output.
        html = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", "", html, flags=re.IGNORECASE)
        # Remove inline event handlers like onclick/onload.
        html = re.sub(r"\s+on[a-zA-Z]+\s*=\s*\"[^\"]*\"", "", html)
        html = re.sub(r"\s+on[a-zA-Z]+\s*=\s*'[^']*'", "", html)

        if "<html" not in html.lower():
            html = (
                "<!doctype html><html><head><meta charset=\"utf-8\" /><title>Generated Page</title></head><body>"
                + html
                + "</body></html>"
            )
        return html[:120000]

    @staticmethod
    def _normalize_assets(assets: Any) -> list[dict[str, str]]:
        if isinstance(assets, list):
            items = assets
        elif isinstance(assets, dict):
            items = [assets]
        else:
            items = []

        normalized: list[dict[str, str]] = []
        for item in items[:20]:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip()
            content = str(item.get("content", "")).strip()
            content_type = str(item.get("content_type", "text/plain")).strip() or "text/plain"
            if not path or not content:
                continue
            normalized.append(
                {
                    "path": path[:200],
                    "content": content[:20000],
                    "content_type": content_type[:80],
                }
            )
        return normalized
