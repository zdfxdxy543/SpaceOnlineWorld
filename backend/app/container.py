from __future__ import annotations

from dataclasses import dataclass

from app.consistency.checker import ConsistencyChecker
from app.core.config import Settings
from app.infrastructure.db.forum_repository import SQLiteForumRepository
from app.infrastructure.db.mainpage_repository import SQLiteMainPageRepository
from app.infrastructure.db.netdisk_repository import SQLiteNetdiskRepository
from app.infrastructure.db.news_repository import SQLiteNewsRepository
from app.infrastructure.db.paper_repository import SQLitePaperRepository
from app.infrastructure.db.p2pstore_repository import SQLiteP2PStoreRepository
from app.infrastructure.db.session import DatabaseSessionManager
from app.infrastructure.db.social_repository import SQLiteSocialRepository
from app.infrastructure.db.world_repository import SQLiteWorldRepository
from app.infrastructure.llm.base import AbstractLLMClient
from app.infrastructure.llm.siliconflow_client import SiliconFlowLLMClient
from app.infrastructure.llm.structured_content import (
    AbstractStructuredContentGenerator,
    SiliconFlowStructuredContentGenerator,
)
from app.infrastructure.llm.siliconflow_planner import SiliconFlowStoryPlanner
from app.repositories.forum_repository import AbstractForumRepository
from app.repositories.news_repository import AbstractNewsRepository
from app.repositories.paper_repository import AbstractPaperRepository
from app.services.forum_service import ForumService
from app.services.generation_service import GenerationService
from app.services.mainpage_service import MainPageService
from app.services.netdisk_service import NetdiskService
from app.services.news_service import NewsService
from app.services.paper_service import PaperService
from app.services.p2pstore_service import P2PStoreService
from app.services.social_service import SocialService
from app.services.story_arc_service import StoryArcService
from app.services.world_service import WorldService
from app.simulation.engine import SimulationEngine
from app.simulation.planner import (
    AbstractStoryPlanner,
    LifeEventStoryPlanner,
    OngoingDetectiveArcPlanner,
    OngoingLifeArcPlanner,
    RuleBasedStoryPlanner,
)
from app.simulation.scheduler import StoryScheduler
from app.simulation.tool_registry import ToolRegistry
from app.simulation.tools.forum_pipeline import ForumPipelineToolExecutor
from app.simulation.tools.mainpage_pipeline import MainPagePipelineToolExecutor
from app.simulation.tools.netdisk_pipeline import NetdiskPipelineToolExecutor
from app.simulation.tools.news_pipeline import NewsPipelineToolExecutor
from app.simulation.tools.p2pstore_pipeline import P2PStorePipelineToolExecutor
from app.simulation.tools.social_pipeline import SocialPipelineToolExecutor


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    database_session_manager: DatabaseSessionManager
    world_service: WorldService
    story_arc_service: StoryArcService
    forum_service: ForumService
    netdisk_service: NetdiskService
    news_service: NewsService
    paper_service: PaperService
    p2pstore_service: P2PStoreService
    social_service: SocialService
    mainpage_service: MainPageService
    tool_registry: ToolRegistry
    story_scheduler: StoryScheduler
    life_story_scheduler: StoryScheduler
    life_arc_story_scheduler: StoryScheduler
    detective_arc_story_scheduler: StoryScheduler


