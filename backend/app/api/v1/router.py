"""Version 1 API router, mounted at /api/v1.

Endpoint routers are included here as their phases are implemented
(see docs/IMPLEMENTATION_STATUS.md and API_CONTRACT.md).
"""

from fastapi import APIRouter

from app.api.v1.repositories import router as repositories_router

API_V1_PREFIX = "/api/v1"

router = APIRouter(prefix=API_V1_PREFIX)
router.include_router(repositories_router)
