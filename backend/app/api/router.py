from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.ai_image import router as ai_image_router
from app.api.v1.endpoints.forum import router as forum_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.mainpage import router as mainpage_router
from app.api.v1.endpoints.netdisk import router as netdisk_router
from app.api.v1.endpoints.news import router as news_router
from app.api.v1.endpoints.p2pstore import router as p2pstore_router
from app.api.v1.endpoints.social import router as social_router
from app.api.v1.endpoints.world import router as world_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(world_router, prefix="/world", tags=["world"])
api_router.include_router(forum_router, prefix="/forum", tags=["forum"])
api_router.include_router(netdisk_router, prefix="/netdisk", tags=["netdisk"])
api_router.include_router(news_router, prefix="/news", tags=["news"])
api_router.include_router(p2pstore_router, prefix="/p2pstore", tags=["p2pstore"])
api_router.include_router(social_router, prefix="/social", tags=["social"])
api_router.include_router(mainpage_router, prefix="/main-pages", tags=["main-pages"])
api_router.include_router(ai_router, prefix="/ai", tags=["ai"])
api_router.include_router(ai_image_router, tags=["ai_image"])