def build_container(settings: Settings) -> ServiceContainer:
    if settings.llm_provider.lower() != "siliconflow":
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER={settings.llm_provider}. Strict mode requires LLM_PROVIDER=siliconflow."
        )
    if not settings.siliconflow_api_key:
        raise RuntimeError("LLM_PROVIDER=siliconflow but SILICONFLOW_API_KEY is missing")

    database_session_manager = DatabaseSessionManager(settings.database_url)
    forum_repository: AbstractForumRepository = SQLiteForumRepository(database_session_manager)
    forum_repository.initialize()
    database_session_manager.mark_initialized()

    world_repository = SQLiteWorldRepository(database_session_manager)
    world_repository.initialize()
    simulation_engine = SimulationEngine(world_repository)
    consistency_checker = ConsistencyChecker()
    llm_client: AbstractLLMClient = SiliconFlowLLMClient(
        api_key=settings.siliconflow_api_key,
        model_name=settings.llm_model,
        base_url=settings.siliconflow_base_url,
        max_attempts=3,
    )
    generation_service = GenerationService(llm_client, consistency_checker)
    world_service = WorldService(world_repository, simulation_engine, generation_service)
    story_arc_service = StoryArcService(database_session_manager)
    story_arc_service.initialize()
    forum_service = ForumService(forum_repository)
    netdisk_repository = SQLiteNetdiskRepository(database_session_manager)
    netdisk_repository.initialize()
    netdisk_service = NetdiskService(netdisk_repository, storage_dir=settings.netdisk_storage_dir)
    news_repository: AbstractNewsRepository = SQLiteNewsRepository(database_session_manager)
    news_repository.initialize()
    news_service = NewsService(news_repository)

    paper_repository: AbstractPaperRepository = SQLitePaperRepository(database_session_manager)
    paper_repository.initialize()
    paper_service = PaperService(paper_repository)

    p2pstore_repository = SQLiteP2PStoreRepository(database_session_manager)
    p2pstore_repository.initialize()
    p2pstore_service = P2PStoreService(p2pstore_repository)
    mainpage_repository = SQLiteMainPageRepository(database_session_manager)
    mainpage_repository.initialize()
    mainpage_service = MainPageService(mainpage_repository)

    social_repository = SQLiteSocialRepository(database_session_manager)
    social_repository.initialize()
    social_service = SocialService(social_repository)

    content_generator: AbstractStructuredContentGenerator = SiliconFlowStructuredContentGenerator(
        api_key=settings.siliconflow_api_key,
        model_name=settings.llm_model,
        base_url=settings.siliconflow_base_url,
        max_attempts=3,
        request_timeout_seconds=settings.siliconflow_content_timeout_seconds,
        retry_backoff_seconds=settings.siliconflow_content_retry_backoff_seconds,
    )

    from app.simulation.tools.image_pipeline import ImagePipelineToolExecutor
    from app.simulation.tools.paper_pipeline import PaperPipelineToolExecutor
    tool_registry = ToolRegistry(
        executors=[
            NetdiskPipelineToolExecutor(netdisk_service, content_generator),
            ForumPipelineToolExecutor(forum_service, consistency_checker, netdisk_service, content_generator),
            NewsPipelineToolExecutor(
                news_service,
                consistency_checker,
                content_generator,
                forum_service,
                netdisk_service,
            ),
            P2PStorePipelineToolExecutor(
                p2pstore_service,
                consistency_checker,
                content_generator,
            ),
            MainPagePipelineToolExecutor(mainpage_service, consistency_checker, content_generator),
            SocialPipelineToolExecutor(social_service, consistency_checker, content_generator),
            ImagePipelineToolExecutor(content_generator),
            PaperPipelineToolExecutor(
                paper_service,
                consistency_checker,
                content_generator,
                forum_service,
                netdisk_service,
            ),
        ]
    )

    planner: AbstractStoryPlanner = SiliconFlowStoryPlanner(
        api_key=settings.siliconflow_api_key,
        model_name=settings.siliconflow_planner_model,
        base_url=settings.siliconflow_base_url,
        max_attempts=3,
    )

    story_scheduler = StoryScheduler(
        planner=planner,
        tool_registry=tool_registry,
        publication_delay_probability=settings.scheduler_publication_delay_probability,
        publication_delay_min_seconds=settings.scheduler_publication_delay_min_seconds,
        publication_delay_max_seconds=settings.scheduler_publication_delay_max_seconds,
    )

    life_planner: AbstractStoryPlanner = LifeEventStoryPlanner(
        netdisk_probability=settings.scheduler_life_netdisk_probability,
        news_probability=settings.scheduler_life_news_probability,
    )
    life_story_scheduler = StoryScheduler(
        planner=life_planner,
        tool_registry=tool_registry,
        publication_delay_probability=settings.scheduler_publication_delay_probability,
        publication_delay_min_seconds=settings.scheduler_publication_delay_min_seconds,
        publication_delay_max_seconds=settings.scheduler_publication_delay_max_seconds,
    )

    life_arc_planner: AbstractStoryPlanner = OngoingLifeArcPlanner(
        story_arc_service=story_arc_service,
        reveal_after_hours=settings.scheduler_life_arc_reveal_after_hours,
        news_resolution_probability=settings.scheduler_life_arc_news_resolution_probability,
    )
    life_arc_story_scheduler = StoryScheduler(
        planner=life_arc_planner,
        tool_registry=tool_registry,
        publication_delay_probability=settings.scheduler_publication_delay_probability,
        publication_delay_min_seconds=settings.scheduler_publication_delay_min_seconds,
        publication_delay_max_seconds=settings.scheduler_publication_delay_max_seconds,
    )

    detective_arc_planner: AbstractStoryPlanner = OngoingDetectiveArcPlanner(
        story_arc_service=story_arc_service,
        reveal_after_hours=settings.scheduler_detective_arc_reveal_after_hours,
        resolution_news_probability=settings.scheduler_detective_arc_news_resolution_probability,
        netdisk_probability=settings.scheduler_detective_arc_netdisk_probability,
    )
    detective_arc_story_scheduler = StoryScheduler(
        planner=detective_arc_planner,
        tool_registry=tool_registry,
        publication_delay_probability=settings.scheduler_publication_delay_probability,
        publication_delay_min_seconds=settings.scheduler_publication_delay_min_seconds,
        publication_delay_max_seconds=settings.scheduler_publication_delay_max_seconds,
    )

    return ServiceContainer(
        settings=settings,
        database_session_manager=database_session_manager,
        world_service=world_service,
        story_arc_service=story_arc_service,
        forum_service=forum_service,
        netdisk_service=netdisk_service,
        news_service=news_service,
        paper_service=paper_service,
        p2pstore_service=p2pstore_service,
        social_service=social_service,
        mainpage_service=mainpage_service,
        tool_registry=tool_registry,
        story_scheduler=story_scheduler,
        life_story_scheduler=life_story_scheduler,
        life_arc_story_scheduler=life_arc_story_scheduler,
        detective_arc_story_scheduler=detective_arc_story_scheduler,
    )
