from __future__ import annotations

from app.domain.events import StoryEvent
from app.services.forum_service import ForumService
from app.simulation.content_sanitizer import sanitize_forum_content, sanitize_forum_title
from app.simulation.protocol import ActionRequest, ActionResult, CapabilitySpec


def _normalize_forum_stage(stage: str) -> str:
    allowed = {"discussion", "investigation", "disclosure", "conclusion"}
    value = (stage or "").strip().lower()
    return value if value in allowed else "discussion"
from app.simulation.tools.base import AbstractToolExecutor


class ForumToolExecutor(AbstractToolExecutor):
    def __init__(self, forum_service: ForumService) -> None:
        self.forum_service = forum_service
        self._idempotency_cache: dict[str, ActionResult] = {}

    def list_capabilities(self) -> list[CapabilitySpec]:
        board_slugs = [board.slug for board in self.forum_service.list_boards()]
        return [
            CapabilitySpec(
                name="forum.read_board",
                site="forum",
                description="Read threads under a board.",
                input_schema={
                    "board_slug": "string",
                    "limit": "integer optional",
                    "allowed_board_slugs": board_slugs,
                },
                read_only=True,
            ),
            CapabilitySpec(
                name="forum.read_thread",
                site="forum",
                description="Read thread detail with post list.",
                input_schema={"thread_id": "string"},
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
                       "stage": "string optional",
                    "tags": "string[] optional",
                    "allowed_board_slugs": board_slugs,
                },
                read_only=False,
            ),
            CapabilitySpec(
                name="forum.reply_thread",
                site="forum",
                description="Reply to an existing thread.",
                input_schema={"thread_id": "string", "content": "string"},
                read_only=False,
            ),
        ]

    def execute(self, request: ActionRequest) -> ActionResult:
        if request.idempotency_key in self._idempotency_cache:
            return self._idempotency_cache[request.idempotency_key]

        handlers = {
            "forum.read_board": self._read_board,
            "forum.read_thread": self._read_thread,
            "forum.create_thread": self._create_thread,
            "forum.reply_thread": self._reply_thread,
        }
        handler = handlers.get(request.capability)
        if handler is None:
            return ActionResult(
                action_id=request.action_id,
                capability=request.capability,
                status="failed",
                error_code="unsupported_capability",
                error_message=f"Unsupported capability: {request.capability}",
            )

        result = handler(request)
        if result.status == "success":
            self._idempotency_cache[request.idempotency_key] = result
        return result

    def _read_board(self, request: ActionRequest) -> ActionResult:
        board_slug = self._resolve_board_slug(str(request.payload.get("board_slug", "")).strip())
        limit = int(request.payload.get("limit", 10))
        board, threads = self.forum_service.list_board_threads(board_slug)
        if board is None:
            return ActionResult(
                action_id=request.action_id,
                capability=request.capability,
                status="failed",
                error_code="board_not_found",
                error_message=f"Board not found: {board_slug}. Available boards: {', '.join(self._available_board_slugs())}",
            )

        trimmed_threads = threads[: max(1, limit)]
        return ActionResult(
            action_id=request.action_id,
            capability=request.capability,
            status="success",
            output={
                "board": {
                    "slug": board.slug,
                    "name": board.name,
                    "description": board.description,
                },
                "threads": [
                    {
                        "id": thread.id,
                        "title": thread.title,
                        "replies": thread.replies,
                        "last_reply_at": thread.last_reply_at,
                    }
                    for thread in trimmed_threads
                ],
            },
            facts=[f"读取版块={board_slug}", f"读取主题数量={len(trimmed_threads)}"],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="论坛版块读取完成。",
                    metadata={"board_slug": board_slug},
                )
            ],
        )

    def _read_thread(self, request: ActionRequest) -> ActionResult:
        thread_id = str(request.payload.get("thread_id", "")).strip()
        thread = self.forum_service.get_thread(thread_id)
        if thread is None:
            return ActionResult(
                action_id=request.action_id,
                capability=request.capability,
                status="failed",
                error_code="thread_not_found",
                error_message=f"Thread not found: {thread_id}",
            )

        return ActionResult(
            action_id=request.action_id,
            capability=request.capability,
            status="success",
            output={
                "thread": {
                    "id": thread.id,
                    "title": thread.title,
                    "post_count": len(thread.posts),
                }
            },
            facts=[f"读取帖子={thread.id}", f"帖子内容数量={len(thread.posts)}"],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="论坛帖子读取完成。",
                    metadata={"thread_id": thread.id},
                )
            ],
        )

    def _create_thread(self, request: ActionRequest) -> ActionResult:
        board_slug = self._resolve_board_slug(str(request.payload.get("board_slug", "")).strip())
        raw_title = str(request.payload.get("title", "")).strip()
        raw_content = str(request.payload.get("content", "")).strip()
        title = sanitize_forum_title(raw_title)
        content = sanitize_forum_content(raw_content)
        tags = request.payload.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        stage = _normalize_forum_stage(str(request.payload.get("stage", "discussion")))

        board, _ = self.forum_service.list_board_threads(board_slug)
        if board is None:
            return ActionResult(
                action_id=request.action_id,
                capability=request.capability,
                status="failed",
                error_code="board_not_found",
                error_message=f"Board not found: {board_slug}. Available boards: {', '.join(self._available_board_slugs())}",
            )

        thread = self.forum_service.create_thread(
            board_slug=board_slug,
            author_id=request.actor_id,
            title=title,
            content=content,
            stage=stage,
            tags=[str(tag) for tag in tags],
        )

        return ActionResult(
            action_id=request.action_id,
            capability=request.capability,
            status="success",
            output={"thread_id": thread.id, "sanitized_title": title, "sanitized_content": content},
            facts=[
                f"创建主题={thread.id}",
                f"版块={thread.board_slug}",
                f"作者={thread.author_id}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="论坛已创建主题并写入首帖。",
                    metadata={"thread_id": thread.id, "board_slug": thread.board_slug},
                ),
                StoryEvent(
                    name="FactPersisted",
                    detail="论坛主题事实已持久化。",
                    metadata={"thread_id": thread.id},
                ),
            ],
        )

    def _available_board_slugs(self) -> list[str]:
        return [board.slug for board in self.forum_service.list_boards()]

    def _resolve_board_slug(self, raw_value: str) -> str:
        value = raw_value.strip().lower()
        if not value:
            return value

        available = {board.slug: board.slug for board in self.forum_service.list_boards()}
        for board in self.forum_service.list_boards():
            available[board.name.strip().lower()] = board.slug

        aliases = {
            "general": "town-square",
            "general-discussion": "town-square",
            "town square": "town-square",
            "main-forum": "town-square",
            "market": "bazaar",
            "shop": "bazaar",
            "dm": "whispers",
            "private": "whispers",
        }

        if value in aliases:
            return aliases[value]
        return available.get(value, value)

    def _reply_thread(self, request: ActionRequest) -> ActionResult:
        thread_id = str(request.payload.get("thread_id", "")).strip()
        raw_content = str(request.payload.get("content", "")).strip()
        content = sanitize_forum_content(raw_content)
        post = self.forum_service.reply_thread(thread_id=thread_id, author_id=request.actor_id, content=content)
        if post is None:
            return ActionResult(
                action_id=request.action_id,
                capability=request.capability,
                status="failed",
                error_code="thread_not_found",
                error_message=f"Thread not found: {thread_id}",
            )

        return ActionResult(
            action_id=request.action_id,
            capability=request.capability,
            status="success",
            output={"post_id": post.id, "thread_id": thread_id, "sanitized_content": content},
            facts=[f"新回复={post.id}", f"所属主题={thread_id}", f"作者={request.actor_id}"],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="论坛回复已写入。",
                    metadata={"thread_id": thread_id, "post_id": post.id},
                ),
                StoryEvent(
                    name="FactPersisted",
                    detail="论坛回复事实已持久化。",
                    metadata={"post_id": post.id},
                ),
            ],
        )
